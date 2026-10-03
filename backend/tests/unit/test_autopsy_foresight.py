"""Complaint Autopsy and Foresight tests (deck S11, plan §3.3-3.4, §12.9)."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from clarity.kernel.common import Language
from clarity.modules.autopsy.pipeline import (
    CANONICAL_TO_RULE,
    ClusterStatus,
    Complaint,
    ComplaintAutopsy,
    canonicalise,
    detect_language,
)
from clarity.modules.foresight.backtest import (
    DEMO_LAUNCHES,
    MIN_REAL_LAUNCHES,
    Backtest,
    CalibrationStatus,
    HistoricLaunch,
    ObservedOutcome,
    Provenance,
)
from clarity.modules.foresight.simulation import (
    DEMO_SEGMENTS,
    ChangeType,
    Foresight,
    Scenario,
    Segment,
    VolumeBand,
)


def complaints(*texts: str) -> list[Complaint]:
    return [Complaint(complaint_id=f"C{i}", text=t) for i, t in enumerate(texts)]


# --------------------------------------------------------------------------- #
# Autopsy - clean and protect comes first
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("my balance is gone", Language.EN),
        ("මගේ ශේෂය නැති වී ඇත", Language.SI),
        ("என் இருப்பு போய்விட்டது", Language.TA),
        ("mata denna balance eka cut vela", Language.EN),  # Singlish is Latin script
    ],
)
def test_language_is_detected_from_script(text, expected):
    assert detect_language(text) is expected


def test_personal_data_is_masked_before_anything_else_reads_it():
    """Deck S11 step 1: mask PII first, then understand."""
    autopsy = ComplaintAutopsy()

    cleaned, _, _ = autopsy.clean(complaints("call me on 0771234567, my VAS charge is wrong"))

    assert "0771234567" not in cleaned[0].masked_text
    assert "<PHONE_1>" in cleaned[0].masked_text


def test_a_complaint_quoting_a_credential_is_dropped_entirely():
    """It must not enter analytics at all, masked or otherwise (deck S8)."""
    autopsy = ComplaintAutopsy()

    cleaned, _, refused = autopsy.clean(complaints("my OTP 483920 was used for a subscription"))

    assert cleaned == []
    assert refused == 1


def test_duplicates_are_removed():
    autopsy = ComplaintAutopsy()

    _, duplicates, _ = autopsy.clean(
        complaints("my balance is gone", "My Balance Is Gone!", "data stopped")
    )

    assert duplicates == 1


# --------------------------------------------------------------------------- #
# Autopsy - understanding and clustering
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "canonical"),
    [
        ("I was subscribed to a game without asking", "vas charged without consent"),
        ("reload taken twice from my bank", "reload taken twice"),
        ("recharged but did not receive balance", "reload not credited"),
        ("unlimited data became very slow", "data stopped at cap"),
    ],
)
def test_complaints_reduce_to_a_canonical_form(text, canonical):
    assert canonicalise(text) == canonical


def test_the_same_problem_in_three_languages_lands_in_one_cluster():
    """The point of the canonical step (deck S11 step 2)."""
    report = ComplaintAutopsy().run(
        complaints(
            "I was charged for a subscription I never asked for",
            "දායකත්වයක් සඳහා අය කර ඇත, මම ඉල්ලුවේ නැහැ",
            "நான் கேட்காத சந்தாவுக்கு கட்டணம்",
        )
    )

    consent = [c for c in report.clusters if c.label == "vas charged without consent"]
    assert consent and consent[0].size == 3
    assert set(consent[0].languages) == {"en", "si", "ta"}


def test_a_cluster_suggests_the_rule_that_would_explain_it():
    report = ComplaintAutopsy().run(
        complaints("reload taken twice", "the reload was taken twice by the bank")
    )

    assert report.clusters[0].suggested_rule_id == "DUPLICATE_RELOAD"


def test_every_suggested_rule_is_one_we_actually_have():
    """A suggestion pointing at a rule that does not exist would be noise."""
    from pathlib import Path

    from clarity.modules.detection.pack import load_packs

    packs = Path(__file__).resolve().parents[3] / "rules" / "packs"
    known = {p.rule_id for p in load_packs(packs)}

    assert set(CANONICAL_TO_RULE.values()) <= known


def test_a_lone_complaint_is_noise_not_a_cluster():
    """One report is not a pattern, and presenting it as one would mislead."""
    report = ComplaintAutopsy().run(complaints("something odd happened once"))

    assert report.clusters == []
    assert len(report.noise) == 1


def test_clusters_start_as_hypotheses():
    """Deck S11: nothing is published until a CX engineer confirms it."""
    report = ComplaintAutopsy().run(complaints("reload taken twice", "reload was taken twice"))

    assert all(c.status is ClusterStatus.HYPOTHESIS for c in report.clusters)


def test_a_reviewer_confirms_or_rejects_a_cluster():
    """Moved to the review workflow by AU01 (#13).

    This used to call `ComplaintAutopsy.confirm`, which recorded the verdict by
    appending "(reviewed by cx-eng-1)" to the cluster's **label** and asserted
    the reviewer's name was in it. That is why the assertion changed shape: the
    verdict is now a record with a time and a note, and the label is left
    alone.
    """
    from clarity.modules.autopsy.public import ClusterReviews, ReviewedCluster

    report = ComplaintAutopsy().run(complaints("reload taken twice", "reload was taken twice"))
    held = ReviewedCluster(cluster=report.clusters[0])

    confirmed = ClusterReviews().record(held, reviewer="cx-eng-1", accept=True)

    assert confirmed.status is ClusterStatus.CONFIRMED
    assert confirmed.cluster.label == held.cluster.label
    assert confirmed.latest is not None
    assert confirmed.latest.reviewer == "cx-eng-1"
    assert confirmed.latest.at


def test_the_report_counts_what_happened_to_everything():
    report = ComplaintAutopsy().run(
        complaints(
            "reload taken twice",
            "reload was taken twice by bank",
            "reload taken twice",  # duplicate
            "my OTP is 123456",  # refused
        )
    )

    assert report.total_received == 4
    assert report.duplicates_removed == 1
    assert report.refused == 1
    assert 0 < report.coverage <= 1


# --------------------------------------------------------------------------- #
# Foresight - honest by construction
# --------------------------------------------------------------------------- #


def test_a_scenario_predicts_themes_per_segment():
    report = Foresight().run(
        Scenario(name="Retire the 10GB pack", change_type=ChangeType.PACK_RETIRED)
    )

    assert report.predictions
    assert "pack sunset confusion" in report.top_themes
    assert {p.segment for p in report.predictions} == {s.name for s in DEMO_SEGMENTS}


def test_predictions_are_bands_never_counts():
    """Deck S11: 'scenarios, not certainties'."""
    report = Foresight().run(Scenario(name="FUP change", change_type=ChangeType.FUP_TIGHTENED))

    assert all(isinstance(p.band, VolumeBand) for p in report.predictions)


def test_every_prediction_comes_with_something_to_do_about_it():
    report = Foresight().run(Scenario(name="Outage", change_type=ChangeType.OUTAGE))

    assert all(p.suggested_mitigation for p in report.predictions)


def test_a_report_states_that_it_used_no_individual_data():
    """Deck S8: Foresight on aggregates only."""
    report = Foresight().run(Scenario(name="Price up", change_type=ChangeType.PRICE_INCREASE))

    assert "no individual" in report.basis.lower()


def test_a_report_is_not_decision_ready_until_backtested():
    """Plan §3.4 gate: no launch decision rests on an uncalibrated model."""
    report = Foresight().run(Scenario(name="Price up", change_type=ChangeType.PRICE_INCREASE))

    assert not report.is_decision_ready
    assert any("backtest" in c.lower() for c in report.caveats)
    assert any("certaint" in c.lower() for c in report.caveats)


def test_a_bigger_change_predicts_more_complaints_than_a_smaller_one():
    big = Foresight().run(
        Scenario(name="big", change_type=ChangeType.FUP_TIGHTENED, severity=Decimal("2.0"))
    )
    small = Foresight().run(
        Scenario(name="small", change_type=ChangeType.FUP_TIGHTENED, severity=Decimal("0.5"))
    )

    assert big.predictions[0].relative_score > small.predictions[0].relative_score


def test_data_heavy_segments_dominate_a_data_change():
    report = Foresight().run(Scenario(name="FUP", change_type=ChangeType.FUP_TIGHTENED))

    assert report.predictions[0].segment == "students", "the most data-intensive segment"


def test_a_segment_share_outside_zero_to_one_is_rejected():
    with pytest.raises(ValueError, match="fraction"):
        Segment("impossible", Decimal("1.5"), Decimal("0.1"))


def test_the_run_is_deterministic():
    scenario = Scenario(name="Retire pack", change_type=ChangeType.PACK_RETIRED)

    first = [p.relative_score for p in Foresight().run(scenario).predictions]
    second = [p.relative_score for p in Foresight().run(scenario).predictions]

    assert first == second


def test_every_complaint_is_accounted_for_somewhere():
    """Nothing may silently vanish between intake and the report."""
    report = ComplaintAutopsy().run(
        complaints(
            "reload taken twice",
            "the reload was taken twice",
            "a completely unrelated one-off problem",
            "another unrelated and dissimilar thing entirely",
            "reload taken twice",  # duplicate
            "my OTP is 998877",  # refused
        )
    )

    clustered = sum(c.size for c in report.clusters)
    assert clustered + len(report.noise) + report.duplicates_removed + report.refused == (
        report.total_received
    )


# -- AU01 (#13): event-fed, and labelled as a hypothesis ------------------ #


class FakeComplaints:
    """The complaint store the service reads text from.

    A seam rather than the event, because `ComplaintCreatedV1` carries no text:
    putting customer words in the message bus is what that shape avoids.
    """

    def __init__(self, **rows: str) -> None:
        self.rows = dict(rows)
        self.asked: list[str] = []

    def text_for(self, complaint_id: str) -> str | None:
        self.asked.append(complaint_id)
        return self.rows.get(complaint_id)


TWICE = {
    "c1": "my reload was taken twice",
    "c2": "reload taken twice again",
    "c3": "the reload got taken twice",
}


def fed(**rows: str):
    """A service with complaints already accepted and clustered."""
    from clarity.modules.autopsy.public import AutopsyService

    source = FakeComplaints(**rows)
    service = AutopsyService(source=source)
    for complaint_id in rows:
        service.accept(complaint_id)
    service.rerun()
    return service, source


def test_an_unreviewed_cluster_is_labelled_as_a_hypothesis():
    """AU01 acceptance 1, and the reason the module exists in this shape.

    A cluster is a machine's guess that several complaints share one cause.
    Shown to a CX engineer labelled as a hypothesis it is useful; shown without
    that label it is a finding nobody established, which I16 forbids.

    The assertion is on the staff-facing representation rather than on the
    status enum, because the status being right while the screen says nothing
    about it is exactly the failure this guards against.
    """
    from clarity.modules.autopsy.public import HYPOTHESIS_LABEL

    service, _source = fed(**TWICE)

    views = service.for_staff()

    assert views, "nothing was clustered, so nothing below is tested"
    for view in views:
        assert view["hypothesis"] is True
        assert view["status_label"] == HYPOTHESIS_LABEL
        assert view["status"] == "hypothesis"
        assert view["reviewed_by"] is None
        # Nothing has been acted on, and the surface says so rather than
        # leaving a reader to assume either way.
        assert view["acted_on"] is False


def test_a_suggested_rule_on_an_unreviewed_cluster_is_marked_a_guess():
    """A rule id beside a cluster reads as "this is caused by that".

    On an unreviewed cluster nothing has established that, so the flag travels
    with the id. Dropping the id instead would lose the one thing a reviewer
    most wants to see.
    """
    service, _source = fed(**TWICE)

    with_rules = [v for v in service.for_staff() if v["suggested_rule_id"]]

    assert with_rules, "no cluster suggested a rule, so this asserts nothing"
    for view in with_rules:
        assert view["suggested_rule_is_a_guess"] is True


def test_a_confirmed_cluster_is_still_not_a_published_rule():
    """Confirmed is a person agreeing, not a change being made.

    Turning a confirmed cause into a rule goes through the policy lifecycle
    (plan 20), so the surface must not imply the loop is closed.
    """
    from clarity.modules.autopsy.public import CONFIRMED_LABEL

    service, _source = fed(**TWICE)
    cluster_id = service.for_staff()[0]["cluster_id"]

    service.review(cluster_id, reviewer="cx-eng-1", accept=True, note="real")

    view = next(v for v in service.for_staff() if v["cluster_id"] == cluster_id)
    assert view["hypothesis"] is False
    assert view["status_label"] == CONFIRMED_LABEL
    assert view["acted_on"] is False
    assert view["suggested_rule_is_a_guess"] is False


# -- the review workflow -------------------------------------------------- #


def test_a_verdict_is_a_record_and_not_a_label_edit():
    """The first version of `confirm` wrote the reviewer into the label.

    That put audit data in display text, appended twice if it ran twice, and
    kept no time, no note and nothing to look up. A verdict is evidence about
    who decided what and when.
    """
    service, _source = fed(**TWICE)
    before = service.for_staff()[0]
    cluster_id = before["cluster_id"]

    service.review(cluster_id, reviewer="cx-eng-1", accept=True, note="matches VAS consent")

    after = next(v for v in service.for_staff() if v["cluster_id"] == cluster_id)
    assert after["label"] == before["label"], "the label was mutated by a review"
    assert after["reviewed_by"] == "cx-eng-1"
    assert after["reviewed_at"]
    assert len(after["reviews"]) == 1
    assert after["reviews"][0]["note"] == "matches VAS consent"


def test_a_second_verdict_is_refused_rather_than_silently_overwriting():
    """The first verdict was somebody's professional judgement."""
    from clarity.modules.autopsy.public import ReviewRefused

    service, _source = fed(**TWICE)
    cluster_id = service.for_staff()[0]["cluster_id"]
    service.review(cluster_id, reviewer="cx-eng-1", accept=True)

    with pytest.raises(ReviewRefused, match="already reviewed"):
        service.review(cluster_id, reviewer="cx-eng-2", accept=False)


def test_superseding_a_verdict_keeps_the_one_it_replaced():
    """Changing a decision is allowed; erasing the previous one is not."""
    service, _source = fed(**TWICE)
    cluster_id = service.for_staff()[0]["cluster_id"]
    service.review(cluster_id, reviewer="cx-eng-1", accept=True)

    service.review(
        cluster_id,
        reviewer="cx-lead",
        accept=False,
        note="two causes, not one",
        supersede=True,
    )

    view = next(v for v in service.for_staff() if v["cluster_id"] == cluster_id)
    assert view["status"] == "rejected"
    assert len(view["reviews"]) == 2
    assert view["reviews"][0]["reviewer"] == "cx-eng-1"
    assert view["reviews"][1]["supersedes"] == view["reviews"][0]["review_id"]


def test_superseding_needs_a_reason():
    """An unexplained reversal is the thing an auditor asks about."""
    from clarity.modules.autopsy.public import ReviewRefused

    service, _source = fed(**TWICE)
    cluster_id = service.for_staff()[0]["cluster_id"]
    service.review(cluster_id, reviewer="cx-eng-1", accept=True)

    with pytest.raises(ReviewRefused, match="reason"):
        service.review(cluster_id, reviewer="cx-lead", accept=False, note="", supersede=True)


def test_an_anonymous_verdict_is_refused():
    from clarity.modules.autopsy.public import ReviewRefused

    service, _source = fed(**TWICE)
    cluster_id = service.for_staff()[0]["cluster_id"]

    with pytest.raises(ReviewRefused, match="reviewer"):
        service.review(cluster_id, reviewer="   ", accept=True)


def test_a_rerun_keeps_reviewed_clusters_and_redraws_the_rest():
    """A re-run may not discard somebody's recorded judgement.

    Leaving the old hypotheses instead would show a reviewer two overlapping
    guesses about the same complaints, so unreviewed ones are redrawn.
    """
    service, _source = fed(**TWICE)
    cluster_id = service.for_staff()[0]["cluster_id"]
    service.review(cluster_id, reviewer="cx-eng-1", accept=True, note="real")

    service.rerun()

    kept = [v for v in service.for_staff() if v["cluster_id"] == cluster_id]
    assert len(kept) == 1, "the reviewed cluster was dropped by a re-run"
    assert kept[0]["reviewed_by"] == "cx-eng-1"


# -- the event feed ------------------------------------------------------- #


def test_the_consumer_reads_the_text_from_the_store_not_the_event():
    """`ComplaintCreatedV1` carries no text, deliberately.

    Putting a customer's words in the message bus would copy complaint content
    somewhere nobody owns its retention, which is the same reason
    `conversation.turn.completed` carries no message text.
    """
    from clarity.contracts.events import ComplaintCreatedV1
    from clarity.kernel.common import Channel, Language
    from clarity.modules.autopsy.public import AutopsyService
    from clarity.platform.messaging.envelope import Event

    source = FakeComplaints(**TWICE)
    service = AutopsyService(source=source)

    service.on_complaint_created(
        Event.of(
            ComplaintCreatedV1(complaint_id="c1", channel=Channel.APP, language=Language.EN),
            subject="sub_x",
        )
    )

    assert source.asked == ["c1"], "the consumer did not ask the store for the text"
    assert "text" not in ComplaintCreatedV1.model_fields, (
        "the event gained a text field; autopsy would then be storing bus content"
    )


def test_a_redelivered_event_does_not_inflate_a_cluster():
    """Consumers are idempotent (I7), and a cluster's size is a claim.

    The same complaint counted twice makes three complaints look like four,
    which is the number a reviewer decides on.
    """
    service, _source = fed(**TWICE)
    before = sorted(v["size"] for v in service.for_staff())

    for complaint_id in TWICE:
        service.accept(complaint_id)
    service.rerun()

    assert sorted(v["size"] for v in service.for_staff()) == before


def test_only_masked_text_is_stored():
    """Masking happens before anything else reads a complaint (I13).

    What reaches the repository is the masked form, so the store holds no raw
    customer words.
    """
    from clarity.modules.autopsy.public import AutopsyService

    source = FakeComplaints(c9="call me on 0771234567 about the double charge")
    service = AutopsyService(source=source)

    service.accept("c9")

    with service._open_unit() as unit:
        stored = unit.repository("autopsy.complaints").values()
    assert stored, "nothing was stored"
    assert "0771234567" not in stored[0].masked_text
    assert not hasattr(stored[0], "text"), "the raw text travelled with the record"


def test_a_complaint_quoting_a_credential_is_never_stored():
    """The pipeline's existing rule, asserted on the way into the store.

    A message containing a PIN is not evidence about a billing pattern, and
    masking it would still leave it in a store of complaints.
    """
    from clarity.modules.autopsy.public import AutopsyService

    service = AutopsyService(source=FakeComplaints(c9="my PIN is 4321 and I was charged twice"))

    outcome = service.accept("c9")

    assert outcome.stored is False
    assert outcome.refused
    assert service.clusters() == []


def test_a_complaint_with_no_text_is_not_an_error():
    """It may not have reached the store the relay reads yet.

    At-least-once means a redelivery will find it, so losing the event would
    be worse than returning nothing.
    """
    from clarity.modules.autopsy.public import AutopsyService

    service = AutopsyService(source=FakeComplaints())

    outcome = service.accept("missing")

    assert outcome.stored is False
    assert outcome.reason == "no_text"


def test_the_similarity_measure_is_replaceable_and_named_for_what_it_is():
    """The `embed` role seam. There is no embedding model in the system.

    `TrigramSimilarity` is character overlap and is named so nobody reads a
    cluster as semantically grouped. An embedding-backed measure drops in here
    without touching the clustering, and still produces hypotheses.
    """
    from clarity.modules.autopsy.public import ComplaintAutopsy, TrigramSimilarity

    class NothingIsAlike:
        def score(self, left: str, right: str) -> float:
            return 0.0

    alike = ComplaintAutopsy(measure=TrigramSimilarity())
    apart = ComplaintAutopsy(measure=NothingIsAlike())
    texts = ["the thing is totally broken today", "that thing is totally broken today"]

    assert alike.run(complaints(*texts)).clusters, "trigrams found nothing alike"
    # Canonicalisation still groups known phrases, so this asserts the measure
    # is consulted rather than that clustering collapses entirely.
    assert apart.run(complaints(*texts)).noise, "the injected measure was ignored"


# --------------------------------------------------------------------------- #
# Foresight backtest and calibration (F01, plan 02 §3.4)
# --------------------------------------------------------------------------- #


def real(launch: HistoricLaunch) -> HistoricLaunch:
    """The same launch, relabelled as a real one.

    No real launch record exists in the prototype (REQUIRES HUTCH
    CONFIRMATION). These tests relabel a simulated one purely to prove the
    gate opens on real evidence and on nothing else.
    """
    return replace(launch, provenance=Provenance.REAL)


def test_a_backtest_states_the_calibration_error_and_that_results_are_scenarios():
    """Acceptance 1. The number and the hedge travel together or not at all."""
    report = Backtest().run(DEMO_LAUNCHES)

    assert report.compared > 0
    assert report.mean_absolute_band_error is not None
    assert str(report.mean_absolute_band_error) in report.summary()
    assert "scenarios, not certainties" in report.summary().lower()
    assert any("scenarios, not certainties" in c.lower() for c in report.caveats)


def test_the_error_is_measured_in_band_steps_not_complaints():
    report = Backtest().run(DEMO_LAUNCHES)

    assert "band steps" in report.summary()
    assert any("not in complaints" in c.lower() for c in report.caveats)
    assert all(abs(m.step_error) <= 2 for m in report.misses)


def test_a_synthetic_backtest_never_claims_calibration():
    """I16: a launch we authored cannot validate the model that predicted it."""
    report = Backtest().run(DEMO_LAUNCHES)

    assert report.real_launches == 0
    assert report.status is CalibrationStatus.NOT_CALIBRATED
    assert not report.is_calibrated
    assert any("validates nothing" in c.lower() for c in report.caveats)
    assert any("simulated" in c.lower() for c in report.caveats)


def test_real_launches_below_the_gate_are_insufficient_not_calibrated():
    below = (real(DEMO_LAUNCHES[0]), real(DEMO_LAUNCHES[1]))

    report = Backtest().run(below)

    assert report.real_launches == 2 < MIN_REAL_LAUNCHES
    assert report.status is CalibrationStatus.INSUFFICIENT
    assert not report.is_calibrated
    assert any(str(MIN_REAL_LAUNCHES) in c and "gate" in c for c in report.caveats)


def test_the_gate_opens_only_at_three_real_launches():
    report = Backtest().run(tuple(real(launch) for launch in DEMO_LAUNCHES))

    assert report.real_launches == MIN_REAL_LAUNCHES
    assert report.status is CalibrationStatus.CALIBRATED
    assert report.is_calibrated


def test_mixing_synthetic_launches_in_does_not_help_reach_the_gate():
    mixed = (real(DEMO_LAUNCHES[0]), DEMO_LAUNCHES[1], DEMO_LAUNCHES[2])

    assert Backtest().run(mixed).status is CalibrationStatus.INSUFFICIENT


def test_an_observed_theme_the_model_missed_is_reported_not_dropped():
    """Under-prediction is the dangerous direction, so it must stay visible."""
    report = Backtest().run(DEMO_LAUNCHES)

    missed = {(o.theme, o.segment) for o in report.unpredicted}
    assert ("roaming bill shock", "tourists") in missed
    assert all((m.theme, m.segment) != ("roaming bill shock", "tourists") for m in report.misses), (
        "a theme the model never predicted cannot count towards its error"
    )
    assert any("never predicted" in c.lower() for c in report.caveats)


def test_a_prediction_with_no_record_is_not_treated_as_a_quiet_launch():
    report = Backtest().run(DEMO_LAUNCHES)

    assert report.unobserved, "the demo launches record a few themes, not all of them"
    assert any("absence of a record is not a low observation" in c.lower() for c in report.caveats)


def test_nothing_comparable_reports_no_error_rather_than_a_perfect_one():
    """A 0.000 over zero pairs would read as a flawless model."""
    nothing = (
        HistoricLaunch(
            launch_id="SIM-LAUNCH-EMPTY",
            scenario=Scenario(name="quiet", change_type=ChangeType.POLICY_CHANGE),
            observed=(),
        ),
    )

    report = Backtest().run(nothing)

    assert report.compared == 0
    assert report.mean_absolute_band_error is None
    assert report.signed_band_error is None
    assert report.exact_band_rate is None
    assert report.top_theme_hit_rate is None
    assert "not measurable" in report.summary()
    assert any("no calibration error could be measured" in c.lower() for c in report.caveats)


def test_an_exact_match_scores_zero_error():
    perfect = Foresight().run(Scenario(name="probe", change_type=ChangeType.OUTAGE))
    launch = HistoricLaunch(
        launch_id="SIM-LAUNCH-PERFECT",
        scenario=Scenario(name="probe", change_type=ChangeType.OUTAGE),
        observed=tuple(ObservedOutcome(p.theme, p.segment, p.band) for p in perfect.predictions),
    )

    report = Backtest().run((launch,))

    assert report.mean_absolute_band_error == Decimal("0.000")
    assert report.exact_band_rate == Decimal("1.000")
    assert report.status is CalibrationStatus.NOT_CALIBRATED, "still synthetic"


def test_under_prediction_is_called_out_as_the_dangerous_direction():
    pessimistic = Foresight().run(Scenario(name="probe", change_type=ChangeType.OUTAGE))
    worse_than_predicted = HistoricLaunch(
        launch_id="SIM-LAUNCH-WORSE",
        scenario=Scenario(name="probe", change_type=ChangeType.OUTAGE),
        observed=tuple(
            ObservedOutcome(p.theme, p.segment, VolumeBand.HIGH) for p in pessimistic.predictions
        ),
    )

    report = Backtest().run((worse_than_predicted,))

    assert report.signed_band_error is not None
    assert report.signed_band_error < 0
    assert any("dangerous direction" in c.lower() for c in report.caveats)


def test_over_prediction_is_not_called_dangerous():
    optimistic = Foresight().run(Scenario(name="probe", change_type=ChangeType.OUTAGE))
    quieter_than_predicted = HistoricLaunch(
        launch_id="SIM-LAUNCH-QUIET",
        scenario=Scenario(name="probe", change_type=ChangeType.OUTAGE),
        observed=tuple(
            ObservedOutcome(p.theme, p.segment, VolumeBand.LOW) for p in optimistic.predictions
        ),
    )

    report = Backtest().run((quieter_than_predicted,))

    assert report.signed_band_error is not None
    assert report.signed_band_error > 0
    assert not any("dangerous direction" in c.lower() for c in report.caveats)


def test_the_backtest_reads_no_individual_data():
    """Deck S8, carried through from the simulation to the backtest."""
    assert "no individual" in Backtest().run(DEMO_LAUNCHES).basis.lower()


def test_the_backtest_is_deterministic():
    first = Backtest().run(DEMO_LAUNCHES)
    second = Backtest().run(DEMO_LAUNCHES)

    assert first.mean_absolute_band_error == second.mean_absolute_band_error
    assert first.exact_band_rate == second.exact_band_rate
    assert first.caveats == second.caveats
    assert first.run_id != second.run_id, "each run is its own record"


def test_a_calibration_report_stays_advisory():
    assert any("advisory only" in c.lower() for c in Backtest().run(DEMO_LAUNCHES).caveats)


def test_a_foresight_report_is_decision_ready_only_with_a_calibrated_backtest():
    """Plan §3.4: the gate is wired to evidence, not hard-coded shut."""
    synthetic = Backtest().run(DEMO_LAUNCHES)
    calibrated = Backtest().run(tuple(real(launch) for launch in DEMO_LAUNCHES))
    scenario = Scenario(name="Price up", change_type=ChangeType.PRICE_INCREASE)

    assert not Foresight().run(scenario, calibration=synthetic).is_decision_ready
    assert Foresight().run(scenario, calibration=calibrated).is_decision_ready


def test_a_foresight_report_carries_the_calibration_error_it_rests_on():
    calibration = Backtest().run(DEMO_LAUNCHES)

    report = Foresight().run(
        Scenario(name="Price up", change_type=ChangeType.PRICE_INCREASE),
        calibration=calibration,
    )

    assert report.calibration is calibration
    assert any(str(calibration.mean_absolute_band_error) in c for c in report.caveats)
    assert any("certaint" in c.lower() for c in report.caveats)


def test_an_uncalibrated_foresight_report_says_it_is_not_launch_ready():
    report = Foresight().run(
        Scenario(name="Price up", change_type=ChangeType.PRICE_INCREASE),
        calibration=Backtest().run(DEMO_LAUNCHES),
    )

    assert not report.is_decision_ready
    assert any("not usable for a launch decision" in c.lower() for c in report.caveats)

"""Complaint Autopsy and Foresight tests (deck S11, plan §3.3-3.4, §12.9)."""

from __future__ import annotations

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
    autopsy = ComplaintAutopsy()
    report = autopsy.run(complaints("reload taken twice", "reload was taken twice"))

    confirmed = autopsy.confirm(report.clusters[0], reviewer="cx-eng-1", accept=True)

    assert confirmed.status is ClusterStatus.CONFIRMED
    assert "cx-eng-1" in confirmed.label


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

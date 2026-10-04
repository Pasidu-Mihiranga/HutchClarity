"""Closing the loop between foresight and autopsy (C7/F10).

Three things are being asserted, and the middle one is the load-bearing one:

1. **Foresight stays a leaf.** It does not import `autopsy`; the composition
   root supplies a driver for a port declared inside foresight. A test walks the
   module's imports and fails if that ever changes, because the alternative
   costs edits to the dependency map, plan 21 section 11.2, `docs/modules.md`,
   `ARCHITECTURE.md` and two `MODULE.md` files, and would stop foresight running
   as the batch job plan 21 moves it to.
2. **A cluster never becomes calibration evidence on its own.** A confirmed
   cluster is a real observation about complaints; turning it into "this theme
   was HIGH for this segment" is an act of interpretation. So a
   `cluster.updated` event produces an inert candidate, and a named person turns
   it into an outcome under their own name (ADR-0044).
3. **A predicted pair with no recorded outcome is `None`, not LOW.** The
   backtest already refuses to average absence in; the comparison says the same
   thing in the shape a person reads.
"""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from clarity.contracts.events import ClusterUpdatedV1, DomainEventType
from clarity.modules.foresight.catalogue import ChangeType, ForesightCatalogue
from clarity.modules.foresight.loop import (
    CANDIDATES,
    AutopsyLoop,
    ClusterRate,
)
from clarity.modules.foresight.records import Provenance
from clarity.modules.foresight.service import AlreadyConfirmed, ForesightService
from clarity.modules.foresight.simulation import Scenario, VolumeBand
from clarity.platform.config.resolver import PolicyResolver
from clarity.platform.messaging.envelope import Event
from clarity.platform.persistence import MemoryStore, MemoryUnitOfWork
from tests.conftest import POLICY_DIR

_AT = datetime(2027, 1, 1, tzinfo=UTC)
_EFFECTIVE = date(2027, 10, 1)


class Clusters:
    """A stand-in `ClusterRateSource`. The real one lives in the container."""

    def __init__(self, *rates: ClusterRate, fails: bool = False) -> None:
        self._rates = rates
        self._fails = fails

    def rates(self) -> tuple[ClusterRate, ...]:
        if self._fails:
            raise RuntimeError("the complaint side is unreachable")
        return self._rates


class World:
    """A service and a loop over one store."""

    def __init__(self, clusters: Clusters | None = None) -> None:
        self.store = MemoryStore()
        self.loop = AutopsyLoop(
            open_unit=lambda: MemoryUnitOfWork(self.store),
            clusters=clusters,
            clock=lambda: _AT,
        )
        self.service = ForesightService(
            open_unit=lambda: MemoryUnitOfWork(self.store),
            catalogue=ForesightCatalogue(PolicyResolver.from_directory(POLICY_DIR)),
            clock=lambda: _AT,
            loop=self.loop,
        )

    def cluster_updated(
        self,
        cluster_id: str = "CL-1",
        *,
        status: str = "confirmed",
        size: int = 12,
        event_id: str = "EVT-1",
    ) -> None:
        event = Event.of(
            ClusterUpdatedV1(
                cluster_id=cluster_id,
                status=status,
                size=size,
                suggested_rule_id="VAS_NO_CONSENT",
                reviewed_by="cx:ruwan",
            ),
            subject="autopsy",
        ).model_copy(update={"time": _AT, "id": event_id})
        self.loop.on_cluster_updated(event)

    def launch(self) -> tuple[str, str]:
        version = self.service.draft(
            Scenario(
                name="Retire the 10GB pack",
                change_type=ChangeType.PACK_RETIRED,
                effective_date=_EFFECTIVE,
            ),
            by="staff:pm",
        )
        run, _ = self.service.request_run(
            version.version_id, by="staff:pm", idempotency_key="run-key"
        )
        self.service.execute(run.run_id)
        recorded = self.service.record_launch(
            scenario_version_id=version.version_id,
            provenance=Provenance.SYNTHETIC,
            by="staff:cx",
        )
        return version.version_id, recorded.launch_id


# --------------------------------------------------------------------------- #
# Foresight stays a leaf
# --------------------------------------------------------------------------- #


def test_foresight_does_not_import_autopsy():
    """The reason the port is wired rather than imported.

    A synchronous L4-to-L4 dependency has to be declared in five documents and
    a test, and it would stop foresight running as a separate batch job.
    """
    module = Path(__file__).resolve().parents[2] / "src" / "clarity" / "modules" / "foresight"
    offending: list[str] = []
    for path in module.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and "modules.autopsy" in (node.module or ""):
                offending.append(f"{path.name}:{node.lineno}")
            if isinstance(node, ast.Import):
                offending.extend(
                    f"{path.name}:{node.lineno}"
                    for alias in node.names
                    if "modules.autopsy" in alias.name
                )
    assert offending == []


def test_the_cluster_rate_source_is_a_port_not_a_class_foresight_owns():
    """It is a Protocol, so the driver can live in the composition root."""
    from typing import Protocol

    from clarity.modules.foresight.loop import ClusterRateSource

    assert Protocol in ClusterRateSource.__mro__


def test_the_container_supplies_the_driver():
    from clarity.app.container import Clarity

    clarity = Clarity()

    assert clarity.foresight_loop is not None
    # It answers, which means the composition root joined the two modules.
    assert isinstance(clarity.foresight_loop._rates(), tuple)


# --------------------------------------------------------------------------- #
# A candidate is inert
# --------------------------------------------------------------------------- #


def test_a_cluster_update_makes_a_candidate_not_an_outcome():
    world = World()

    world.cluster_updated()

    candidates = world.loop.candidates()
    assert len(candidates) == 1
    assert not candidates[0].is_confirmed
    assert world.service.outcomes_of("anything") == []


def test_a_candidate_carries_no_theme_and_no_segment():
    """A cluster does not know which rehearsed theme it is. A person decides."""
    world = World()
    world.cluster_updated()

    candidate = world.loop.candidates()[0]

    assert not hasattr(candidate, "theme")
    assert not hasattr(candidate, "segment")
    assert not hasattr(candidate, "band")


def test_a_replayed_cluster_update_is_one_candidate():
    """I7: consumers are idempotent."""
    world = World()

    world.cluster_updated(event_id="EVT-1")
    world.cluster_updated(event_id="EVT-2")

    assert len(world.loop.candidates()) == 1


def test_a_candidate_never_reaches_the_backtest_on_its_own():
    """The lock that matters: noticing something is not evidence."""
    world = World()
    world.launch()
    world.cluster_updated()

    stored = world.service.backtest(by="staff:risk")

    assert stored.report.compared == 0, "an unconfirmed candidate scores nothing"


def test_confirming_records_an_outcome_under_the_persons_name():
    world = World()
    _, launch_id = world.launch()
    world.cluster_updated()

    outcome = world.service.confirm_candidate(
        cluster_id="CL-1",
        launch_id=launch_id,
        theme="pack sunset confusion",
        segment="students",
        band=VolumeBand.HIGH,
        by="cx:ruwan",
    )

    assert outcome.recorded_by == "cx:ruwan"
    assert outcome.theme == "pack sunset confusion"
    assert world.loop.candidate("CL-1").is_confirmed  # type: ignore[union-attr]
    assert world.loop.candidate("CL-1").confirmed_by == "cx:ruwan"  # type: ignore[union-attr]


def test_the_confirmed_outcome_is_what_the_backtest_reads():
    world = World()
    _, launch_id = world.launch()
    world.cluster_updated()
    world.service.confirm_candidate(
        cluster_id="CL-1",
        launch_id=launch_id,
        theme="pack sunset confusion",
        segment="students",
        band=VolumeBand.HIGH,
        by="cx:ruwan",
    )

    stored = world.service.backtest(by="staff:risk")

    assert stored.report.compared == 1


def test_confirming_twice_is_refused():
    """A second confirmation would write a second append-only outcome from one
    observation, which is how one cluster would count twice at the gate."""
    world = World()
    _, launch_id = world.launch()
    world.cluster_updated()
    world.service.confirm_candidate(
        cluster_id="CL-1",
        launch_id=launch_id,
        theme="pack sunset confusion",
        segment="students",
        band=VolumeBand.HIGH,
        by="cx:ruwan",
    )

    with pytest.raises(AlreadyConfirmed):
        world.service.confirm_candidate(
            cluster_id="CL-1",
            launch_id=launch_id,
            theme="pack sunset confusion",
            segment="parents",
            band=VolumeBand.LOW,
            by="cx:ruwan",
        )


def test_confirming_a_candidate_nobody_noticed_is_refused():
    world = World()
    _, launch_id = world.launch()

    with pytest.raises(KeyError):
        world.service.confirm_candidate(
            cluster_id="CL-nothing",
            launch_id=launch_id,
            theme="t",
            segment="s",
            band=VolumeBand.LOW,
            by="cx:ruwan",
        )


def test_candidates_are_mutable_because_confirming_is_their_one_transition():
    """Deliberately not append-only. The evidence a confirmation produces is,
    and spending `as_custodian` on a product note would make that span mean
    nothing."""
    from clarity.platform.persistence.schemas import is_append_only

    assert not is_append_only(CANDIDATES)
    assert is_append_only("foresight.outcomes")


# --------------------------------------------------------------------------- #
# Predicted versus actual
# --------------------------------------------------------------------------- #


def test_a_comparison_puts_the_prediction_beside_what_was_recorded():
    world = World()
    _, launch_id = world.launch()
    world.service.record_outcome(
        launch_id=launch_id,
        theme="pack sunset confusion",
        segment="students",
        band=VolumeBand.HIGH,
        by="cx:ruwan",
    )

    comparison = world.service.comparison(launch_id)

    assert comparison is not None
    assert comparison.compared == 1
    matched = next(
        pair
        for pair in comparison.pairs
        if (pair.theme, pair.segment) == ("pack sunset confusion", "students")
    )
    assert matched.observed is VolumeBand.HIGH


def test_a_predicted_pair_with_no_record_is_none_not_low():
    """Absence of a record is absence of a record."""
    world = World()
    _, launch_id = world.launch()

    comparison = world.service.comparison(launch_id)

    assert comparison is not None
    assert comparison.pairs
    assert all(pair.observed is None for pair in comparison.pairs)
    assert all(pair.agrees is None for pair in comparison.pairs)


def test_an_agreement_rate_over_nothing_is_none():
    world = World()
    _, launch_id = world.launch()

    comparison = world.service.comparison(launch_id)

    assert comparison is not None
    assert comparison.agreement_rate is None


def test_an_observed_theme_the_rehearsal_never_predicted_is_reported():
    world = World()
    _, launch_id = world.launch()
    world.service.record_outcome(
        launch_id=launch_id,
        theme="roaming bill shock",
        segment="tourists",
        band=VolumeBand.HIGH,
        by="cx:ruwan",
    )

    comparison = world.service.comparison(launch_id)

    assert comparison is not None
    assert ("roaming bill shock", "tourists") in comparison.unpredicted


def test_the_agreement_rate_is_exact():
    world = World()
    _, launch_id = world.launch()
    for segment, band in (("students", VolumeBand.HIGH), ("parents", VolumeBand.LOW)):
        world.service.record_outcome(
            launch_id=launch_id,
            theme="pack sunset confusion",
            segment=segment,
            band=band,
            by="cx:ruwan",
        )

    comparison = world.service.comparison(launch_id)

    assert comparison is not None
    assert comparison.compared == 2
    assert isinstance(comparison.agreement_rate, Decimal)


def test_a_comparison_for_a_launch_nobody_recorded_is_none():
    assert World().service.comparison("LNC-nothing") is None


def test_the_comparison_says_a_candidate_is_not_an_outcome():
    world = World()
    _, launch_id = world.launch()

    comparison = world.service.comparison(launch_id)

    assert comparison is not None
    assert any("not an outcome" in c for c in comparison.caveats)
    assert any("not a LOW observation" in c for c in comparison.caveats)


# --------------------------------------------------------------------------- #
# Cluster rates are context, not score
# --------------------------------------------------------------------------- #


def test_cluster_rates_appear_as_context():
    world = World(Clusters(ClusterRate(cluster_id="CL-1", size=40, status="confirmed")))
    _, launch_id = world.launch()

    comparison = world.service.comparison(launch_id)

    assert comparison is not None
    assert comparison.cluster_rates[0].size == 40


def test_cluster_rates_carry_no_label():
    """A label is derived from what customers wrote, so it stays in autopsy."""
    rate = ClusterRate(cluster_id="CL-1", size=40, status="confirmed")

    assert not hasattr(rate, "label")
    assert not hasattr(rate, "keywords")
    assert not hasattr(rate, "members")


def test_cluster_rates_do_not_change_the_comparison():
    """They are not keyed by theme or segment, so they cannot be scored."""
    with_rates = World(Clusters(ClusterRate(cluster_id="CL-1", size=400, status="confirmed")))
    without = World()
    first = with_rates.launch()[1]
    second = without.launch()[1]

    a = with_rates.service.comparison(first)
    b = without.service.comparison(second)

    assert a is not None and b is not None
    assert [(p.theme, p.segment, p.predicted) for p in a.pairs] == [
        (p.theme, p.segment, p.predicted) for p in b.pairs
    ]


def test_an_unreachable_complaint_side_leaves_the_context_empty():
    """Losing the whole screen because a side panel could not load would be the
    wrong trade: the predicted-versus-actual part stands on its own."""
    world = World(Clusters(fails=True))
    _, launch_id = world.launch()

    comparison = world.service.comparison(launch_id)

    assert comparison is not None
    assert comparison.cluster_rates == ()
    assert comparison.pairs, "the comparison itself still works"


# --------------------------------------------------------------------------- #
# The event
# --------------------------------------------------------------------------- #


def test_cluster_updated_carries_codes_and_counts_only():
    fields = set(ClusterUpdatedV1.model_fields)

    assert "label" not in fields
    assert "keywords" not in fields
    assert "members" not in fields
    assert fields == {"cluster_id", "status", "size", "suggested_rule_id", "reviewed_by"}


def test_reviewing_a_cluster_publishes_the_event():
    """I7: the verdict and the event in one transaction."""
    from clarity.app.container import Clarity
    from clarity.platform.messaging.outbox import outbox_in

    clarity = Clarity()
    for index in range(4):
        clarity.autopsy.accept(
            f"C{index}", channel="app", text=f"my data stopped at the cap again number {index}"
        )
    clarity.autopsy.rerun()
    clusters = clarity.autopsy.clusters()
    assert clusters, "the pipeline should have drawn at least one cluster"
    cluster = clusters[0].cluster

    clarity.autopsy.review(cluster.cluster_id, reviewer="cx:ruwan", accept=True)

    with clarity.open_unit() as unit:
        published = [
            row.event
            for row in outbox_in(unit).all_rows()
            if row.event.type is DomainEventType.CLUSTER_UPDATED
        ]
    assert published
    assert published[-1].payload().cluster_id == cluster.cluster_id  # type: ignore[union-attr]

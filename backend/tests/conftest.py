"""Shared fixtures and builders for the test suite."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from clarity.contracts.decision import BudgetState
from clarity.contracts.timeline import EventType, EvidenceSnapshot, SourceStatus, TimelineEvent
from clarity.integration.drivers.mock.world import (
    DEMO_NOW,
    SyntheticWorld,
    build_demo_world,
    ref_for,
)
from clarity.integration.registry import AdapterRegistry
from clarity.kernel.common import Completeness, EventSource, money
from clarity.modules.decision.policy import DecisionPolicy
from clarity.modules.detection.engine import RuleEngine
from clarity.modules.detection.pack import RulePack, load_packs
from clarity.modules.timeline.builder import TimelineBuilder, TimelineRequest
from clarity.platform.config.resolver import PolicyResolver

PACKS_DIR = Path(__file__).resolve().parents[2] / "rules" / "packs"
POLICY_DIR = Path(__file__).resolve().parents[2] / "config" / "policy"


@pytest.fixture(scope="session")
def packs() -> list[RulePack]:
    return load_packs(PACKS_DIR)


@pytest.fixture
def engine(packs: list[RulePack]) -> RuleEngine:
    return RuleEngine(packs)


@pytest.fixture
def policy() -> DecisionPolicy:
    return DecisionPolicy()


@pytest.fixture
def world() -> SyntheticWorld:
    return build_demo_world()


@pytest.fixture
def registry(world: SyntheticWorld) -> AdapterRegistry:
    return AdapterRegistry(world=world)


@pytest.fixture
def builder(registry: AdapterRegistry) -> TimelineBuilder:
    return TimelineBuilder(registry.read_ports())


@pytest.fixture(scope="session")
def policies() -> PolicyResolver:
    """The real policy artefacts, so tests exercise the caps that ship."""
    return PolicyResolver.from_directory(POLICY_DIR)


@pytest.fixture
def ample_budget() -> BudgetState:
    return BudgetState(global_remaining_lkr=money("1000000"))


def snapshot_for(builder: TimelineBuilder, msisdn: str) -> EvidenceSnapshot:
    """Build a snapshot for one of the demo subscribers."""
    return builder.build(TimelineRequest.for_case("CASE-T", ref_for(msisdn), now=DEMO_NOW))


class SnapshotBuilder:
    """Fluent builder for hand-made evidence, used by the golden tests.

    Golden tests need to state precisely which facts exist, so they construct
    snapshots directly rather than going through the synthetic world.
    """

    def __init__(self, *, now: datetime = DEMO_NOW) -> None:
        self.now = now
        self._events: list[TimelineEvent] = []
        self._sources: dict[EventSource, Completeness] = {}
        self._seq = 0

    def at(self, **delta: float) -> datetime:
        return self.now - timedelta(**delta)  # type: ignore[arg-type]

    def event(
        self,
        source: EventSource,
        event_type: EventType,
        occurred_at: datetime,
        *,
        amount: Any | None = None,
        **attributes: Any,
    ) -> SnapshotBuilder:
        self._seq += 1
        self._events.append(
            TimelineEvent(
                event_id=f"ev-{self._seq:04d}",
                source=source,
                event_type=event_type,
                source_event_id=f"src-{self._seq:04d}",
                occurred_at=occurred_at,
                amount_lkr=amount,
                attributes=attributes,
            )
        )
        self._sources.setdefault(source, Completeness.COMPLETE)
        return self

    def source(self, source: EventSource, completeness: Completeness) -> SnapshotBuilder:
        """Override a source's completeness, e.g. to make a rule indeterminate."""
        self._sources[source] = completeness
        return self

    def build(self) -> EvidenceSnapshot:
        # A source that did not answer contributes no events. Keeping events
        # from a MISSING source would assert both "we could not look" and
        # "here is what we found", which is the contradiction the snapshot
        # model rejects.
        silent = {src for src, c in self._sources.items() if c is Completeness.MISSING}
        events = sorted(
            (e for e in self._events if e.source not in silent),
            key=lambda e: (e.occurred_at, e.event_id),
        )
        # Any source not touched is reported COMPLETE with zero events, which
        # is the honest statement "we looked and found nothing".
        statuses = [
            SourceStatus(
                source=src,
                completeness=self._sources.get(src, Completeness.COMPLETE),
                event_count=sum(1 for e in events if e.source is src),
            )
            for src in EventSource
        ]
        return EvidenceSnapshot(
            case_id="CASE-T",
            built_at=self.now,
            window_from=self.now - timedelta(days=90),
            window_to=self.now,
            events=events,
            sources=statuses,
        )


@pytest.fixture
def snap() -> SnapshotBuilder:
    return SnapshotBuilder()


@pytest.fixture
def clarity_container():
    """The whole application, wired exactly as the API wires it."""
    from clarity.app.container import Clarity

    return Clarity(world=build_demo_world())

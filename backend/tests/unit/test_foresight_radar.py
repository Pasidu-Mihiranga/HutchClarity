"""The early-warning radar, and the two events foresight publishes (C5/F07, F08).

Plan 18 section 159 promised `forecast.ready` and `spike.detected`; plan 21
section 11.3, which is the operative catalogue, omitted foresight entirely.
Both rows exist now and `tests/contract/test_event_contracts.py` fails if the
table and the code disagree.

The tests worth reading first are the ones about what a spike is **not**. A
count that reaches three times a trailing average of 0.3 is a tripling, and it
is also two complaints. A first busy hour with no history behind it is a
statement about the radar's age, not about traffic. Both would be alerts nobody
should act on, and both are refused here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from clarity.contracts.events import (
    ComplaintCreatedV1,
    DomainEventType,
    EventPayload,
    ForecastReadyV1,
    SpikeDetectedV1,
)
from clarity.kernel.common import Channel, Language
from clarity.modules.foresight.catalogue import ChangeType, ForesightCatalogue
from clarity.modules.foresight.radar import OBSERVATIONS, ComplaintRadar
from clarity.modules.foresight.repository import StoredForesightRepository
from clarity.modules.foresight.service import ForesightService
from clarity.modules.foresight.simulation import Scenario
from clarity.platform.config.artefacts import PolicyKey, PolicyValue, Tag
from clarity.platform.config.resolver import PolicyResolver
from clarity.platform.messaging.envelope import Event
from clarity.platform.messaging.outbox import outbox_in
from clarity.platform.persistence import MemoryStore, MemoryUnitOfWork
from tests.conftest import POLICY_DIR

_BASE = datetime(2027, 1, 1, tzinfo=UTC)
_HOUR = timedelta(hours=1)


def catalogue(**overrides: str) -> ForesightCatalogue:
    resolver = PolicyResolver.from_directory(POLICY_DIR)
    for key, value in overrides.items():
        resolver.add(
            PolicyKey(
                key=key.replace("__", "."),
                kind="number",
                owner_role="product",
                tags={Tag.OPERATIONAL},
                values=[PolicyValue(value=value, version=99)],
            )
        )
    return ForesightCatalogue(resolver)


class Radar:
    """A radar over one in-memory store, with a counter for event ids."""

    def __init__(self, cat: ForesightCatalogue | None = None) -> None:
        self.store = MemoryStore()
        self.catalogue = cat or catalogue()
        self.radar = ComplaintRadar(
            open_unit=lambda: MemoryUnitOfWork(self.store),
            catalogue=self.catalogue,
            clock=lambda: _BASE,
        )
        self._next = 0

    def complaint(
        self, at: datetime, *, channel: Channel = Channel.APP, event_id: str | None = None
    ) -> str:
        self._next += 1
        identifier = event_id or f"EVT-{self._next}"
        event = Event.of(
            ComplaintCreatedV1(
                complaint_id=f"C{self._next}", channel=channel, language=Language.EN
            ),
            subject="subscriber",
        ).model_copy(update={"time": at, "id": identifier})
        self.radar.on_complaint_created(event)
        return identifier

    def spikes(self) -> list:
        with MemoryUnitOfWork(self.store) as unit:
            return StoredForesightRepository.of(unit).all_spikes()

    def observations(self) -> list:
        with MemoryUnitOfWork(self.store) as unit:
            return unit.repository(OBSERVATIONS).values()

    def published(self) -> list[Event]:
        with MemoryUnitOfWork(self.store) as unit:
            return [row.event for row in outbox_in(unit).all_rows()]

    def quiet_history(self, *, per_window: int = 1, windows: int = 6) -> None:
        """One complaint an hour for six hours: a steady, boring baseline."""
        for window in range(windows):
            for item in range(per_window):
                self.complaint(_BASE + window * _HOUR + timedelta(minutes=item))

    def burst(self, count: int, *, window: int = 6) -> None:
        for item in range(count):
            self.complaint(_BASE + window * _HOUR + timedelta(minutes=item))


# --------------------------------------------------------------------------- #
# What a spike is
# --------------------------------------------------------------------------- #


def test_a_jump_over_the_threshold_raises_one_spike():
    radar = Radar()
    radar.quiet_history()

    radar.burst(6)

    spikes = radar.spikes()
    assert len(spikes) == 1
    assert spikes[0].observed >= 5
    assert spikes[0].baseline == Decimal("1.000")


def test_one_window_raises_one_spike_however_many_complaints_follow():
    """I7: the spike id is derived from scope and window, so a later complaint
    in the same window finds the spike already there."""
    radar = Radar()
    radar.quiet_history()

    radar.burst(30)

    assert len(radar.spikes()) == 1


def test_the_spike_id_is_derived_so_two_replicas_agree():
    """A trailing window would give each replica its own boundaries and its own
    spike. A fixed grid from the epoch gives both the same id."""
    first, second = Radar(), Radar()
    for radar in (first, second):
        radar.quiet_history()
        radar.burst(6)

    assert first.spikes()[0].spike_id == second.spikes()[0].spike_id


# --------------------------------------------------------------------------- #
# What a spike is not
# --------------------------------------------------------------------------- #


def test_a_quiet_channel_tripling_from_one_to_three_is_not_a_spike():
    """True, and useless. The floor is what stops it being an alert."""
    radar = Radar()
    radar.quiet_history(per_window=1)

    radar.burst(3)

    assert radar.spikes() == []


def test_a_busy_window_under_the_threshold_is_not_a_spike():
    radar = Radar()
    radar.quiet_history(per_window=4)

    radar.burst(6)  # over the floor, under 4 * 3

    assert radar.spikes() == []


def test_the_first_busy_window_with_no_history_is_not_a_spike():
    """It is a statement about the radar's age, not about traffic."""
    radar = Radar()

    radar.burst(50, window=0)

    assert radar.spikes() == []


def test_partial_history_is_still_not_enough():
    radar = Radar()
    radar.quiet_history(windows=3)

    radar.burst(20, window=3)

    assert radar.spikes() == []


def test_an_empty_baseline_window_counts_towards_the_average():
    """Dropping the quiet hours would make the baseline look like the peak."""
    radar = Radar()
    # One complaint in the first window only, then five empty windows.
    radar.complaint(_BASE)
    for _ in range(6):
        radar.complaint(_BASE - _HOUR)  # outside the baseline range, keeps history old

    radar.burst(6)

    spikes = radar.spikes()
    assert spikes
    # 1 complaint over 6 windows, not 1 over 1.
    assert spikes[0].baseline < Decimal("1")


# --------------------------------------------------------------------------- #
# Idempotency and scope
# --------------------------------------------------------------------------- #


def test_a_replayed_event_is_counted_once():
    """I7: consumers are idempotent, and a replay must not inflate a window."""
    radar = Radar()

    radar.complaint(_BASE, event_id="EVT-same")
    radar.complaint(_BASE, event_id="EVT-same")

    assert len(radar.observations()) == 1


def test_a_replay_cannot_raise_a_spike_that_did_not_happen():
    radar = Radar()
    radar.quiet_history()
    for item in range(4):
        radar.complaint(_BASE + 6 * _HOUR + timedelta(minutes=item), event_id=f"burst-{item}")

    for item in range(4):
        radar.complaint(_BASE + 6 * _HOUR + timedelta(minutes=item), event_id=f"burst-{item}")

    assert radar.spikes() == [], "replaying four complaints is not eight complaints"


def test_channels_are_counted_separately():
    radar = Radar()
    radar.quiet_history()
    for item in range(20):
        radar.complaint(_BASE + 6 * _HOUR + timedelta(minutes=item), channel=Channel.WHATSAPP)

    assert radar.spikes() == [], "a different channel has its own history"


def test_a_spike_names_a_channel_code_not_a_channel_name():
    radar = Radar()
    radar.quiet_history()
    radar.burst(6)

    spike = radar.spikes()[0]

    assert spike.scope.value == "channel"
    assert spike.scope_ref == Channel.APP.value
    assert not hasattr(spike, "channel_name")


def test_the_radar_keeps_no_complaint_text():
    """It counts. `autopsy` is what reads what people actually said."""
    radar = Radar()
    radar.complaint(_BASE)

    observation = radar.observations()[0]

    assert set(vars(observation)) == {"event_id", "channel", "occurred_at"}


def test_a_spike_says_it_is_not_a_cause():
    radar = Radar()
    radar.quiet_history()
    radar.burst(6)

    spike = radar.spikes()[0]

    assert any("not a cause" in c for c in spike.caveats)
    assert any("advisory only" in c.lower() for c in spike.caveats)
    assert "no individual customer record" in spike.basis


# --------------------------------------------------------------------------- #
# Policy drives it (I10)
# --------------------------------------------------------------------------- #


def test_the_threshold_comes_from_policy():
    strict = Radar(catalogue(foresight__radar__threshold_multiple="50"))
    strict.quiet_history()
    strict.burst(6)

    lenient = Radar(catalogue(foresight__radar__threshold_multiple="2"))
    lenient.quiet_history()
    lenient.burst(6)

    assert strict.spikes() == []
    assert lenient.spikes()


def test_the_floor_comes_from_policy():
    radar = Radar(catalogue(foresight__radar__min_observations="100"))
    radar.quiet_history()

    radar.burst(20)

    assert radar.spikes() == []


def test_the_window_length_comes_from_policy():
    """A different window puts the same complaints in different buckets."""
    radar = Radar(catalogue(foresight__radar__window_minutes="5"))
    radar.quiet_history()

    radar.burst(6)

    spike = radar.spikes()[0]
    assert spike.window_end - spike.window_start == timedelta(minutes=5)


def test_a_spike_against_a_zero_baseline_says_it_rests_on_the_floor_alone():
    """ "This channel was quiet and now it is not" is the signal a radar exists
    for, so it is raised. But there is no multiple of normal to report, and the
    spike says so rather than leaving a reader to infer one."""
    radar = Radar(catalogue(foresight__radar__window_minutes="5"))
    radar.quiet_history()

    radar.burst(6)

    spike = radar.spikes()[0]
    assert spike.baseline == Decimal("0.000")
    assert spike.ratio is None
    assert any("rests on the floor alone" in c for c in spike.caveats)


# --------------------------------------------------------------------------- #
# The events
# --------------------------------------------------------------------------- #


def test_a_spike_is_published_through_the_outbox():
    """I7: the state change and the event in the same transaction."""
    radar = Radar()
    radar.quiet_history()
    radar.burst(6)

    published = [e for e in radar.published() if e.type is DomainEventType.SPIKE_DETECTED]

    assert len(published) == 1
    payload = published[0].payload()
    assert isinstance(payload, SpikeDetectedV1)
    assert payload.spike_id == radar.spikes()[0].spike_id
    assert payload.scope_ref == "app"


def test_no_spike_means_no_event():
    radar = Radar()
    radar.quiet_history()

    assert [e for e in radar.published() if e.type is DomainEventType.SPIKE_DETECTED] == []


def test_a_finished_run_publishes_forecast_ready():
    store = MemoryStore()
    service = ForesightService(
        open_unit=lambda: MemoryUnitOfWork(store),
        catalogue=catalogue(),
        clock=lambda: _BASE,
    )
    version = service.draft(
        Scenario(
            name="Retire the 10GB pack",
            change_type=ChangeType.PACK_RETIRED,
            effective_date=date(2027, 10, 1),
        ),
        by="staff:pm",
    )
    run, _ = service.request_run(version.version_id, by="staff:pm", idempotency_key="k")
    service.execute(run.run_id)

    with MemoryUnitOfWork(store) as unit:
        published = [
            row.event
            for row in outbox_in(unit).all_rows()
            if row.event.type is DomainEventType.FORECAST_READY
        ]

    assert len(published) == 1
    payload = published[0].payload()
    assert isinstance(payload, ForecastReadyV1)
    assert payload.run_id == run.run_id
    assert payload.scenario_id == version.scenario_id
    assert payload.change_type == "pack_retired"
    assert payload.predicted_pairs > 0
    assert payload.backtested is False


def test_forecast_ready_carries_codes_and_counts_only():
    """A consumer that wants the scenario's name asks `/v1/foresight` for it,
    where the permission check is."""
    fields = set(ForecastReadyV1.model_fields)

    assert "scenario_name" not in fields
    assert "name" not in fields
    assert "predictions" not in fields
    assert "themes" not in fields


@pytest.mark.parametrize("field", ["scenario_name", "migration_card_count", "customer_msisdn"])
def test_a_personal_or_naming_field_cannot_be_added_to_a_foresight_event(field: str):
    """`_FORBIDDEN_SEGMENTS` contains `name` and `card`, so these are
    uninstantiable rather than merely discouraged. The plan flagged exactly
    these two as the trap."""
    with pytest.raises(TypeError, match="personal"):

        class _Leaky(EventPayload):  # pragma: no cover - the definition must fail
            event_type = DomainEventType.FORECAST_READY
            __annotations__ = {field: str}


def test_the_spike_baseline_is_an_exact_decimal():
    """It is divided into `observed` to make a ratio a person reads."""
    radar = Radar()
    radar.quiet_history()
    radar.burst(6)

    spike = radar.spikes()[0]

    assert isinstance(spike.baseline, Decimal)
    assert isinstance(spike.ratio, Decimal)

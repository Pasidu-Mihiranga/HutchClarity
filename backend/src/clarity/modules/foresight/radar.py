"""The early-warning radar: more complaints than usual, said out loud (C5/F08).

Foresight rehearses a change *before* it ships. The radar is the other half:
noticing, while something is happening, that one channel is producing more
complaints than it usually does. Plan 18 section 159 puts both in this module.

**Channel scope only, and that is a consequence of the event rather than a
preference.** `complaint.created` carries a complaint id, a channel, a language
and an optional case id. It carries no cluster, so a cluster-scoped spike would
need a field that does not exist, and inferring one in the consumer would be
guessing at which complaints belong together. When the clustering side
publishes something that carries a cluster, this gains a scope rather than
changing shape.

**What a spike is, and what it is not.** A window whose count reaches a multiple
of the trailing average, with a floor under it. It is not a cause, it is not a
forecast, and nothing acts on it: it lands in a table and on an API a person
reads. The floor matters more than it looks: without it a quiet channel going
from one complaint to three is a tripling, which is true and useless.

**Idempotency (I7).** Every observation is keyed by the event id, so a replayed
`complaint.created` is counted once. Every spike is keyed by scope and window,
so one window raises one spike however many complaints arrive after it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from clarity.contracts.events import ComplaintCreatedV1, SpikeDetectedV1
from clarity.modules.foresight.catalogue import ForesightCatalogue, RadarSettings
from clarity.modules.foresight.records import DetectedSpike, SpikeScope
from clarity.modules.foresight.repository import StoredForesightRepository
from clarity.platform.messaging.envelope import Event, EventType
from clarity.platform.messaging.outbox import outbox_in
from clarity.platform.persistence import Repository, UnitOfWorkFactory

#: One complaint, counted. Append-only: these are observations about the past,
#: and the only way to make a spike disappear would be to delete some.
OBSERVATIONS = "foresight.observations"

_BASIS = (
    "Complaints counted per channel in a fixed window, compared against the "
    "trailing average of the preceding windows. Counts only: no complaint text "
    "and no individual customer record was read."
)
_CAVEATS = (
    "A spike is a count, not a cause. It says something changed, not what.",
    "Advisory only: nothing acts on a spike, and it can never change a customer.",
    "The window, the threshold and the floor are ASSUMPTIONS and have not been "
    "tuned against real traffic.",
)


@dataclass(frozen=True)
class ComplaintObservation:
    """One complaint, reduced to the two things a count needs.

    Keyed by the event id so a replay cannot inflate a window. The channel is a
    code, and nothing else about the complaint is kept: the radar counts, and
    `autopsy` is what reads what people actually said.
    """

    event_id: str
    channel: str
    occurred_at: datetime


class ComplaintRadar:
    """Counts `complaint.created` per channel and raises a spike when one jumps."""

    def __init__(
        self,
        *,
        open_unit: UnitOfWorkFactory,
        catalogue: ForesightCatalogue,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._open_unit = open_unit
        self._catalogue = catalogue
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    def on_complaint_created(self, event: Event) -> None:
        payload = event.payload()
        if not isinstance(payload, ComplaintCreatedV1):
            return

        settings = self._catalogue.radar(self._clock())
        at = event.time
        with self._open_unit() as unit:
            observations: Repository[str, ComplaintObservation] = unit.repository(OBSERVATIONS)
            if observations.get(event.id) is not None:
                # Already counted. A replayed event must not inflate a window
                # (I7), and returning here rather than re-evaluating also means
                # a replay cannot raise a spike that did not happen.
                return
            observations.put(
                event.id,
                ComplaintObservation(
                    event_id=event.id,
                    channel=payload.channel.value,
                    occurred_at=at,
                ),
            )

            repository = StoredForesightRepository.of(unit)
            spike = self._spike_for(
                scope_ref=payload.channel.value,
                at=at,
                counts=[
                    item for item in observations.values() if item.channel == payload.channel.value
                ],
                settings=settings,
            )
            if spike is not None and repository.spike(spike.spike_id) is None:
                repository.save_spike(spike)
                outbox_in(unit).append(
                    event.caused(
                        SpikeDetectedV1(
                            spike_id=spike.spike_id,
                            scope=spike.scope.value,
                            scope_ref=spike.scope_ref,
                            window_start=spike.window_start,
                            window_end=spike.window_end,
                            observed=spike.observed,
                            baseline=spike.baseline,
                            threshold_multiple=settings.threshold_multiple,
                        )
                    ).model_copy(update={"time": at})
                )
            unit.commit()

    # ----------------------------------------------------------------- #

    def _spike_for(
        self,
        *,
        scope_ref: str,
        at: datetime,
        counts: list[ComplaintObservation],
        settings: RadarSettings,
    ) -> DetectedSpike | None:
        start = _window_start(at, settings.window)
        end = start + settings.window
        observed = sum(1 for item in counts if start <= item.occurred_at < end)
        if observed < settings.min_observations:
            return None

        baseline = self._baseline(counts, start, settings)
        if baseline is None:
            # Not enough history to say what usual looks like. Reporting a spike
            # here would mean "the first busy hour we ever saw is a spike",
            # which is a statement about the radar's age, not about traffic.
            return None
        if baseline > 0 and Decimal(observed) < baseline * settings.threshold_multiple:
            return None

        caveats: tuple[str, ...] = _CAVEATS
        if baseline <= 0:
            # Permitted, because "this channel was quiet and now it is not" is
            # the signal a radar exists for. But there is no multiple to report:
            # `DetectedSpike.ratio` answers `None` for a zero baseline, and the
            # caveat says why rather than leaving a reader to wonder.
            caveats = (
                *caveats,
                "The baseline for this window was zero, so this spike rests on the "
                "floor alone and no multiple of normal could be computed.",
            )

        return DetectedSpike(
            # Derived from the scope and the window, so one window raises one
            # spike however many complaints arrive after the threshold is
            # crossed, on any replica.
            spike_id=f"SPK-{scope_ref}-{int(start.timestamp())}",
            scope=SpikeScope.CHANNEL,
            scope_ref=scope_ref,
            window_start=start,
            window_end=end,
            observed=observed,
            baseline=baseline,
            detected_at=at,
            basis=_BASIS,
            caveats=caveats,
        )

    def _baseline(
        self, counts: list[ComplaintObservation], start: datetime, settings: RadarSettings
    ) -> Decimal | None:
        """The trailing average, or ``None`` when there is not enough history.

        Every preceding window counts, including the empty ones: dropping them
        would average over only the busy hours and make the baseline look like
        the peak rather than the usual.
        """
        earliest = min((item.occurred_at for item in counts), default=None)
        if earliest is None:
            return None
        covered = start - settings.window * settings.baseline_windows
        if earliest > covered:
            return None

        totals = []
        for index in range(1, settings.baseline_windows + 1):
            window_start = start - settings.window * index
            window_end = window_start + settings.window
            totals.append(
                sum(1 for item in counts if window_start <= item.occurred_at < window_end)
            )
        return (Decimal(sum(totals)) / Decimal(len(totals))).quantize(Decimal("0.001"))


def _window_start(at: datetime, window: timedelta) -> datetime:
    """Snap to a fixed grid from the epoch.

    Fixed rather than trailing, so two replicas seeing the same complaint agree
    on which window it falls in and derive the same spike id. A trailing window
    would give each replica its own boundaries and its own spike.
    """
    seconds = int(window.total_seconds())
    stamp = int(at.timestamp())
    return datetime.fromtimestamp(stamp - (stamp % seconds), tz=UTC)


CONSUMED_EVENTS = (EventType.COMPLAINT_CREATED,)


__all__ = [
    "CONSUMED_EVENTS",
    "OBSERVATIONS",
    "ComplaintObservation",
    "ComplaintRadar",
]

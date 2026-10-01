"""Timeline Builder: eight log sources, one case file (deck S7, S12).

Responsibilities:

- read every source over a bounded window;
- normalise into :class:`TimelineEvent`;
- record how completely each source answered;
- freeze the result into an :class:`EvidenceSnapshot` whose hash makes the
  later decision reproducible.

A source that fails is recorded as ``MISSING`` with the reason. It is never
treated as "nothing happened", because those are different facts: one means the
customer has no such events, the other means we could not look.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from clarity.integrations.base import AdapterError, ReadPort, SourceRead
from clarity.schemas.common import Completeness, EventSource, utc_now
from clarity.schemas.timeline import EvidenceSnapshot, SourceStatus

#: Default lookback. 90 days covers a monthly pack cycle plus disputes.
#: ASSUMPTION — the real window depends on HUTCH retention (plan §9.3).
DEFAULT_WINDOW_DAYS = 90


@dataclass(frozen=True)
class TimelineRequest:
    case_id: str
    subscriber_ref: str
    window_from: datetime
    window_to: datetime

    @classmethod
    def for_case(
        cls,
        case_id: str,
        subscriber_ref: str,
        *,
        now: datetime | None = None,
        window_days: int = DEFAULT_WINDOW_DAYS,
    ) -> TimelineRequest:
        end = now or utc_now()
        return cls(
            case_id=case_id,
            subscriber_ref=subscriber_ref,
            window_from=end - timedelta(days=window_days),
            window_to=end,
        )


class TimelineBuilder:
    """Builds evidence snapshots from the configured read ports."""

    def __init__(self, read_ports: dict[EventSource, ReadPort]) -> None:
        self._ports = read_ports

    def build(self, request: TimelineRequest) -> EvidenceSnapshot:
        """Read all sources and freeze a snapshot.

        Reads are independent, so production runs them in parallel with
        per-source timeouts (plan §3.1). The prototype runs them sequentially:
        the mock world is in-memory, and sequential execution keeps the demo
        deterministic.
        """
        reads: list[SourceRead] = []
        for source, port in self._ports.items():
            reads.append(self._read_one(source, port, request))

        events = sorted(
            (event for read in reads for event in read.events),
            key=lambda e: (e.occurred_at, e.event_id),
        )
        statuses: list[SourceStatus] = [read.to_status() for read in reads]
        statuses.sort(key=lambda s: s.source.value)

        return EvidenceSnapshot(
            case_id=request.case_id,
            built_at=utc_now(),
            window_from=request.window_from,
            window_to=request.window_to,
            events=events,
            sources=statuses,
        )

    def _read_one(
        self, source: EventSource, port: ReadPort, request: TimelineRequest
    ) -> SourceRead:
        try:
            return port.read(request.subscriber_ref, request.window_from, request.window_to)
        except AdapterError as error:
            return SourceRead(
                source=source,
                events=[],
                completeness=Completeness.MISSING,
                note=f"{error.code}: source could not be read",
                queried_window_days=(request.window_to - request.window_from).days,
            )

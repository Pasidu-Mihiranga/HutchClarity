"""Read models folded from the event log (I01, #30; plan 02 section 3.5, plan 10).

The dashboards read live objects today, which means they read whatever happens
to be in this process: a restart loses the numbers, a second replica disagrees
with the first, and nobody can ask what the figures were last Tuesday. A
projection is the fix, and the property that makes it trustworthy is that
replaying the log rebuilds exactly the same numbers.

Three rules get that property, and each one is a thing projections usually get
wrong.

**1. Applying an event twice counts it once.** Consumers are at-least-once
(I7), so a redelivery is normal rather than exceptional. Every event id the
fold has seen is kept, and a repeat is a no-op. Without this the first
redelivery silently inflates a dashboard and nothing ever says so.

**2. Joins happen at read time, not at apply time.** "Refunds by rule" needs a
case's cause and its refunds, and those arrive in separate events in no
guaranteed order across partitions. A fold that joined on arrival would drop a
refund whose `cause.detected` had not landed yet, and the number would depend
on delivery order. So the fold keeps per-case facts and the view joins them.

**3. Anything "latest" is decided by a number in the event, never by arrival
order.** The last state a conversation reached is the turn with the highest
`turn_no`, not the turn that happened to arrive last. Otherwise a replay in a
different order gives a different answer, which is exactly what acceptance 1
forbids.

Everything here is pure. Nothing in this module reads a clock, a repository or
another module: a projection that consulted anything outside its events could
not be rebuilt from them.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from clarity.contracts.events import (
    ActionCompletedV1,
    ActionFailedV1,
    CaseCreatedV1,
    CauseDetectedV1,
    ConversationTurnCompletedV1,
    DecisionGeneratedV1,
    EventPayload,
    ReceiptIssuedV1,
)
from clarity.platform.messaging.envelope import Event

#: Why the assistant stopped being able to help, in the order a reader cares.
#:
#: Named reasons rather than a single "handoff" count, because they call for
#: different work: a guard refusal is a safety control firing, a verifier
#: failure is the assistant nearly saying something wrong, and a handoff is a
#: customer who asked for a person or a journey with no automated answer.
STOP_REASONS = ("refused", "verifier_failed", "handoff", "no_source")

#: The payload types the dashboards are built from.
#:
#: One tuple, used both to decide what to fold and by the composition root to
#: decide what to subscribe to, so the two cannot drift: a type subscribed but
#: not folded wastes deliveries, and a type folded but not subscribed makes a
#: live projection disagree with a replay.
PROJECTED: tuple[type[EventPayload], ...] = (
    CaseCreatedV1,
    CauseDetectedV1,
    DecisionGeneratedV1,
    ActionCompletedV1,
    ActionFailedV1,
    ReceiptIssuedV1,
    ConversationTurnCompletedV1,
)


@dataclass
class TurnFact:
    """The latest turn seen for one case, by `turn_no`."""

    turn_no: int
    flow: str
    flow_state: str
    intent: str
    channel: str
    language: str
    handoff: bool = False
    refused: bool = False
    verifier_ok: bool = True
    resumed: bool = False
    guard_codes: tuple[str, ...] = ()
    cited: bool = False


@dataclass
class CaseFact:
    """What the log says about one case, kept so views can join at read time."""

    case_id: str
    cause_ref: str | None = None
    outcome: str | None = None
    refunded_lkr: Decimal = Decimal("0.00")
    failed: bool = False
    receipt_id: str | None = None
    channel: str | None = None


@dataclass
class Insights:
    """The read model. A pure fold over events, rebuildable from the log."""

    #: Event ids already folded in. What makes applying an event twice a no-op.
    #:
    #: Grows with the log, which is the honest trade for a prototype: the
    #: alternative is a per-consumer offset, and B04's `processed_event` record
    #: is where that belongs once projections are a deployable of their own.
    seen: set[str] = field(default_factory=set)

    cases: dict[str, CaseFact] = field(default_factory=dict)
    turns: dict[str, TurnFact] = field(default_factory=dict)
    causes: Counter[str] = field(default_factory=Counter)
    outcomes: Counter[str] = field(default_factory=Counter)
    events_folded: int = 0

    # -- the four dashboards --------------------------------------------- #

    def top_causes(self, limit: int = 10) -> list[dict[str, Any]]:
        """Which causes Clarity is finding, most first.

        Counted from `cause.detected`, so a case with two candidate causes
        contributes to both: the question a dashboard answers here is "what is
        the detector firing on", not "what was each case finally about".
        """
        total = sum(self.causes.values())
        return [
            {
                "cause_ref": cause,
                "cases": count,
                # A share only when there is something to share. A percentage
                # of nothing reads as 0% rather than as "no data".
                "share": round(count / total, 4) if total else None,
            }
            for cause, count in _ranked(self.causes)[:limit]
        ]

    def where_ai_stops(self) -> dict[str, Any]:
        """Where the assistant stopped being able to help, and why.

        Per reason, because they call for different work. A reader seeing one
        "handoff" number cannot tell a guard firing from a journey with no
        automated answer.
        """
        reasons: Counter[str] = Counter()
        for turn in self.turns.values():
            if turn.refused:
                reasons["refused"] += 1
            if not turn.verifier_ok:
                reasons["verifier_failed"] += 1
            if turn.handoff:
                reasons["handoff"] += 1
        conversations = len(self.turns)
        stopped = sum(1 for t in self.turns.values() if t.handoff or t.refused or not t.verifier_ok)
        return {
            "conversations": conversations,
            "stopped": stopped,
            "by_reason": {reason: reasons.get(reason, 0) for reason in STOP_REASONS},
            "containment": round(1 - stopped / conversations, 4) if conversations else None,
            "by_flow": dict(
                _ranked(
                    Counter(
                        f"{t.flow}.{t.flow_state}"
                        for t in self.turns.values()
                        if t.handoff or t.refused or not t.verifier_ok
                    )
                )
            ),
        }

    def drop_offs(self) -> dict[str, Any]:
        """Conversations that stopped somewhere that is not an ending.

        A drop-off is a customer who left mid journey, and it is the metric
        most easily faked: counting every conversation that is not `answered`
        would include the ones correctly handed to a person, which are not
        drop-offs but successes of a different kind. So a terminal state is a
        terminal state and only the rest count.
        """
        incomplete = {case_id: turn for case_id, turn in self.turns.items() if not _is_ending(turn)}
        return {
            "conversations": len(self.turns),
            "dropped": len(incomplete),
            "rate": round(len(incomplete) / len(self.turns), 4) if self.turns else None,
            "last_state": dict(
                _ranked(Counter(f"{t.flow}.{t.flow_state}" for t in incomplete.values()))
            ),
            "note": (
                "A conversation whose last turn was not a terminal flow state. "
                "A case handed to a person is not counted as a drop-off."
            ),
        }

    def refunds_by_rule(self) -> list[dict[str, Any]]:
        """What each cause cost, joined at read time.

        The join is here and not in the fold: a case's cause and its refunds
        arrive in separate events with no guaranteed order, so joining on
        arrival would drop a refund whose cause had not landed yet and the
        total would depend on delivery order.

        A refund with no known cause is reported under `unattributed` rather
        than dropped. Money that moved and cannot be explained is the most
        important row on this dashboard, not the one to hide.
        """
        totals: dict[str, Decimal] = {}
        counts: Counter[str] = Counter()
        for case in self.cases.values():
            if not case.refunded_lkr:
                continue
            key = case.cause_ref or "unattributed"
            totals[key] = totals.get(key, Decimal("0.00")) + case.refunded_lkr
            counts[key] += 1
        return [
            {
                "cause_ref": cause,
                "cases": counts[cause],
                # Decimal to string, never float: this is money (I3).
                "refunded_lkr": str(total),
            }
            for cause, total in sorted(totals.items(), key=lambda row: (-row[1], row[0]))
        ]

    def to_dict(self) -> dict[str, Any]:
        """Every dashboard, for a console or a smoke check."""
        return {
            "events_folded": self.events_folded,
            "cases": len(self.cases),
            "top_causes": self.top_causes(),
            "where_ai_stops": self.where_ai_stops(),
            "drop_offs": self.drop_offs(),
            "refunds_by_rule": self.refunds_by_rule(),
            "outcomes": dict(_ranked(self.outcomes)),
        }


#: Flow states that are an ending rather than a drop-off.
#:
#: Read from the flow files would be better and is the gap recorded in
#: MODULE.md: this is a second copy of names `config/flows/*.yaml` owns, and a
#: renamed state silently turns every conversation through it into a drop-off.
ENDINGS = frozenset(
    {
        "answered",
        "done",
        "receipt",
        "receipt_shown",
        "safeguard_on",
        "handed_off",
        "offer_person",
        "no_incident",
        "incident",
        "status",
    }
)


def _is_ending(turn: TurnFact) -> bool:
    """Whether this turn left the conversation somewhere final.

    A handoff counts as an ending: the customer is with a person, which is a
    resolution and not an abandonment.
    """
    return turn.handoff or turn.flow_state in ENDINGS


def _ranked(counter: Counter[str]) -> list[tuple[str, int]]:
    """Highest first, then by name, so two reads agree."""
    return sorted(counter.items(), key=lambda row: (-row[1], row[0]))


def apply(state: Insights, event: Event) -> Insights:
    """Fold one event in. Idempotent, pure, and mutates the state in place.

    In place because a projection folds a whole log and copying the state per
    event would make a rebuild quadratic. The function is still pure in the
    sense that matters: given the same events in any order it produces the same
    numbers, and it reads nothing outside them.
    """
    if event.id in state.seen:
        # At-least-once delivery (I7). A redelivery is normal, and counting it
        # would inflate a dashboard with nothing to say it had happened.
        return state

    payload = event.payload()
    if not isinstance(payload, PROJECTED):
        # An event this projection does not read. Not recorded and not
        # counted, which matters for more than tidiness: a rebuild folds the
        # whole log while the consumer group only receives the types it
        # subscribed to, so counting ignored events made `events_folded`
        # disagree between a live fold and a replay of the same history. The
        # counter now means "events this projection used", which is also the
        # more useful number.
        return state

    state.seen.add(event.id)
    state.events_folded += 1

    if isinstance(payload, CaseCreatedV1):
        case = _case(state, payload.case_id)
        case.channel = payload.channel.value
    elif isinstance(payload, CauseDetectedV1):
        case = _case(state, payload.case_id)
        cause = f"{payload.rule_id}@{payload.rule_version}"
        case.cause_ref = cause
        state.causes[cause] += 1
    elif isinstance(payload, DecisionGeneratedV1):
        case = _case(state, payload.case_id)
        case.outcome = payload.outcome.value
        state.outcomes[payload.outcome.value] += 1
    elif isinstance(payload, ActionCompletedV1):
        case = _case(state, payload.case_id)
        # Summed, because a case can be remediated more than once and each
        # execution is money that moved.
        case.refunded_lkr += Decimal(str(payload.total_amount_lkr))
    elif isinstance(payload, ActionFailedV1):
        _case(state, payload.case_id).failed = True
    elif isinstance(payload, ReceiptIssuedV1):
        _case(state, payload.case_id).receipt_id = payload.receipt_id
    elif isinstance(payload, ConversationTurnCompletedV1):
        _fold_turn(state, payload)

    return state


def _case(state: Insights, case_id: str) -> CaseFact:
    if case_id not in state.cases:
        state.cases[case_id] = CaseFact(case_id=case_id)
    return state.cases[case_id]


def _fold_turn(state: Insights, payload: ConversationTurnCompletedV1) -> None:
    """Keep the latest turn per case, decided by `turn_no`.

    By the number in the event and never by arrival order: a replay in a
    different order has to give the same answer (acceptance 1). An equal
    `turn_no` keeps the one already held, so the fold is stable rather than
    last-writer-wins.
    """
    held = state.turns.get(payload.case_id)
    if held is not None and held.turn_no >= payload.turn_no:
        return
    state.turns[payload.case_id] = TurnFact(
        turn_no=payload.turn_no,
        flow=payload.flow,
        flow_state=payload.flow_state,
        intent=payload.intent,
        channel=payload.channel.value,
        language=payload.language.value,
        handoff=payload.handoff,
        refused=payload.refused,
        verifier_ok=payload.verifier_ok,
        resumed=payload.resumed,
        guard_codes=tuple(payload.guard_codes),
        cited=bool(payload.chunk_ids),
    )


def rebuild(events: list[Event]) -> Insights:
    """Build the read model from scratch. Acceptance 1 compares this to live."""
    state = Insights()
    for event in events:
        apply(state, event)
    return state


__all__ = [
    "ENDINGS",
    "PROJECTED",
    "STOP_REASONS",
    "CaseFact",
    "Insights",
    "TurnFact",
    "apply",
    "rebuild",
]

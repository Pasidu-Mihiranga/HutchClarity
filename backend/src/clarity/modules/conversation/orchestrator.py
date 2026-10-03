"""The turn pipeline: one customer message, start to finish (C01, plan 22 section 4).

Before this, every chat turn was stateless: `handle_turn` read a message and
answered it with no memory of the one before. That made two things impossible.
A customer could not continue in the app what they started on WhatsApp, and
nothing recorded what the assistant had actually done, so a turn could not be
reviewed after the fact.

The pipeline runs the steps plan 22 section 4 lays out, in order:

1. **Guard** the input. Forbidden values (OTP, card, CVV, PIN) refuse the turn
   outright. Injection signals neutralise it instead (see below).
2. **Mask** personal data into tokens. Everything stored or sent onward from
   here is masked text, never what the customer typed.
3. **Intake**: language, intent and slots, from deterministic keyword rules.
4. **Handoff check**, on every turn.
5. **Flow step**, through the `FlowEngine` seam that C02 (#21) fills.
6. **Compose** from an approved template.
7. **Verify** the composed reply against FACTS.
8. **Record**: a turn audit entry and `conversation.turn.completed@v1`.

Two decisions in here are worth reading before changing anything.

**An injection neutralises the turn; it does not refuse it.** When the guard
holds the text, the message does not reach intake: the intent becomes FALLBACK,
a safe template answers, and the guard codes go in the audit. Refusing outright
was the other option and it is worse. Not every held message is an attack (a
confused customer writes strange things), and the control that actually stops
money moving is elsewhere: amounts come from the decision record, execution
needs a confirmation token minted outside this path, and the tool layer refuses
anything outside `Decision.allowed_actions`. The guard's job here is to stop the
text *steering* the conversation, which neutralising achieves without cutting
off a customer who may simply need help.

**Forbidden content does refuse.** An OTP or a card number must never be stored
or sent anywhere, so there is nothing to neutralise: the turn stops and the
reply tells the customer not to send it. This is the one hard stop.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from clarity.ai.guard import Guard, GuardVerdict, inspect
from clarity.ai.pii import ForbiddenContent, Masker
from clarity.contracts.events import ConversationTurnCompletedV1
from clarity.kernel.common import Channel, Language, utc_now
from clarity.modules.conversation.intent_routes import routing_payload
from clarity.modules.conversation.intents import Intent
from clarity.modules.conversation.service import (
    IntakeResult,
    check_handoff,
    compose_reply,
    extract_intake,
)
from clarity.modules.conversation.state import ConversationState, ConversationStore
from clarity.modules.conversation.verify import VerifierResult, verify_reply
from clarity.platform.audit.ledger import AuditEventType, AuditLedger
from clarity.platform.messaging.envelope import Event
from clarity.platform.messaging.outbox import outbox_in
from clarity.platform.persistence import UnitOfWorkFactory

#: The longest message the pipeline will take. Beyond this the turn is refused
#: rather than truncated: a truncated complaint is a complaint whose end nobody
#: read, and the customer is never told which half was dropped.
MAX_MESSAGE_CHARS = 2_000

#: What the customer is told when a turn is refused. Approved wording only
#: (I15): no model writes these, and they carry no detail about why beyond the
#: one thing the customer needs to do differently.
REFUSALS: Mapping[str, str] = {
    "FORBIDDEN_CONTENT": (
        "For your safety, please never send PINs, passwords, card numbers or "
        "one-time codes. I have not stored that message. Tell me what happened "
        "instead and I will look into the charge."
    ),
    "MESSAGE_TOO_LONG": (
        "That message is longer than I can read in one go. Could you send me "
        "the main problem in a few sentences?"
    ),
    "EMPTY_MESSAGE": "I did not catch that. Could you tell me what happened?",
}


@dataclass(frozen=True)
class FlowOutcome:
    """Where the flow engine moved the conversation, and what it used.

    `tools_called` and `chunk_ids` are here rather than on separate seams
    because the flow is what chooses a tool or a retrieval in a given state
    (plan 22 section 4, steps 5 to 7). The turn audit has to carry both
    (C01 acceptance 2), so they travel with the step that caused them.
    """

    flow: str
    state: str
    slots: dict[str, Any] = field(default_factory=dict)
    tools_called: tuple[str, ...] = ()
    chunk_ids: tuple[str, ...] = ()
    citations: tuple[str, ...] = ()
    proposal_id: str | None = None
    facts: dict[str, Any] = field(default_factory=dict)
    requires_citations: bool = False


class FlowEngine(Protocol):
    """The seam C02 (#21) fills with the flow registry and the seven flows.

    Until then the orchestrator keeps the conversation in `none/start` and says
    so in the audit, which is a truthful "no flow is driving this" rather than
    a guess at one.
    """

    def step(
        self,
        state: ConversationState,
        intake: IntakeResult,
        facts: Mapping[str, Any],
    ) -> FlowOutcome: ...


@dataclass(frozen=True)
class TurnRecord:
    """Everything the audit and the event need about one turn.

    No message text and no personal data. The reply and the customer's words are
    not in here by design: this is the record of what the assistant *did*, and
    a trail that quotes conversations becomes a store of conversations.
    """

    case_id: str
    turn_no: int
    channel: Channel
    flow: str
    state: str
    intent: str
    language: Language
    confidence: float
    resumed: bool
    handoff: bool
    refused: bool
    refusal_code: str | None
    guard_codes: tuple[str, ...]
    guard_assisted: bool
    masked_kinds: tuple[str, ...]
    tools_called: tuple[str, ...]
    chunk_ids: tuple[str, ...]
    model_role: str | None
    model: str | None
    verifier: VerifierResult

    def to_detail(self) -> dict[str, Any]:
        """The audit detail. Masked kinds, never masked values."""
        return {
            "turn_no": self.turn_no,
            "channel": self.channel.value,
            "flow": self.flow,
            "flow_state": self.state,
            "intent": self.intent,
            "language": self.language.value,
            "confidence": round(self.confidence, 3),
            "resumed": self.resumed,
            "handoff": self.handoff,
            "refused": self.refused,
            "refusal_code": self.refusal_code,
            "guard_codes": list(self.guard_codes),
            "guard_assisted_by_model": self.guard_assisted,
            "masked_kinds": list(self.masked_kinds),
            "tools_called": list(self.tools_called),
            "chunk_ids": list(self.chunk_ids),
            "model_role": self.model_role,
            "model": self.model,
            "verifier": self.verifier.to_dict(),
        }


@dataclass(frozen=True)
class Turn:
    """The result of one turn: what to say, and what was recorded."""

    reply: str
    state: ConversationState
    intake: IntakeResult
    handoff: dict[str, Any]
    verifier: VerifierResult
    record: TurnRecord
    citations: tuple[str, ...] = ()
    follow_ups: list[dict[str, str]] = field(default_factory=list)
    card_hints: dict[str, Any] = field(default_factory=dict)
    proposal_id: str | None = None

    @property
    def refused(self) -> bool:
        return self.record.refused

    def to_dict(self) -> dict[str, Any]:
        """A superset of the stateless `TurnResult.to_dict`.

        Every key the existing `/v1/conversation/turn` consumers read is kept
        with the same meaning, so putting the orchestrator behind that route is
        additive: `state`, `citations`, `proposal_id`, `refused` and `verifier`
        are new, and nothing that was there has moved.
        """
        return {
            "intake": self.intake.to_dict(),
            "handoff": self.handoff,
            "reply": self.reply,
            "case_id": self.state.case_id,
            "follow_ups": self.follow_ups,
            "card_hints": self.card_hints,
            "route": self.intake.route,
            "client_intent": self.intake.client_intent,
            "state": self.state.to_dict(),
            "citations": list(self.citations),
            "proposal_id": self.proposal_id,
            "refused": self.refused,
            "verifier": self.verifier.to_dict(),
        }


class ConversationOrchestrator:
    """Runs one turn through the pipeline and records what happened.

    Everything optional is optional on purpose. With no flow engine, no audit
    ledger and no unit of work, the orchestrator still runs a complete turn and
    keeps state: the `lite` profile needs no infrastructure (ADR-0006), and a
    test can construct one in a line.
    """

    def __init__(
        self,
        store: ConversationStore | None = None,
        *,
        masker: Masker | None = None,
        guard: Guard | None = None,
        flow: FlowEngine | None = None,
        audit: AuditLedger | None = None,
        open_unit: UnitOfWorkFactory | None = None,
    ) -> None:
        self._store = store or ConversationStore(open_unit=open_unit)
        self._masker = masker or Masker()
        self._guard = guard
        self._flow = flow
        self._audit = audit
        self._open_unit = open_unit

    @property
    def store(self) -> ConversationStore:
        return self._store

    def handle(
        self,
        case_id: str,
        text: str,
        *,
        channel: Channel,
        subscriber_ref: str = "",
        language_hint: str | None = None,
        intent_override: str | None = None,
        facts: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> Turn:
        """Run one customer message through the pipeline.

        Args:
            case_id: the conversation's identity. The same case id continues the
                same conversation on any channel, which is what makes WhatsApp
                to app continuity work (plan 22 section 9).
            text: what the customer sent. Masked before anything is stored.
            channel: where it arrived, for the audit and the handover trail.
            subscriber_ref: the pseudonymous subject, for the audit actor and
                the event envelope. Never an MSISDN.
            intent_override: an intent the interface is asserting, from a
                follow-up chip the customer tapped rather than typed. A tap is
                a choice from a list Clarity offered, so it is a stronger
                signal than free text; it still only selects a route, and the
                guard still runs on the text.
            facts: the authoritative set the reply is verified against.
            now: injected clock (I11).
        """
        moment = now or utc_now()
        known: dict[str, Any] = dict(facts or {})
        # Validated once, here. An unrecognised hint (a browser sending
        # "si-en", say) must not reach the stored state or the event: the
        # catalogue allows three languages and silently storing a fourth is how
        # a field stops meaning anything.
        asked = _language_or_none(language_hint)

        state, resumed = self._store.resume_or_start(
            case_id,
            channel=channel.value,
            language=asked.value if asked else None,
            now=moment,
        )
        state.turn_no += 1

        # -- 1. Guard input ------------------------------------------------ #
        refusal = self._refusal_for(text)
        if refusal is not None:
            return self._refuse(
                state,
                refusal,
                channel=channel,
                subscriber_ref=subscriber_ref,
                resumed=resumed,
                now=moment,
            )

        try:
            masked = self._masker.mask(text, now=moment)
        except ForbiddenContent:
            # The masker is the authority on this, and it refuses rather than
            # masking. Reaching here means the cheap check above missed a shape
            # the recognizers catch, which is the order they should run in.
            return self._refuse(
                state,
                "FORBIDDEN_CONTENT",
                channel=channel,
                subscriber_ref=subscriber_ref,
                resumed=resumed,
                now=moment,
            )

        verdict = self._inspect(masked.text)

        # -- 3. Intake, on masked text ------------------------------------- #
        if verdict.allowed:
            intake = extract_intake(masked.text)
        else:
            # Neutralised: the held text does not get to choose an intent. See
            # the module docstring for why this is not a refusal.
            intake = _fallback_intake(masked.text, language_hint or state.language)

        if intent_override and verdict.allowed:
            intake.intent = intent_override
            routing = routing_payload(intent_override)
            intake.route = routing["route"]
            intake.client_intent = routing["client_intent"]
            intake.needs_handoff = intent_override == Intent.HANDOFF.value
            intake.confidence = max(intake.confidence, 0.95)

        if asked is not None:
            intake.language = asked.value
        language = _language_or_none(intake.language) or Language.EN
        intake.language = language.value
        state.language = language.value

        # -- 4. Handoff check ---------------------------------------------- #
        handoff = check_handoff(intake)
        if handoff["handoff"]:
            intake.route = "handoff"
            intake.client_intent = "human"

        # -- 5. Flow step -------------------------------------------------- #
        outcome = self._step(state, intake, known)
        state.flow = outcome.flow
        state.state = outcome.state
        state.slots.update(outcome.slots)
        # Slots from intake are hints (I2). Stored because the next turn needs
        # the context, masked because the text they came from was.
        state.slots.update({key: value for key, value in intake.slots.items()})
        if outcome.proposal_id:
            state.last_proposal_id = outcome.proposal_id
        known.update(outcome.facts)

        # -- 6. Compose ---------------------------------------------------- #
        reply = compose_reply(intake, facts=known)

        # -- 7. Verify ----------------------------------------------------- #
        verifier = verify_reply(
            reply,
            facts=known,
            language=intake.language,
            citations=outcome.citations,
            require_citations=outcome.requires_citations,
        )
        if not verifier.ok:
            # A reply that failed verification is not sent. The customer gets
            # the approved fallback and a person gets the case, because the
            # alternative is quoting a figure nobody decided (I1).
            reply = compose_reply(_fallback_intake(masked.text, intake.language), facts={})
            handoff = {
                "handoff": True,
                "reason": "verifier_failed",
                "queue": "cx-general",
            }

        self._store.save(state, now=moment)

        record = TurnRecord(
            case_id=case_id,
            turn_no=state.turn_no,
            channel=channel,
            flow=state.flow,
            state=state.state,
            intent=intake.intent,
            language=language,
            confidence=intake.confidence,
            resumed=resumed,
            handoff=bool(handoff["handoff"]),
            refused=False,
            refusal_code=None,
            guard_codes=verdict.codes,
            guard_assisted=verdict.assisted_by_model,
            masked_kinds=tuple(sorted(set(masked.tokens.values()))),
            tools_called=outcome.tools_called,
            chunk_ids=outcome.chunk_ids,
            # No model wrote this turn: composition used an approved template.
            # Recorded as None rather than omitted, so "which model said this"
            # always has an answer in the trail (ADR-0009).
            model_role=None,
            model=None,
            verifier=verifier,
        )

        # -- 8. Record ----------------------------------------------------- #
        self._record(record, subscriber_ref=subscriber_ref, now=moment)

        return Turn(
            reply=reply,
            state=state,
            intake=intake,
            handoff=handoff,
            verifier=verifier,
            record=record,
            citations=outcome.citations,
            follow_ups=list(routing_payload(intake.intent)["follow_ups"]),
            card_hints={
                "title_key": "foundReason",
                "show_evidence": intake.route in {"account", "both"},
            },
            proposal_id=state.last_proposal_id,
        )

    # ------------------------------------------------------------------ #
    # Steps
    # ------------------------------------------------------------------ #

    @staticmethod
    def _refusal_for(text: str) -> str | None:
        """The cheap input checks, before masking or any model."""
        if not text or not text.strip():
            return "EMPTY_MESSAGE"
        if len(text) > MAX_MESSAGE_CHARS:
            return "MESSAGE_TOO_LONG"
        return None

    def _inspect(self, text: str) -> GuardVerdict:
        """The guard, with the model tier when one is configured.

        This is the call site A03 built `Guard` for and left unwired: until C01
        nothing in a request path inspected customer text.
        """
        if self._guard is not None:
            return self._guard.check(text)
        return inspect(text)

    def _step(
        self,
        state: ConversationState,
        intake: IntakeResult,
        facts: Mapping[str, Any],
    ) -> FlowOutcome:
        if self._flow is None:
            return FlowOutcome(flow=state.flow, state=state.state)
        return self._flow.step(state, intake, facts)

    def _refuse(
        self,
        state: ConversationState,
        code: str,
        *,
        channel: Channel,
        subscriber_ref: str,
        resumed: bool,
        now: datetime,
    ) -> Turn:
        """Stop the turn, say the approved thing, and record the refusal.

        State is still saved: a refused turn happened, and the next turn should
        not look like the first one. Nothing from the refused message is kept.
        """
        intake = _fallback_intake("", state.language)
        verifier = verify_reply(REFUSALS[code], facts={}, language=state.language)
        self._store.save(state, now=now)

        record = TurnRecord(
            case_id=state.case_id,
            turn_no=state.turn_no,
            channel=channel,
            flow=state.flow,
            state=state.state,
            intent=intake.intent,
            language=_language_or_none(state.language) or Language.EN,
            confidence=intake.confidence,
            resumed=resumed,
            handoff=False,
            refused=True,
            refusal_code=code,
            guard_codes=(),
            guard_assisted=False,
            masked_kinds=(),
            tools_called=(),
            chunk_ids=(),
            model_role=None,
            model=None,
            verifier=verifier,
        )
        self._record(record, subscriber_ref=subscriber_ref, now=now)

        return Turn(
            reply=REFUSALS[code],
            state=state,
            intake=intake,
            handoff={"handoff": False, "reason": code, "queue": None},
            verifier=verifier,
            record=record,
        )

    def _record(self, record: TurnRecord, *, subscriber_ref: str, now: datetime) -> None:
        """Step 11: the turn audit entry and the completed event.

        Both or neither. They are written in the same call so a turn cannot be
        audited without being published or the other way round; the event goes
        through the outbox in its own unit of work, so a consumer never sees a
        turn that was not recorded (I7).
        """
        if self._audit is not None:
            self._audit.append(
                AuditEventType.TURN_RECORDED,
                actor_ref=subscriber_ref or "anonymous",
                object_ref=record.case_id,
                case_id=record.case_id,
                payload={
                    "case_id": record.case_id,
                    "turn_no": record.turn_no,
                    "flow_state": record.state,
                    "intent": record.intent,
                    "verifier_ok": record.verifier.ok,
                },
                detail=record.to_detail(),
                now=now,
            )

        if self._open_unit is None:
            return
        with self._open_unit() as unit:
            outbox_in(unit).append(
                Event.of(
                    ConversationTurnCompletedV1(
                        case_id=record.case_id,
                        turn_no=record.turn_no,
                        channel=record.channel,
                        flow=record.flow,
                        flow_state=record.state,
                        intent=record.intent,
                        language=record.language,
                        resumed=record.resumed,
                        handoff=record.handoff,
                        refused=record.refused,
                        guard_codes=list(record.guard_codes),
                        tools_called=list(record.tools_called),
                        chunk_ids=list(record.chunk_ids),
                        model_role=record.model_role,
                        verifier_ok=record.verifier.ok,
                        verifier_codes=list(record.verifier.codes),
                    ),
                    subject=subscriber_ref or record.case_id,
                )
            )
            unit.commit()


def _language_or_none(value: str | None) -> Language | None:
    """The language if Clarity answers in it, otherwise None."""
    if not value:
        return None
    try:
        return Language(value)
    except ValueError:
        return None


def _fallback_intake(text: str, language: str) -> IntakeResult:
    """A neutral intake: no intent claimed, no slots carried over."""
    routing = routing_payload(Intent.FALLBACK.value)
    return IntakeResult(
        intent=Intent.FALLBACK.value,
        confidence=0.0,
        slots={},
        language=language,
        needs_handoff=False,
        raw_text=text,
        route=routing["route"],
        client_intent=routing["client_intent"],
    )


def citations_of(outcome: FlowOutcome) -> Sequence[str]:
    """The citations a flow step produced, for an interface to render."""
    return outcome.citations


__all__ = [
    "MAX_MESSAGE_CHARS",
    "REFUSALS",
    "ConversationOrchestrator",
    "FlowEngine",
    "FlowOutcome",
    "Turn",
    "TurnRecord",
]

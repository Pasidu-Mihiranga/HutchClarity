"""Case aggregate and its lifecycle (plan §16.2, Diagram 18)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from clarity.kernel.common import (
    Channel,
    ClarityModel,
    Language,
    Money,
    ensure_utc,
    utc_now,
)


class CaseState(StrEnum):
    """States from the case lifecycle state machine (plan Diagram 18)."""

    OPEN = "OPEN"
    COLLECTING_EVIDENCE = "COLLECTING_EVIDENCE"
    HELD_FOR_EVIDENCE = "HELD_FOR_EVIDENCE"
    EVALUATED = "EVALUATED"
    AWAITING_CUSTOMER = "AWAITING_CUSTOMER"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    COMPENSATING = "COMPENSATING"
    ACTIONED = "ACTIONED"
    EXPLAINED = "EXPLAINED"
    HANDED_OFF = "HANDED_OFF"
    RECEIPTED = "RECEIPTED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


#: Allowed transitions. Anything not listed is rejected, so a case can never
#: reach ACTIONED without passing through execution.
CASE_TRANSITIONS: dict[CaseState, frozenset[CaseState]] = {
    CaseState.OPEN: frozenset({CaseState.COLLECTING_EVIDENCE, CaseState.HANDED_OFF}),
    CaseState.COLLECTING_EVIDENCE: frozenset(
        {CaseState.EVALUATED, CaseState.HELD_FOR_EVIDENCE, CaseState.HANDED_OFF}
    ),
    CaseState.HELD_FOR_EVIDENCE: frozenset({CaseState.COLLECTING_EVIDENCE, CaseState.HANDED_OFF}),
    CaseState.EVALUATED: frozenset(
        {
            CaseState.EXECUTING,
            CaseState.AWAITING_CUSTOMER,
            CaseState.AWAITING_APPROVAL,
            CaseState.EXPLAINED,
            CaseState.HANDED_OFF,
        }
    ),
    CaseState.AWAITING_CUSTOMER: frozenset({CaseState.EXECUTING, CaseState.EXPLAINED}),
    CaseState.AWAITING_APPROVAL: frozenset(
        {CaseState.EXECUTING, CaseState.EXPLAINED, CaseState.HANDED_OFF}
    ),
    CaseState.EXECUTING: frozenset({CaseState.ACTIONED, CaseState.COMPENSATING}),
    CaseState.COMPENSATING: frozenset({CaseState.HANDED_OFF}),
    CaseState.ACTIONED: frozenset({CaseState.RECEIPTED}),
    CaseState.EXPLAINED: frozenset({CaseState.RECEIPTED, CaseState.HANDED_OFF}),
    CaseState.HANDED_OFF: frozenset({CaseState.EVALUATED, CaseState.CLOSED}),
    CaseState.RECEIPTED: frozenset({CaseState.CLOSED}),
    CaseState.CLOSED: frozenset({CaseState.REOPENED}),
    CaseState.REOPENED: frozenset({CaseState.COLLECTING_EVIDENCE}),
}


class IllegalTransition(ValueError):
    """Raised when code attempts a transition the lifecycle forbids."""

    def __init__(self, source: CaseState, target: CaseState) -> None:
        super().__init__(f"illegal case transition {source.value} -> {target.value}")
        self.source = source
        self.target = target


def assert_transition(source: CaseState, target: CaseState) -> None:
    """Guard a state change (raises :class:`IllegalTransition`)."""
    if target not in CASE_TRANSITIONS.get(source, frozenset()):
        raise IllegalTransition(source, target)


class CaseTrigger(StrEnum):
    """Who or what opened the case."""

    CUSTOMER = "customer"
    STREAM = "stream"
    """Zero-contact detection from the live event stream (deck S5)."""
    STAFF = "staff"


class CustomerReference(ClarityModel):
    """Pseudonymous customer record. No raw MSISDN (plan §16.1)."""

    subscriber_ref: str
    msisdn_masked: str
    preferred_language: Language = Language.EN
    segment: str | None = None
    vault_token: str | None = Field(
        default=None, description="Handle for the raw MSISDN held in the token vault."
    )


class CaseEvent(ClarityModel):
    """Audit-visible activity on a case (messages, state changes, handoffs)."""

    type: str
    at: datetime = Field(default_factory=utc_now)
    channel: Channel = Channel.SYSTEM
    payload_masked: dict[str, Any] = Field(default_factory=dict)

    @field_validator("at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class Case(ClarityModel):
    """A dispute or question, from any channel, with one shared trail.

    One case follows the customer across channels: "start on WhatsApp, finish
    in the app or at a shop" (deck S5).
    """

    case_id: str
    case_no: str
    customer: CustomerReference
    state: CaseState = CaseState.OPEN
    trigger: CaseTrigger
    origin_channel: Channel
    language: Language = Language.EN
    charge_ref: str | None = Field(
        default=None, description="Set when the customer tapped Why? on a specific charge."
    )
    money_at_stake_lkr: Money | None = None
    opened_at: datetime = Field(default_factory=utc_now)
    events: list[CaseEvent] = Field(default_factory=list)

    @field_validator("opened_at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    def with_state(self, target: CaseState, *, note: str | None = None) -> Case:
        """Return a copy in ``target`` state, enforcing the lifecycle."""
        assert_transition(self.state, target)
        event = CaseEvent(
            type="state_change",
            payload_masked={"from": self.state.value, "to": target.value}
            | ({"note": note} if note else {}),
        )
        return self.model_copy(update={"state": target, "events": [*self.events, event]})

"""Alerts and their lifecycle (audit assurance plan 5.7, ADR-0037).

An alert is a finding that a person owes an answer on. The lifecycle exists so
that answer is recorded rather than remembered: ``open`` to ``acknowledged`` to
``investigating`` to ``disposed``, each transition with an actor, and a
disposition that always carries a reason.

Three rules shape who may close one:

- **Nobody disposes of an alert they are the subject of** (plan 5.6 rule 2).
- **A high or critical alert needs a second person**: whoever acknowledged it
  cannot also dispose of it.
- **Disposing needs ``alert:dispose``**, which an audit duty grants and which
  removes money permissions from whoever holds it (ADR-0036).

Repeat firings do not pile up: a finding with the same ``group_key`` as an open
alert is the same alert seen again, which keeps a noisy rule from burying the
quiet one next to it.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from clarity.kernel.common import ClarityModel
from clarity.modules.assurance.rules import Band, Finding
from clarity.platform.security.principal import Permission, Principal

#: One collection is one table in B05.
ALERTS = "assurance.alerts"

#: Bands whose closure needs a different person from the one who acknowledged.
SECOND_PERSON_BANDS: frozenset[Band] = frozenset({Band.HIGH, Band.CRITICAL})


class AlertState(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    DISPOSED = "disposed"


class Disposition(StrEnum):
    CONFIRMED = "confirmed"
    """It was real. The finding stands."""
    FALSE_POSITIVE = "false_positive"
    """It was not. Feeds threshold changes through governance, never a live edit."""
    ACCEPTED_RISK = "accepted_risk"
    """Real, and accepted deliberately, by someone who may accept it."""


class Alert(ClarityModel):
    alert_id: str
    rule_id: str
    band: Band
    group_key: str
    summary: str
    evidence: list[int]
    """``seq`` numbers in the audit trail that justify this alert."""
    subject_ref: str | None = None
    case_id: str | None = None
    state: AlertState = AlertState.OPEN
    raised_at: datetime
    last_seen_at: datetime
    occurrences: int = 1
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    escalated_at: datetime | None = None
    disposed_by: str | None = None
    disposed_at: datetime | None = None
    disposition: Disposition | None = None
    disposition_reason: str | None = None

    @property
    def is_closed(self) -> bool:
        return self.state is AlertState.DISPOSED

    def seen_again(self, finding: Finding, at: datetime) -> Alert:
        """The same finding again: one alert, more evidence, not a second row."""
        return self.model_copy(
            update={
                "occurrences": self.occurrences + 1,
                "last_seen_at": at,
                "summary": finding.summary,
                "evidence": sorted({*self.evidence, *finding.evidence}),
            }
        )


class AlertRefused(Exception):
    """A lifecycle move broke a rule. ``code`` is stable for the API."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


class AlertNotFound(KeyError):
    pass


def refuse_unless_may_act(alert: Alert, by: Principal) -> None:
    """Who may touch an alert at all: the permission, and not its own subject.

    Applies to every move. The second-person rule is deliberately *not* here:
    whoever acknowledges an alert should go on to investigate it, and only the
    closing move needs the other pair of eyes.
    """
    if not by.has(Permission.ALERT_DISPOSE):
        raise AlertRefused("NOT_PERMITTED", "this account may not act on alerts")
    if alert.subject_ref is not None and alert.subject_ref == by.ref:
        raise AlertRefused("SELF_DISPOSAL", "nobody may act on an alert they are the subject of")


def refuse_unless_may_dispose(alert: Alert, by: Principal) -> None:
    """The closing move: everything above, plus the second pair of eyes."""
    refuse_unless_may_act(alert, by)
    if alert.band in SECOND_PERSON_BANDS and alert.acknowledged_by == by.ref:
        raise AlertRefused(
            "SECOND_PERSON",
            f"a {alert.band.value} alert is disposed of by someone other than "
            "the person who acknowledged it",
        )


__all__ = [
    "ALERTS",
    "SECOND_PERSON_BANDS",
    "Alert",
    "AlertNotFound",
    "AlertRefused",
    "AlertState",
    "Disposition",
    "refuse_unless_may_act",
    "refuse_unless_may_dispose",
]

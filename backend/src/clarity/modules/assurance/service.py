"""The assurance service: detection, alerts, liveness and the playbook (ADR-0037).

What it does, and deliberately does not do:

- It **reads** the audit trail and raises alerts. It never decides anything
  about a case, never touches money, and is never called by a money path: it
  reacts to events (I22), so a slow or failing rule cannot block a refund.
- It **flips kill switches** when the trail breaks. That is the one action it
  takes, it only ever moves them to the safe side, and it is recorded.
- It knows nothing about customers. Its subjects are staff refs and case ids.

**Silence is not safety.** If detection stops running, nothing raises alerts
and the dashboard looks calm. So the service records a heartbeat each time it
runs, and a liveness check turns a missing heartbeat into a critical alert.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from clarity.kernel.common import utc_now
from clarity.kernel.ids import new_id
from clarity.modules.assurance.alerts import (
    ALERTS,
    Alert,
    AlertNotFound,
    AlertRefused,
    AlertState,
    Disposition,
    refuse_unless_may_act,
    refuse_unless_may_dispose,
)
from clarity.modules.assurance.rules import RULES, Band, Finding, Thresholds
from clarity.platform.audit.ledger import ActorKind, AuditEventType, AuditLedger
from clarity.platform.config.switches import Switch, SwitchBoard
from clarity.platform.messaging.outbox import OutboxRow
from clarity.platform.persistence import Repository, UnitOfWorkFactory
from clarity.platform.security.principal import Principal

#: Where the last detection run is remembered, so silence can be noticed.
HEARTBEATS = "assurance.heartbeats"

_HEARTBEAT_KEY = "detection"

#: Switches moved to the safe side when the trail cannot be trusted.
PLAYBOOK_SWITCHES: tuple[Switch, ...] = (Switch.AUTO_FIX_GLOBAL, Switch.CUSTOMER_ACTIONS)

#: Rules the service raises itself rather than counting from the trail.
CHAIN_BREAK = "chain_break"
DETECTOR_SILENT = "detector_silent"
CHECKPOINT_GAP = "checkpoint_gap"
TRAIL_LAG = "trail_lag"


class AssuranceService:
    """Runs the rules, keeps the alerts, and holds the chain-break playbook."""

    def __init__(
        self,
        open_unit: UnitOfWorkFactory,
        *,
        audit: AuditLedger,
        switches: SwitchBoard,
        verify: Callable[[], object],
        resolve: Callable[[str, datetime], object],
        clock: Callable[[], datetime] | None = None,
        pending: Callable[[], Sequence[OutboxRow]] | None = None,
    ) -> None:
        self._open_unit = open_unit
        self._audit = audit
        self._switches = switches
        self._verify = verify
        self._resolve = resolve
        self._clock = clock or utc_now
        #: Undelivered outbox rows. Optional, and a callable rather than the
        #: outbox itself, because this module must not reach into messaging: it
        #: is handed the one read it needs by the composition root.
        self._pending = pending

    # -- reading -------------------------------------------------------------- #

    def alerts(self, *, open_only: bool = False) -> list[Alert]:
        with self._open_unit() as unit:
            store: Repository[str, Alert] = unit.repository(ALERTS)
            found = store.values()
        ordered = sorted(found, key=lambda alert: alert.raised_at, reverse=True)
        return [alert for alert in ordered if not alert.is_closed] if open_only else ordered

    def alert(self, alert_id: str) -> Alert:
        with self._open_unit() as unit:
            store: Repository[str, Alert] = unit.repository(ALERTS)
            found = store.get(alert_id)
        if found is None:
            raise AlertNotFound(alert_id)
        return found

    # -- detection -------------------------------------------------------------- #

    def run(self) -> list[Alert]:
        """Evaluate every rule over the trail, then record that detection ran.

        The heartbeat is written even when nothing fires: a quiet run and a run
        that never happened must not look the same.
        """
        now = self._clock()
        records = self._audit.records
        thresholds = Thresholds(self._resolve, now)

        findings: list[Finding] = []
        for rule_id, rule in RULES.items():
            try:
                findings.extend(rule(records, thresholds, now))
            except Exception as error:  # one broken rule must not stop the rest
                findings.append(
                    Finding(
                        rule_id=f"{rule_id}_failed",
                        band=Band.MEDIUM,
                        summary=f"risk rule {rule_id} could not be evaluated: {error}",
                        evidence=(),
                    )
                )
        findings.extend(self._integrity_findings(now))
        findings.extend(self._lag_findings(now))
        raised = [self._record(finding, now) for finding in findings]
        self._escalate_overdue(now)
        self._beat(now)
        return [alert for alert in raised if alert is not None]

    def _integrity_findings(self, now: datetime) -> list[Finding]:
        """The trail's own health: a break, and a checkpoint that stopped coming."""
        verification = self._verify()
        intact = bool(getattr(verification, "intact", True))
        findings: list[Finding] = []
        if not intact:
            reason = getattr(verification, "reason", None)
            broken_at = getattr(verification, "broken_at", None)
            findings.append(
                Finding(
                    rule_id=CHAIN_BREAK,
                    band=Band.CRITICAL,
                    summary=f"the audit trail failed verification at seq {broken_at}: {reason}",
                    evidence=(broken_at,) if isinstance(broken_at, int) else (),
                )
            )
            self.chain_break_playbook(reason=str(reason), broken_at=broken_at)
        else:
            last = getattr(verification, "last_checkpoint_seq", None)
            gap = Thresholds(self._resolve, now).window("assurance.checkpoint.max_gap")
            latest = self._last_checkpoint_at()
            if last is None or (latest is not None and now - latest > gap):
                findings.append(
                    Finding(
                        rule_id=CHECKPOINT_GAP,
                        band=Band.CRITICAL,
                        summary=f"no audit checkpoint has been signed within {gap}",
                        evidence=(),
                    )
                )
        return findings

    def _lag_findings(self, now: datetime) -> list[Finding]:
        """Events committed but not yet published: the quiet way the trail stops.

        An append to the ledger is synchronous, so there is no writer queue to
        fall behind. The gap is one step earlier. A state change commits its
        event to the outbox in the same transaction (I7) and the relay publishes
        it afterwards; the consumers that turn an event into a ``event.published``
        record run on the far side of that. So a stalled relay leaves the state
        changed and the trail quiet, which is precisely the failure the
        heartbeat was added for: nothing looks wrong, because nothing is
        arriving to look wrong.

        Counted, like every other rule: the number of rows still pending past
        the age the policy store allows, with the oldest named, and no attempt to
        guess why. A relay that is merely busy clears them and the alert closes
        on the next run; one that is stuck does not.
        """
        if self._pending is None:
            return []
        tolerated = Thresholds(self._resolve, now).window("assurance.outbox.max_lag")
        try:
            stale = [row for row in self._pending() if now - row.appended_at > tolerated]
        except Exception as error:  # the check must not be the thing that fails
            return [
                Finding(
                    rule_id=f"{TRAIL_LAG}_failed",
                    band=Band.MEDIUM,
                    summary=f"outbox lag could not be measured: {error}",
                    evidence=(),
                )
            ]
        if not stale:
            return []
        oldest = min(stale, key=lambda row: row.appended_at)
        return [
            Finding(
                rule_id=TRAIL_LAG,
                band=Band.HIGH,
                summary=(
                    f"{len(stale)} event(s) have been waiting to be published for "
                    f"longer than {tolerated}, the oldest since "
                    f"{oldest.appended_at.isoformat()}: the trail is behind the system"
                ),
                evidence=(),
            )
        ]

    def _last_checkpoint_at(self) -> datetime | None:
        issued = self._audit.of_type(AuditEventType.CHECKPOINT_ISSUED)
        return issued[-1].occurred_at if issued else None

    # -- liveness ----------------------------------------------------------------- #

    def _beat(self, now: datetime) -> None:
        with self._open_unit() as unit:
            store: Repository[str, datetime] = unit.repository(HEARTBEATS)
            store.put(_HEARTBEAT_KEY, now)
            unit.commit()

    def last_run(self) -> datetime | None:
        with self._open_unit() as unit:
            store: Repository[str, datetime] = unit.repository(HEARTBEATS)
            return store.get(_HEARTBEAT_KEY)

    def check_liveness(self) -> Alert | None:
        """Turn silence into a critical alert.

        Called from somewhere that is *not* the detection loop, because a loop
        that has stopped cannot report that it stopped.
        """
        now = self._clock()
        interval = Thresholds(self._resolve, now).window("assurance.liveness.max_silence")
        last = self.last_run()
        if last is not None and now - last <= interval:
            return None
        silent_for = "ever" if last is None else str(now - last)
        return self._record(
            Finding(
                rule_id=DETECTOR_SILENT,
                band=Band.CRITICAL,
                summary=f"risk detection has not run for {silent_for}: nothing is watching",
                evidence=(),
            ),
            now,
        )

    # -- the playbook ---------------------------------------------------------------- #

    def chain_break_playbook(self, *, reason: str, broken_at: object = None) -> list[Switch]:
        """Money stops moving while the trail cannot be trusted.

        Only ever towards the safe side, and never back: a person with the
        authority turns these on again, with a reason, once the break is
        understood. Flipping an already-off switch is not repeated.
        """
        flipped: list[Switch] = []
        for switch in PLAYBOOK_SWITCHES:
            if self._switches.is_off(switch):
                continue
            self._switches.turn_off(
                switch,
                actor_ref="clarity-assurance",
                reason=f"audit trail broken at {broken_at}: {reason}",
            )
            flipped.append(switch)
        return flipped

    # -- the lifecycle -------------------------------------------------------------- #

    def _record(self, finding: Finding, now: datetime) -> Alert | None:
        """Raise the alert, or fold the finding into the open one it repeats."""
        with self._open_unit() as unit:
            store: Repository[str, Alert] = unit.repository(ALERTS)
            existing = next(
                (
                    alert
                    for alert in store.values()
                    if alert.group_key == finding.group_key and not alert.is_closed
                ),
                None,
            )
            if existing is not None:
                seen = existing.seen_again(finding, now)
                if seen.evidence == existing.evidence and seen.summary == existing.summary:
                    return None  # nothing new to say
                store.put(seen.alert_id, seen)
                unit.commit()
                return seen
            alert = Alert(
                alert_id=new_id("ALT"),
                rule_id=finding.rule_id,
                band=finding.band,
                group_key=finding.group_key,
                summary=finding.summary,
                evidence=sorted(finding.evidence),
                subject_ref=finding.subject_ref,
                case_id=finding.case_id,
                raised_at=now,
                last_seen_at=now,
            )
            store.put(alert.alert_id, alert)
            unit.commit()
        self._audit_alert(AuditEventType.ALERT_RAISED, alert, actor_ref="clarity-assurance")
        return alert

    def acknowledge(self, by: Principal, alert_id: str) -> Alert:
        alert = self.alert(alert_id)
        refuse_unless_may_act(alert, by)
        if alert.is_closed:
            raise AlertRefused("ALREADY_DISPOSED", "this alert is closed")
        moved = alert.model_copy(
            update={
                "state": AlertState.ACKNOWLEDGED,
                "acknowledged_by": by.ref,
                "acknowledged_at": self._clock(),
            }
        )
        return self._save_and_record(moved, AuditEventType.ALERT_ACKNOWLEDGED, by.ref)

    def investigate(self, by: Principal, alert_id: str) -> Alert:
        alert = self.alert(alert_id)
        refuse_unless_may_act(alert, by)
        if alert.state is not AlertState.ACKNOWLEDGED:
            raise AlertRefused("NOT_ACKNOWLEDGED", "acknowledge an alert before investigating it")
        return self._save_and_record(
            alert.model_copy(update={"state": AlertState.INVESTIGATING}),
            AuditEventType.ALERT_INVESTIGATING,
            by.ref,
        )

    def dispose(
        self, by: Principal, alert_id: str, *, disposition: Disposition, reason: str
    ) -> Alert:
        """Close it, with a reason. The three closure rules apply here."""
        alert = self.alert(alert_id)
        refuse_unless_may_dispose(alert, by)
        if alert.is_closed:
            raise AlertRefused("ALREADY_DISPOSED", "this alert is closed")
        if alert.state is AlertState.OPEN:
            raise AlertRefused("NOT_ACKNOWLEDGED", "acknowledge an alert before disposing of it")
        if not reason.strip():
            raise AlertRefused("REASON_REQUIRED", "a disposition needs a reason")
        closed = alert.model_copy(
            update={
                "state": AlertState.DISPOSED,
                "disposed_by": by.ref,
                "disposed_at": self._clock(),
                "disposition": disposition,
                "disposition_reason": reason.strip(),
            }
        )
        return self._save_and_record(closed, AuditEventType.ALERT_DISPOSED, by.ref)

    def _escalate_overdue(self, now: datetime) -> list[Alert]:
        """An alert nobody acknowledged within the SLA is escalated, once."""
        sla = Thresholds(self._resolve, now).window("assurance.alert.ack_sla")
        escalated: list[Alert] = []
        for alert in self.alerts(open_only=True):
            if alert.state is not AlertState.OPEN or alert.escalated_at is not None:
                continue
            if now - alert.raised_at <= sla:
                continue
            escalated.append(
                self._save_and_record(
                    alert.model_copy(update={"escalated_at": now}),
                    AuditEventType.ALERT_ESCALATED,
                    "clarity-assurance",
                )
            )
        return escalated

    def _save_and_record(self, alert: Alert, event: AuditEventType, actor_ref: str) -> Alert:
        with self._open_unit() as unit:
            store: Repository[str, Alert] = unit.repository(ALERTS)
            store.put(alert.alert_id, alert)
            unit.commit()
        self._audit_alert(event, alert, actor_ref=actor_ref)
        return alert

    def _audit_alert(self, event: AuditEventType, alert: Alert, *, actor_ref: str) -> None:
        self._audit.append(
            event,
            actor_ref=actor_ref,
            actor_kind=ActorKind.SYSTEM if actor_ref.startswith("clarity-") else ActorKind.STAFF,
            object_ref=alert.alert_id,
            payload=alert.model_dump(mode="json"),
            case_id=alert.case_id,
            detail={
                "rule_id": alert.rule_id,
                "band": alert.band.value,
                "state": alert.state.value,
                "subject": alert.subject_ref,
                "evidence": alert.evidence,
                "occurrences": alert.occurrences,
                "disposition": alert.disposition.value if alert.disposition else None,
                "reason": alert.disposition_reason,
            },
        )

    def sweep_interval(self) -> timedelta:
        return Thresholds(self._resolve, self._clock()).window("assurance.detection.interval")


__all__ = [
    "CHAIN_BREAK",
    "CHECKPOINT_GAP",
    "DETECTOR_SILENT",
    "HEARTBEATS",
    "PLAYBOOK_SWITCHES",
    "AssuranceService",
]

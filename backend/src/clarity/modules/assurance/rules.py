"""Risk rules counted from the audit trail (audit assurance plan 5.7, ADR-0037).

**Counted, never modelled.** Every rule here is a count or a join over records
the trail already holds, with its thresholds resolved from the policy store at
the moment they apply (I10). No model scores risk, and nothing in this file
decides anything about a case: a finding is a reason for a person to look
(I1). ``deskops/watch.py`` set this precedent and says why: a modelled number
is a guess wearing a number's clothes, and the desk would act on it.

Every finding carries the ``seq`` numbers that justify it, so a reviewer reads
the evidence rather than trusting a score.

**What a rule may read.** Only ``AuditRecord`` fields: the type, actor, object,
case, times and the masked detail. Never a payload, never customer data.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from clarity.platform.audit.ledger import AuditEventType, AuditRecord


class Band(StrEnum):
    """How loudly a finding asks for attention."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Finding:
    """One rule firing: what, about whom, and the records that prove it."""

    rule_id: str
    band: Band
    summary: str
    evidence: tuple[int, ...]
    subject_ref: str | None = None
    """The actor the finding is about, when it is about one. Never a customer."""
    case_id: str | None = None

    @property
    def group_key(self) -> str:
        """Firings that share this key are the same alert, seen again."""
        return f"{self.rule_id}:{self.subject_ref or self.case_id or '-'}"


class Thresholds:
    """Policy values a rule needs, resolved ``as_of`` the moment they apply."""

    def __init__(self, resolve: Callable[[str, datetime], object], now: datetime) -> None:
        self._resolve = resolve
        self._now = now

    def number(self, key: str) -> Decimal:
        return Decimal(str(self._resolve(key, self._now)))

    def count(self, key: str) -> int:
        return int(self.number(key))

    def window(self, key: str) -> timedelta:
        from pydantic import TypeAdapter

        return TypeAdapter(timedelta).validate_python(str(self._resolve(key, self._now)))


Rule = Callable[[Sequence[AuditRecord], Thresholds, datetime], list[Finding]]


def _money(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _within(records: Iterable[AuditRecord], *, since: datetime) -> list[AuditRecord]:
    return [record for record in records if record.occurred_at >= since]


def _approvers_by_case(records: Sequence[AuditRecord]) -> dict[str, tuple[str, int]]:
    """Which human approved each case, from the request they made.

    A domain event names the mode (``staff_approved``), never the person; the
    request record from W2 names the person. Joining them on the case is how an
    investigator does it, and the only way to attribute an amount to a human.
    """
    found: dict[str, tuple[str, int]] = {}
    for record in records:
        if (
            record.event_type is AuditEventType.REQUEST_PERFORMED
            and record.object_ref.endswith("/approve")
            and record.case_id
            and int(record.detail.get("status", 0)) < 300
        ):
            found[record.case_id] = (record.actor_ref, record.seq)
    return found


# --------------------------------------------------------------------------- #
# The rules
# --------------------------------------------------------------------------- #


def structuring(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """Repeated approvals just under the four-eyes cap by one person.

    One approval below the cap is the system working. Several in an hour, each
    sitting just under the line that would have called a second person, is the
    shape of someone splitting payouts to stay below it.
    """
    cap = thresholds.number("decision.four_eyes.threshold_lkr")
    floor = cap * thresholds.number("assurance.structuring.near_cap_fraction")
    minimum = thresholds.count("assurance.structuring.min_count")
    since = now - thresholds.window("assurance.structuring.window")

    recent = _within(records, since=since)
    approvers = _approvers_by_case(recent)
    by_actor: dict[str, list[int]] = defaultdict(list)
    for record in recent:
        if record.event_type is not AuditEventType.ACTION_EXECUTED or not record.case_id:
            continue
        amount = _money(record.detail.get("total_amount_lkr") or record.detail.get("amount_lkr"))
        if amount is None or not (floor <= amount < cap):
            continue
        approved = approvers.get(record.case_id)
        if approved is None:
            continue
        actor, approval_seq = approved
        by_actor[actor].extend((approval_seq, record.seq))

    return [
        Finding(
            rule_id="structuring",
            band=Band.HIGH,
            subject_ref=actor,
            summary=(
                f"{len(seqs) // 2} approvals between LKR {floor} and the "
                f"LKR {cap} four-eyes cap by {actor} within the window"
            ),
            evidence=tuple(sorted(seqs)),
        )
        for actor, seqs in by_actor.items()
        if len(seqs) // 2 >= minimum
    ]


def self_approval(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """The same human proposed a plan and approved it.

    Four-eyes is enforced on the money path, so this should be impossible. A
    finding here means it was circumvented, or two sessions resolve to one
    person, which is worth a look either way.
    """
    proposed: dict[str, tuple[str, int]] = {}
    findings: list[Finding] = []
    for record in records:
        if record.event_type is not AuditEventType.REQUEST_PERFORMED or not record.case_id:
            continue
        if int(record.detail.get("status", 0)) >= 300:
            continue
        if record.object_ref.endswith("/proposals"):
            proposed[record.case_id] = (record.actor_ref, record.seq)
        elif record.object_ref.endswith("/approve"):
            earlier = proposed.get(record.case_id)
            if earlier is not None and earlier[0] == record.actor_ref:
                findings.append(
                    Finding(
                        rule_id="self_approval",
                        band=Band.HIGH,
                        subject_ref=record.actor_ref,
                        case_id=record.case_id,
                        summary=f"{record.actor_ref} proposed and approved the same plan",
                        evidence=(earlier[1], record.seq),
                    )
                )
    return findings


def money_without_proof(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """Money moved and no receipt followed within the window.

    Every executed fix ends in a Trust Receipt. One that did not is either a
    failure nobody noticed or a payment with nothing to show a customer.
    """
    grace = thresholds.window("assurance.receipt.grace")
    receipted = {
        record.case_id for record in records if record.event_type is AuditEventType.RECEIPT_ISSUED
    }
    return [
        Finding(
            rule_id="money_without_proof",
            band=Band.HIGH,
            case_id=record.case_id,
            summary=f"money moved on {record.case_id} with no receipt within {grace}",
            evidence=(record.seq,),
        )
        for record in records
        if record.event_type is AuditEventType.ACTION_EXECUTED
        and record.case_id
        and record.case_id not in receipted
        and now - record.occurred_at > grace
    ]


def brute_force(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """Failed sign-in codes above the threshold in the window."""
    minimum = thresholds.count("assurance.otp_failures.min_count")
    since = now - thresholds.window("assurance.otp_failures.window")
    failures = [
        record
        for record in _within(records, since=since)
        if record.event_type is AuditEventType.OTP_FAILED
    ]
    if len(failures) < minimum:
        return []
    return [
        Finding(
            rule_id="brute_force",
            band=Band.MEDIUM,
            summary=f"{len(failures)} failed sign-in codes within the window",
            evidence=tuple(record.seq for record in failures),
        )
    ]


def denial_spike(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """One account refused repeatedly: probing, or a broken integration."""
    minimum = thresholds.count("assurance.denials.min_count")
    since = now - thresholds.window("assurance.denials.window")
    by_actor: dict[str, list[int]] = defaultdict(list)
    for record in _within(records, since=since):
        if record.event_type is AuditEventType.ACCESS_DENIED:
            by_actor[record.actor_ref].append(record.seq)
    return [
        Finding(
            rule_id="denial_spike",
            band=Band.MEDIUM,
            subject_ref=actor,
            summary=f"{len(seqs)} refusals for {actor} within the window",
            evidence=tuple(seqs),
        )
        for actor, seqs in by_actor.items()
        if len(seqs) >= minimum
    ]


def mass_audit_read(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """Someone reading the trail far more than usual: rule 5 turned into a signal."""
    minimum = thresholds.count("assurance.audit_reads.min_count")
    since = now - thresholds.window("assurance.audit_reads.window")
    by_actor: dict[str, list[int]] = defaultdict(list)
    for record in _within(records, since=since):
        if record.event_type is AuditEventType.AUDIT_READ:
            by_actor[record.actor_ref].append(record.seq)
    return [
        Finding(
            rule_id="mass_audit_read",
            band=Band.HIGH,
            subject_ref=actor,
            summary=f"{len(seqs)} reads of the audit trail by {actor} within the window",
            evidence=tuple(seqs),
        )
        for actor, seqs in by_actor.items()
        if len(seqs) >= minimum
    ]


def break_glass_used(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """Break-glass is legitimate and always worth a second pair of eyes."""
    return [
        Finding(
            rule_id="break_glass_used",
            band=Band.HIGH,
            subject_ref=record.actor_ref,
            summary=(
                f"{record.actor_ref} took a break-glass audit duty: "
                f"{record.detail.get('reason', '')}"
            ),
            evidence=(record.seq,),
        )
        for record in records
        if record.event_type is AuditEventType.BREAK_GLASS_USED
    ]


def switch_then_pay(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """A kill switch turned off, money moved, the switch turned back on.

    Each step is ordinary. In that order, inside the window, it is the shape of
    someone stepping around a control and tidying up after themselves.
    """
    window = thresholds.window("assurance.switch_then_pay.window")
    overrides = [r for r in records if r.event_type is AuditEventType.OVERRIDE_RECORDED]
    findings: list[Finding] = []
    for index, off in enumerate(overrides):
        if off.detail.get("enabled") is not False:
            continue
        for on in overrides[index + 1 :]:
            if on.object_ref != off.object_ref or on.detail.get("enabled") is not True:
                continue
            if on.occurred_at - off.occurred_at > window:
                break
            moved = [
                record.seq
                for record in records
                if record.event_type is AuditEventType.ACTION_EXECUTED
                and off.occurred_at <= record.occurred_at <= on.occurred_at
            ]
            if moved:
                findings.append(
                    Finding(
                        rule_id="switch_then_pay",
                        band=Band.HIGH,
                        subject_ref=off.actor_ref,
                        summary=(
                            f"{off.object_ref} was turned off, {len(moved)} execution(s) "
                            f"followed, and it was turned back on"
                        ),
                        evidence=(off.seq, *moved, on.seq),
                    )
                )
            break
    return findings


#: Every rule, by id. Adding one here is all it takes for the service to run it.
RULES: dict[str, Rule] = {
    "structuring": structuring,
    "self_approval": self_approval,
    "money_without_proof": money_without_proof,
    "switch_then_pay": switch_then_pay,
    "break_glass_used": break_glass_used,
    "mass_audit_read": mass_audit_read,
    "denial_spike": denial_spike,
    "brute_force": brute_force,
}


__all__ = ["RULES", "Band", "Finding", "Rule", "Thresholds"]

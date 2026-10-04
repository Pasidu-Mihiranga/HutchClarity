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
from datetime import datetime, timedelta, timezone
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


#: Sri Lanka keeps UTC+5:30 all year and has had no daylight saving since 2006.
#: A fixed offset rather than a tzdata lookup, so the rule has no dependency a
#: deployment could be missing. **ASSUMPTION**, noted in the devlog.
COLOMBO = timezone(timedelta(hours=5, minutes=30))


def _local_hour(moment: datetime) -> float:
    """The hour of day in Colombo, as a fraction, so the half-hour offset shows."""
    local = moment.astimezone(COLOMBO)
    return local.hour + local.minute / 60


def _subject_of(record: AuditRecord) -> str | None:
    """The pseudonymous subscriber an event was about, where it names one.

    The envelope's ``subject`` carries it (``contracts.events``), and the
    container copies it into the detail. Never an MSISDN.
    """
    subject = record.detail.get("subject")
    return str(subject) if subject else None


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


def snooping(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """A staff account opening customer records it never did any work on.

    The shape of curiosity rather than work: an agent who reads twenty cases in
    an hour and touches none of them is not working a queue. "Assigned work" is
    proxied by a state-changing request on the same case by the same person
    inside the window, which is the only notion of assignment the trail carries;
    a reader who looked and then acted is doing the job and does not fire.

    Needs ``data.read``, which is why this rule could not exist before the
    middleware recorded staff reads of one subject (plan 5.5).
    """
    minimum = thresholds.count("assurance.snooping.min_cases")
    since = now - thresholds.window("assurance.snooping.window")
    recent = _within(records, since=since)

    read: dict[str, dict[str, int]] = defaultdict(dict)
    worked: dict[str, set[str]] = defaultdict(set)
    for record in recent:
        if not record.case_id:
            continue
        if record.event_type is AuditEventType.DATA_READ:
            read[record.actor_ref].setdefault(record.case_id, record.seq)
        elif record.event_type is AuditEventType.REQUEST_PERFORMED:
            worked[record.actor_ref].add(record.case_id)

    findings: list[Finding] = []
    for actor, seen in read.items():
        idle = {case: seq for case, seq in seen.items() if case not in worked[actor]}
        if len(idle) >= minimum:
            findings.append(
                Finding(
                    rule_id="snooping",
                    band=Band.MEDIUM,
                    subject_ref=actor,
                    summary=(
                        f"{actor} opened {len(idle)} customer records within the window "
                        "and did no work on any of them"
                    ),
                    evidence=tuple(sorted(idle.values())),
                )
            )
    return findings


def collusion(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """One subscriber paid across several cases inside the window.

    A customer with two genuine problems is ordinary. The same pseudonym
    collecting money on case after case, each opened and approved separately, is
    the shape of an account being farmed, whether by one person or by two who
    approve for each other. The finding names the approvers so an investigator
    sees at once whether it is one hand or several.

    Counted on the pseudonym, never on a number: the subject is a
    ``subscriber_ref`` (I13), and the rule needs nothing more than that two
    payments went to the same one.
    """
    minimum = thresholds.count("assurance.collusion.min_cases")
    since = now - thresholds.window("assurance.collusion.window")
    recent = _within(records, since=since)
    approvers = _approvers_by_case(recent)

    paid: dict[str, dict[str, int]] = defaultdict(dict)
    for record in recent:
        if record.event_type is not AuditEventType.ACTION_EXECUTED or not record.case_id:
            continue
        subject = _subject_of(record)
        if subject is None:
            continue
        paid[subject].setdefault(record.case_id, record.seq)

    findings: list[Finding] = []
    for subject, cases in paid.items():
        if len(cases) < minimum:
            continue
        hands = sorted({approvers[case][0] for case in cases if case in approvers})
        evidence = sorted(
            {*cases.values(), *(approvers[case][1] for case in cases if case in approvers)}
        )
        who = ", ".join(hands) if hands else "no human approver on record"
        findings.append(
            Finding(
                rule_id="collusion",
                band=Band.HIGH,
                subject_ref=hands[0] if len(hands) == 1 else None,
                summary=(
                    f"{len(cases)} cases paid money to {subject} within the window, "
                    f"approved by: {who}"
                ),
                evidence=tuple(evidence),
            )
        )
    return findings


def budget_pressure(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """More money moved in the window than compliance wants to learn about late.

    Not a second copy of the refund cap, which the decision policy enforces per
    case and the budget enforces per day: this is a compliance-owned figure for
    *how much in total* may move before someone is told, which is a different
    question with a different owner. A legitimate incident trips it, and should.
    """
    ceiling = thresholds.number("assurance.budget.window_alert_lkr")
    since = now - thresholds.window("assurance.budget.window")

    moved = Decimal("0")
    evidence: list[int] = []
    for record in _within(records, since=since):
        if record.event_type is not AuditEventType.ACTION_EXECUTED:
            continue
        amount = _money(record.detail.get("total_amount_lkr") or record.detail.get("amount_lkr"))
        if amount is None:
            continue
        moved += amount
        evidence.append(record.seq)

    if moved <= ceiling or not evidence:
        return []
    return [
        Finding(
            rule_id="budget_pressure",
            band=Band.HIGH,
            summary=(
                f"LKR {moved} moved across {len(evidence)} executions within the window, "
                f"above the LKR {ceiling} that compliance wants told"
            ),
            evidence=tuple(evidence),
        )
    ]


def off_hours(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """Money approved outside the hours the desk is supposed to be working.

    Deliberately **configured hours, not a learned baseline.** A baseline is a
    model, and a model that scores a person's working pattern as unusual is a
    guess wearing a number's clothes, which this module does not do (I1). Two
    numbers from the policy store, owned by whoever owns the roster, are
    something an investigator and the person investigated can both argue with.

    It fires on approvals and executions only. Reading a case at midnight is a
    late shift; approving a payout at midnight is a question.
    """
    opens = float(thresholds.number("assurance.off_hours.from_hour"))
    closes = float(thresholds.number("assurance.off_hours.to_hour"))
    minimum = thresholds.count("assurance.off_hours.min_count")
    since = now - thresholds.window("assurance.off_hours.window")

    watched = {AuditEventType.ACTION_EXECUTED, AuditEventType.REQUEST_PERFORMED}
    by_actor: dict[str, list[int]] = defaultdict(list)
    for record in _within(records, since=since):
        if record.event_type not in watched:
            continue
        if record.event_type is AuditEventType.REQUEST_PERFORMED and not (
            record.object_ref.endswith("/approve") or record.object_ref.endswith("/execute")
        ):
            continue
        hour = _local_hour(record.occurred_at)
        if opens <= hour < closes:
            continue
        by_actor[record.actor_ref].append(record.seq)

    return [
        Finding(
            rule_id="off_hours",
            band=Band.MEDIUM,
            subject_ref=actor,
            summary=(
                f"{len(seqs)} approval(s) or execution(s) by {actor} outside "
                f"{opens:g}:00-{closes:g}:00 Colombo time within the window"
            ),
            evidence=tuple(seqs),
        )
        for actor, seqs in by_actor.items()
        if len(seqs) >= minimum
    ]


def grant_abuse(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """An audit duty taken, used and given straight back.

    A grant exists so somebody can do a piece of work. One approved, read with,
    and revoked inside a few minutes was not work: it was a look, with the
    evidence of having had the access tidied away afterwards. The grant records
    survive that tidying, which is the point of them being in the trail rather
    than only in the grant table.
    """
    window = thresholds.window("assurance.grant_abuse.window")
    approved: dict[str, tuple[str, datetime, int]] = {}
    reads: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    for record in records:
        if record.event_type is AuditEventType.GRANT_APPROVED:
            subject = str(record.detail.get("subject", ""))
            approved[record.object_ref] = (subject, record.occurred_at, record.seq)
        elif record.event_type is AuditEventType.AUDIT_READ:
            reads[record.actor_ref].append((record.occurred_at, record.seq))

    findings: list[Finding] = []
    for record in records:
        if record.event_type is not AuditEventType.GRANT_REVOKED:
            continue
        earlier = approved.get(record.object_ref)
        if earlier is None:
            continue
        subject, approved_at, approved_seq = earlier
        if record.occurred_at - approved_at > window:
            continue
        holder = subject.split(":", 1)[-1]
        used = [seq for at, seq in reads.get(holder, []) if approved_at <= at <= record.occurred_at]
        if not used:
            continue
        findings.append(
            Finding(
                rule_id="grant_abuse",
                band=Band.HIGH,
                subject_ref=holder,
                summary=(
                    f"an audit duty for {subject} was approved, used {len(used)} time(s) "
                    f"and revoked again within {record.occurred_at - approved_at}"
                ),
                evidence=(approved_seq, *used, record.seq),
            )
        )
    return findings


def agent_pressure(
    records: Sequence[AuditRecord], thresholds: Thresholds, now: datetime
) -> list[Finding]:
    """An assistant whose proposals keep being refused.

    The LLM proposes and never executes (I1), so a refused proposal is the
    control working, not a breach. Many of them in a row is still worth a look:
    either a prompt is being steered towards something the rules will not do, or
    a rule pack and the assistant disagree about what is possible, and both are
    things to find out early rather than from a customer.
    """
    minimum = thresholds.count("assurance.agent_pressure.min_count")
    since = now - thresholds.window("assurance.agent_pressure.window")
    refused: dict[str, list[int]] = defaultdict(list)
    for record in _within(records, since=since):
        if record.event_type is not AuditEventType.MCP_INVOKED:
            continue
        outcome = str(record.detail.get("outcome", "")).lower()
        if outcome in {"denied", "refused", "rejected", "blocked"}:
            refused[record.actor_ref].append(record.seq)
    return [
        Finding(
            rule_id="agent_pressure",
            band=Band.MEDIUM,
            subject_ref=actor,
            summary=f"{len(seqs)} assistant proposals by {actor} were refused within the window",
            evidence=tuple(seqs),
        )
        for actor, seqs in refused.items()
        if len(seqs) >= minimum
    ]


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
    "snooping": snooping,
    "collusion": collusion,
    "budget_pressure": budget_pressure,
    "off_hours": off_hours,
    "grant_abuse": grant_abuse,
    "agent_pressure": agent_pressure,
}


__all__ = ["COLOMBO", "RULES", "Band", "Finding", "Rule", "Thresholds"]

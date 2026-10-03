"""Desk operations (D01, #26; plan 02 section 3.5).

A bulk fix is the most dangerous feature in the product: one operator deciding
that forty cases share a cause and fixing them in one action is what the deck
promises, and it is one mistake away from forty wrong refunds. So most of this
file is about refusals, and the ones that matter are not the obvious ones.

The obvious refusal is "the maker cannot approve their own batch", which is
acceptance 1. The one that makes it mean anything is that the approval is of a
specific **dry run**: a checker who approves "refund these 40 cases" and finds
80 executed has not approved what happened, and without that check four-eyes
approves a label.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from clarity.modules.deskops.public import (
    BatchStatus,
    BulkFixRefused,
    CasePreview,
    CaseResult,
    DeskCase,
    DeskOps,
    Eligibility,
    handover,
    merchant_watch,
    regulator_pack,
)

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
MAKER = "staff:desk-maker"
CHECKER = "staff:desk-checker"


@dataclass
class FakeFixer:
    """A tool layer stand-in that records what it was asked to do.

    `fix` is the single-case path. The real adapter calls
    `approve_and_execute`, which mints the confirmation token, enforces the
    per-case four-eyes and issues the one receipt that plan produces.
    """

    eligible: dict[str, str] = field(default_factory=dict)
    skipped: dict[str, Eligibility] = field(default_factory=dict)
    fixed: list[tuple[str, str, str]] = field(default_factory=list)
    fail: set[str] = field(default_factory=set)
    #: Set to simulate a case gaining or losing a plan between dry run and
    #: execution, which is the drift the fingerprint exists to catch.
    drift: dict[str, str] = field(default_factory=dict)

    def preview(self, case_id: str) -> CasePreview:
        self.eligible.update(self.drift)
        self.drift = {}
        if case_id in self.eligible:
            return CasePreview(
                case_id=case_id,
                eligibility=Eligibility.ELIGIBLE,
                plan_id=self.eligible[case_id],
                amount_lkr="49.00",
                outcome="ONE_TAP_FIX",
            )
        return CasePreview(
            case_id=case_id,
            eligibility=self.skipped.get(case_id, Eligibility.NO_PLAN),
        )

    def fix(self, case_id: str, plan_id: str, *, approver_ref: str, role: str) -> CaseResult:
        self.fixed.append((case_id, plan_id, approver_ref))
        if case_id in self.fail:
            return CaseResult(
                case_id=case_id, executed=False, plan_id=plan_id, error="adapter down"
            )
        return CaseResult(
            case_id=case_id,
            executed=True,
            plan_id=plan_id,
            receipt_id=f"RCPT-{case_id}",
        )


@dataclass
class FakeCases:
    rows: list[DeskCase] = field(default_factory=list)

    def recent(self, since: datetime):
        return [row for row in self.rows if row.opened_at >= since]


def desk(
    fixer: FakeFixer | None = None, cases: FakeCases | None = None
) -> tuple[DeskOps, FakeFixer]:
    used = fixer or FakeFixer(eligible={"C1": "PLAN-1", "C2": "PLAN-2", "C3": "PLAN-3"})
    return (
        DeskOps(fixer=used, cases=cases or FakeCases(), clock=lambda: NOW),
        used,
    )


# -- acceptance 1: a bulk fix by its maker alone is refused -------------- #


def test_the_maker_of_a_batch_cannot_approve_it():
    """D01 acceptance 1. The batch-level half of four-eyes."""
    ops, _fixer = desk()
    batch = ops.draft_bulk_fix(["C1", "C2"], reason="VAS no consent sweep", created_by=MAKER)
    assert batch.dry_run is not None

    with pytest.raises(BulkFixRefused, match="cannot approve"):
        ops.approve_bulk_fix(
            batch.batch_id,
            approver_ref=MAKER,
            role="desk",
            fingerprint=batch.dry_run.fingerprint,
        )


def test_a_batch_with_no_approval_cannot_execute():
    """Acceptance 1 by the other route: the maker simply executing it.

    Both are needed. Refusing the self-approval while letting an unapproved
    batch run would leave the gate bypassable by not asking.
    """
    ops, fixer = desk()
    batch = ops.draft_bulk_fix(["C1", "C2"], reason="sweep", created_by=MAKER)

    with pytest.raises(BulkFixRefused, match="no approval"):
        ops.execute_bulk_fix(batch.batch_id)

    assert fixer.fixed == [], "a case was fixed by an unapproved batch"


def test_a_second_person_can_approve_and_then_it_executes():
    """The other half, without which the module could refuse everything."""
    ops, fixer = desk()
    batch = ops.draft_bulk_fix(["C1", "C2"], reason="sweep", created_by=MAKER)
    assert batch.dry_run is not None

    ops.approve_bulk_fix(
        batch.batch_id,
        approver_ref=CHECKER,
        role="desk",
        fingerprint=batch.dry_run.fingerprint,
    )
    done = ops.execute_bulk_fix(batch.batch_id)

    assert done.status is BatchStatus.EXECUTED
    assert len(fixer.fixed) == 2
    assert sorted(done.receipts) == ["RCPT-C1", "RCPT-C2"]


def test_the_checker_is_carried_through_as_the_per_case_approver():
    """So the tool layer's own four-eyes applies to every case as well.

    A bulk fix is N ordinary fixes. If the batch passed a desk service account
    as the per-case approver instead, a batch could execute plans its own
    checker was not allowed to approve.
    """
    ops, fixer = desk()
    batch = ops.draft_bulk_fix(["C1"], reason="sweep", created_by=MAKER)
    assert batch.dry_run is not None
    ops.approve_bulk_fix(
        batch.batch_id, approver_ref=CHECKER, role="desk", fingerprint=batch.dry_run.fingerprint
    )

    ops.execute_bulk_fix(batch.batch_id)

    assert [approver for _case, _plan, approver in fixer.fixed] == [CHECKER]


# -- the approval is of a dry run, not of a batch id -------------------- #


def test_an_approval_for_a_different_dry_run_is_refused():
    """A checker approves what they were shown."""
    ops, _fixer = desk()
    batch = ops.draft_bulk_fix(["C1"], reason="sweep", created_by=MAKER)

    with pytest.raises(BulkFixRefused, match="changed since that dry run"):
        ops.approve_bulk_fix(
            batch.batch_id, approver_ref=CHECKER, role="desk", fingerprint="sha256:nonsense"
        )


def test_a_batch_that_grew_after_approval_will_not_execute():
    """The rule that makes four-eyes mean anything.

    A checker approved two cases. A third became eligible before execution, so
    executing now would do work nobody approved. Measured in cases, which is
    what the checker was counting.
    """
    fixer = FakeFixer(eligible={"C1": "PLAN-1", "C2": "PLAN-2"})
    ops, _ = desk(fixer)
    batch = ops.draft_bulk_fix(["C1", "C2", "C3"], reason="sweep", created_by=MAKER)
    assert batch.dry_run is not None
    assert len(batch.dry_run.eligible) == 2
    ops.approve_bulk_fix(
        batch.batch_id, approver_ref=CHECKER, role="desk", fingerprint=batch.dry_run.fingerprint
    )

    # C3 gains a plan between approval and execution.
    fixer.drift = {"C3": "PLAN-3"}

    with pytest.raises(BulkFixRefused, match="changed since it was approved"):
        ops.execute_bulk_fix(batch.batch_id)

    assert fixer.fixed == [], "work nobody approved was executed"


def test_the_fingerprint_covers_the_amount_as_well_as_the_case():
    """A re-decided amount is a different batch.

    Approving "refund 49 each" and executing 4900 each would be the same case
    list and a different thing entirely.
    """
    from clarity.modules.deskops.public import DryRun

    def run(amount: str) -> str:
        return DryRun(
            batch_id="BLK-1",
            previews=(
                CasePreview(
                    case_id="C1",
                    eligibility=Eligibility.ELIGIBLE,
                    plan_id="PLAN-1",
                    amount_lkr=amount,
                ),
            ),
            at=NOW,
        ).fingerprint

    assert run("49.00") != run("4900.00")


def test_the_fingerprint_ignores_case_order():
    """Otherwise an approval breaks when an unordered read comes back differently."""
    from clarity.modules.deskops.public import DryRun

    def run(*case_ids: str) -> str:
        return DryRun(
            batch_id="BLK-1",
            previews=tuple(
                CasePreview(
                    case_id=case_id,
                    eligibility=Eligibility.ELIGIBLE,
                    plan_id=f"PLAN-{case_id}",
                    amount_lkr="49.00",
                )
                for case_id in case_ids
            ),
            at=NOW,
        ).fingerprint

    assert run("C1", "C2") == run("C2", "C1")


# -- what a bulk fix may and may not do --------------------------------- #


def test_a_case_with_no_plan_is_skipped_not_invented():
    """The desk chooses which cases, never what to do to them.

    What may happen to a case was settled by its decision under the policy
    resolved as of its event (I1, D2). A batch that could propose an action
    would be a path from one operator's judgement to money moving in cases
    whose decisions never allowed it.
    """
    fixer = FakeFixer(
        eligible={"C1": "PLAN-1"},
        skipped={"C2": Eligibility.NOT_ALLOWED, "C3": Eligibility.NO_PLAN},
    )
    ops, _ = desk(fixer)

    batch = ops.draft_bulk_fix(["C1", "C2", "C3"], reason="sweep", created_by=MAKER)

    assert batch.dry_run is not None
    assert len(batch.dry_run.eligible) == 1
    skipped = {p.case_id: p.eligibility for p in batch.dry_run.previews if not p.would_execute}
    assert skipped == {"C2": Eligibility.NOT_ALLOWED, "C3": Eligibility.NO_PLAN}


def test_a_dry_run_executes_nothing():
    """It is named for what it is, and it has to behave that way."""
    ops, fixer = desk()

    batch = ops.draft_bulk_fix(["C1", "C2"], reason="sweep", created_by=MAKER)

    assert fixer.fixed == []
    assert batch.status is BatchStatus.DRAFTED
    assert batch.dry_run is not None
    assert batch.dry_run.to_dict()["executed"] is False


def test_a_partial_failure_is_reported_and_not_rolled_back():
    """Refunds that succeeded are customers who have their money.

    Unwinding them to make the batch look atomic would be a second
    unauthorised movement.
    """
    fixer = FakeFixer(eligible={"C1": "PLAN-1", "C2": "PLAN-2"}, fail={"C2"})
    ops, _ = desk(fixer)
    batch = ops.draft_bulk_fix(["C1", "C2"], reason="sweep", created_by=MAKER)
    assert batch.dry_run is not None
    ops.approve_bulk_fix(
        batch.batch_id, approver_ref=CHECKER, role="desk", fingerprint=batch.dry_run.fingerprint
    )

    done = ops.execute_bulk_fix(batch.batch_id)

    assert done.status is BatchStatus.EXECUTED
    results = {r.case_id: r for r in done.results}
    assert results["C1"].executed and results["C1"].receipt_id == "RCPT-C1"
    assert not results["C2"].executed and results["C2"].error
    assert done.receipts == ("RCPT-C1",), "a failed case produced a receipt"


def test_re_executing_a_batch_does_nothing_a_second_time():
    """One batch, one set of movements (I8)."""
    ops, fixer = desk()
    batch = ops.draft_bulk_fix(["C1"], reason="sweep", created_by=MAKER)
    assert batch.dry_run is not None
    ops.approve_bulk_fix(
        batch.batch_id, approver_ref=CHECKER, role="desk", fingerprint=batch.dry_run.fingerprint
    )
    ops.execute_bulk_fix(batch.batch_id)

    again = ops.execute_bulk_fix(batch.batch_id)

    assert len(fixer.fixed) == 1
    assert len(again.results) == 1


def test_one_receipt_per_case():
    """Plan 02 section 3.5. A batch is N fixes, so it is N receipts."""
    ops, _fixer = desk()
    batch = ops.draft_bulk_fix(["C1", "C2", "C3"], reason="sweep", created_by=MAKER)
    assert batch.dry_run is not None
    ops.approve_bulk_fix(
        batch.batch_id, approver_ref=CHECKER, role="desk", fingerprint=batch.dry_run.fingerprint
    )

    done = ops.execute_bulk_fix(batch.batch_id)

    assert len(done.receipts) == 3
    assert len(set(done.receipts)) == 3, "two cases shared a receipt"


def test_a_batch_bigger_than_a_person_can_read_is_refused():
    """A checker scrolling 5000 rows is rubber stamping.

    Not a performance limit: a batch nobody can read before approving is a
    batch nobody approved. A bigger remediation is several reviewed batches.
    """
    ops, _fixer = desk()

    with pytest.raises(BulkFixRefused, match="read"):
        ops.draft_bulk_fix([f"C{n}" for n in range(500)], reason="sweep", created_by=MAKER)


def test_a_batch_needs_a_reason():
    """It is what the checker is approving and what the audit will be asked about."""
    ops, _fixer = desk()

    with pytest.raises(BulkFixRefused, match="reason"):
        ops.draft_bulk_fix(["C1"], reason="   ", created_by=MAKER)


def test_the_same_approver_cannot_sign_off_twice():
    """Two signatures from one person is one signature."""
    ops, _fixer = desk()
    batch = ops.draft_bulk_fix(["C1"], reason="sweep", created_by=MAKER)
    assert batch.dry_run is not None
    fingerprint = batch.dry_run.fingerprint
    ops.approve_bulk_fix(batch.batch_id, approver_ref=CHECKER, role="desk", fingerprint=fingerprint)

    with pytest.raises(BulkFixRefused, match="already signed off"):
        ops.approve_bulk_fix(
            batch.batch_id, approver_ref=CHECKER, role="desk", fingerprint=fingerprint
        )


def test_duplicate_case_ids_are_collapsed():
    """Otherwise one case is fixed twice in a batch and counted twice."""
    ops, _fixer = desk()

    batch = ops.draft_bulk_fix(["C1", "C1", "C2"], reason="sweep", created_by=MAKER)

    assert batch.case_ids == ("C1", "C2")


def test_a_batch_survives_the_request_that_drafted_it():
    """An approval is worthless if it dies with the process that recorded it."""
    ops, _fixer = desk()
    batch = ops.draft_bulk_fix(["C1"], reason="sweep", created_by=MAKER)

    found = ops.batch(batch.batch_id)

    assert found is not None
    assert found.created_by == MAKER
    assert found.dry_run is not None


# -- merchant watch ------------------------------------------------------- #


def cases_for_watch() -> FakeCases:
    return FakeCases(
        rows=[
            DeskCase("C1", "s1", NOW, "ONE_TAP_FIX", "VAS_NO_CONSENT", ("MER-A",), "49.00", "R1"),
            DeskCase("C2", "s1", NOW, "ONE_TAP_FIX", "VAS_NO_CONSENT", ("MER-A",), "49.00", "R2"),
            DeskCase("C3", "s2", NOW, "EXPLAIN_ONLY", "FUP_CAP_REACHED", ("MER-B",)),
            DeskCase("C4", "s3", NOW, "HANDOFF", None, (), None, None, True),
        ]
    )


def test_a_merchant_score_shows_what_it_was_counted_from():
    """A score with no working is a number a desk cannot argue with.

    The weighting is a judgement, so a reader has to be able to disagree with
    the weighting rather than with the number.
    """
    ops, _fixer = desk(cases=cases_for_watch())

    scores = ops.merchant_watch()

    assert [s.merchant_id for s in scores] == ["MER-A", "MER-B"]
    top = scores[0].to_dict()
    assert top["counted_from"] == {
        "cases": 2,
        "no_consent": 2,
        "refunded": 2,
        "repeat_subscribers": 1,
    }
    assert top["weights"]
    assert top["measured"] is True


def test_a_repeat_subscriber_counts_for_more_than_two_unrelated_cases():
    """It is the shape of a merchant doing something systematic."""
    one_repeat = merchant_watch(
        [
            DeskCase("C1", "s1", NOW, None, None, ("MER-A",)),
            DeskCase("C2", "s1", NOW, None, None, ("MER-A",)),
        ]
    )
    two_people = merchant_watch(
        [
            DeskCase("C1", "s1", NOW, None, None, ("MER-A",)),
            DeskCase("C2", "s2", NOW, None, None, ("MER-A",)),
        ]
    )

    assert one_repeat[0].score > two_people[0].score


def test_the_watch_order_is_stable():
    """A desk reading the same window twice must see the same order."""
    rows = [
        DeskCase("C1", "s1", NOW, None, None, ("MER-B",)),
        DeskCase("C2", "s2", NOW, None, None, ("MER-A",)),
    ]

    assert [s.merchant_id for s in merchant_watch(rows)] == ["MER-A", "MER-B"]


# -- regulator pack ------------------------------------------------------- #


def test_the_regulator_pack_carries_no_personal_data():
    """A pack that carried identities would be a personal data export.

    A regulator asking "what did you do about unconsented charging" needs
    counts, causes and receipt ids. Every subscriber is an HMAC reference
    (I13).
    """
    ops, _fixer = desk(cases=cases_for_watch())

    pack = ops.regulator_pack(generated_by="desk-1").to_dict()

    assert pack["contains_personal_data"] is False
    body = repr(pack)
    assert "+9477" not in body and "077" not in body
    assert pack["cases"] == 4
    assert pack["by_cause"]["VAS_NO_CONSENT"] == 2
    assert sorted(pack["receipts"]) == ["R1", "R2"]


def test_the_pack_states_its_window_and_who_exported_it():
    """An export nobody can date or attribute is not evidence."""
    ops, _fixer = desk(cases=cases_for_watch())

    pack = ops.regulator_pack(generated_by="desk-1", span=timedelta(days=7)).to_dict()

    assert pack["generated_by"] == "desk-1"
    assert pack["window"]["from"] < pack["window"]["to"]
    assert pack["pack_id"].startswith("PACK-")
    assert "simulated" in pack["note"]


# -- shift handover ------------------------------------------------------- #


def test_the_handover_leads_with_what_somebody_must_do():
    """Ordered by what is outstanding, not by what happened most recently.

    A handover read top to bottom should let the next shift start on the oldest
    thing still waiting.
    """
    ops, _fixer = desk(cases=cases_for_watch())

    summary = ops.handover(prepared_by="desk-1").to_dict()

    assert summary["awaiting_person"] == ["C4"]
    assert summary["open_cases"] == 2
    assert summary["receipts"] == 2
    assert summary["prepared_by"] == "desk-1"


def test_the_handover_window_is_the_shift_and_not_everything():
    """An eight hour summary that included last week is not a handover."""
    old = DeskCase("OLD", "s9", NOW - timedelta(days=3), None, None, (), None, None, True)
    ops, _fixer = desk(cases=FakeCases(rows=[*cases_for_watch().rows, old]))

    summary = ops.handover(prepared_by="desk-1", span=timedelta(hours=8)).to_dict()

    assert "OLD" not in summary["awaiting_person"]


def test_a_handover_with_nothing_outstanding_says_so():
    """An empty list is a useful answer and must not read as missing data."""
    summary = handover(
        [DeskCase("C1", "s1", NOW, "EXPLAIN_ONLY", None, (), None, "R1")],
        shift_from=NOW - timedelta(hours=8),
        shift_to=NOW,
        prepared_by="desk-1",
    ).to_dict()

    assert summary["awaiting_person"] == []
    assert summary["open_cases"] == 0


def test_the_pack_and_the_handover_count_the_same_cases_the_same_way():
    """Two desk views disagreeing about one window is a desk that trusts neither."""
    rows = cases_for_watch().rows
    pack = regulator_pack(
        rows,
        window_from=NOW - timedelta(hours=8),
        window_to=NOW,
        generated_by="desk-1",
        now=NOW,
        pack_id="PACK-1",
    )
    shift = handover(rows, shift_from=NOW - timedelta(hours=8), shift_to=NOW, prepared_by="desk-1")

    assert pack.cases == len(rows)
    assert pack.by_outcome == shift.by_outcome
    assert len(pack.receipts) == shift.receipts


# -- against the real container ------------------------------------------ #


def real_desk():
    """The desk wired to the real case service and tool layer.

    The tests above use a fake fixer so the batch rules can be exercised in
    isolation. These use the real thing, because the claim that matters is not
    "the batch object refuses" but "money does not move", and only the real
    tool layer and the real world can show that.
    """
    from clarity.app.container import Clarity
    from clarity.integration.drivers.mock.world import build_demo_world, ref_for
    from clarity.kernel.common import Channel

    clarity = Clarity(world=build_demo_world())
    # One case per subscriber, which gives one case per outcome: the demo world
    # produces AUTO_FIX, ONE_TAP_FIX, STAFF_APPROVAL and EXPLAIN_ONLY. That
    # mix is the point rather than an inconvenience: a batch over a real
    # population contains cases it may not act on, and the preview has to say
    # which.
    cases: dict[str, str] = {}
    for account in clarity.world.accounts():
        case = clarity.cases.open_case(
            subscriber_ref=account.ref,
            msisdn_masked="077***4567",
            channel=Channel.APP,
            charge_ref=None,
        )
        clarity.cases.evaluate(case.case_id)
        record = clarity.cases.get(case.case_id)
        outcome = record.decision.outcome.value if record.decision else "none"
        # A plan has to exist before a batch can execute one: the desk chooses
        # which cases, never what to do to them. Proposed by the maker, which
        # also keeps the tool layer's per-case four-eyes live in these tests:
        # the checker approving the batch is not the maker who proposed.
        # EXPLAIN_ONLY and HANDOFF allow no action, which is the point: a real
        # population contains cases nothing can be proposed for.
        with contextlib.suppress(Exception):
            clarity.cases.propose(case.case_id, created_by=MAKER)
        cases[outcome] = case.case_id
    return clarity, ref_for("+94771234567"), cases


def test_a_real_bulk_fix_by_its_maker_alone_moves_no_money():
    """Acceptance 1, asserted on the world rather than on an exception.

    A refusal that raised while the refund had already gone out would satisfy
    `pytest.raises` and fail the customer. So this checks the balance and the
    receipt chain, which is the same standard the safety suite holds the
    assistant to.
    """
    clarity, subscriber, cases = real_desk()
    before = clarity.world.account(subscriber).balance_lkr
    receipts_before = len(clarity.receipts.issued())

    batch = clarity.desk.draft_bulk_fix(
        list(cases.values()), reason="VAS no consent sweep", created_by=MAKER
    )

    with pytest.raises(BulkFixRefused):
        clarity.desk.execute_bulk_fix(batch.batch_id)

    assert clarity.world.account(subscriber).balance_lkr == before, "a maker-only batch paid out"
    assert len(clarity.receipts.issued()) == receipts_before


def test_a_real_dry_run_moves_nothing_and_says_which_cases_it_would_skip():
    """A batch over a real population contains cases it may not act on.

    The preview has to say which, and the dry run has to change nothing.
    """
    clarity, _subscriber, cases = real_desk()
    balances = {account.ref: account.balance_lkr for account in clarity.world.accounts()}

    batch = clarity.desk.draft_bulk_fix(list(cases.values()), reason="sweep", created_by=MAKER)

    assert batch.dry_run is not None
    by_case = {p.case_id: p for p in batch.dry_run.previews}
    assert by_case[cases["AUTO_FIX"]].would_execute
    assert by_case[cases["STAFF_APPROVAL"]].would_execute
    # A one-tap fix is the customer's tap and the desk cannot mint their
    # confirmation token (ADR-0007), so it is skipped rather than executed.
    assert not by_case[cases["ONE_TAP_FIX"]].would_execute
    assert by_case[cases["ONE_TAP_FIX"]].eligibility is Eligibility.NOT_ALLOWED
    assert by_case[cases["EXPLAIN_ONLY"]].eligibility is Eligibility.NOT_ALLOWED
    assert {a.ref: a.balance_lkr for a in clarity.world.accounts()} == balances


def test_a_real_approved_batch_pays_out_once_per_case():
    """The other half: an approved batch does the work, exactly once.

    Without this the module could refuse everything and pass every test above.
    """
    clarity, _subscriber, cases = real_desk()
    receipts_before = len(clarity.receipts.issued())
    actionable = [cases["AUTO_FIX"], cases["STAFF_APPROVAL"]]
    before = {a.ref: a.balance_lkr for a in clarity.world.accounts()}

    batch = clarity.desk.draft_bulk_fix(actionable, reason="sweep", created_by=MAKER)
    assert batch.dry_run is not None
    clarity.desk.approve_bulk_fix(
        batch.batch_id,
        approver_ref=CHECKER,
        role="desk_supervisor",
        fingerprint=batch.dry_run.fingerprint,
    )

    done = clarity.desk.execute_bulk_fix(batch.batch_id)

    executed = [r for r in done.results if r.executed]
    assert len(executed) == 2, f"only {len(executed)} executed: {[r.error for r in done.results]}"
    assert len({r.receipt_id for r in executed}) == 2, "a receipt was shared between cases"
    assert len(clarity.receipts.issued()) == receipts_before + 2
    after = {a.ref: a.balance_lkr for a in clarity.world.accounts()}
    assert any(after[ref] > before[ref] for ref in before), "no money moved"


def test_re_executing_a_real_batch_pays_out_nothing_further():
    """I8: zero duplicate financial executions."""
    clarity, _subscriber, cases = real_desk()
    batch = clarity.desk.draft_bulk_fix(
        [cases["AUTO_FIX"], cases["STAFF_APPROVAL"]], reason="sweep", created_by=MAKER
    )
    assert batch.dry_run is not None
    clarity.desk.approve_bulk_fix(
        batch.batch_id,
        approver_ref=CHECKER,
        role="desk_supervisor",
        fingerprint=batch.dry_run.fingerprint,
    )
    clarity.desk.execute_bulk_fix(batch.batch_id)
    after_first = {a.ref: a.balance_lkr for a in clarity.world.accounts()}
    receipts_after_first = len(clarity.receipts.issued())

    clarity.desk.execute_bulk_fix(batch.batch_id)

    assert {a.ref: a.balance_lkr for a in clarity.world.accounts()} == after_first
    assert len(clarity.receipts.issued()) == receipts_after_first


def test_a_one_tap_case_is_never_bulk_executed():
    """The correction that cost a test run, recorded as a test.

    The first version of the desk adapter treated `ONE_TAP_FIX` as actionable
    and the tool layer refused every case with "a ONE_TAP_FIX decision is not
    a staff approval". It was right: a one-tap fix is the customer's tap, and
    executing it for them needs a token minted from that tap (ADR-0007).
    Remediating a population of those means getting them to tap or changing
    the policy that classified them, not a desk batch.
    """
    from clarity.app.desk import ACTIONABLE
    from clarity.contracts.decision import Outcome

    assert Outcome.ONE_TAP_FIX not in ACTIONABLE
    assert Outcome.EXPLAIN_ONLY not in ACTIONABLE
    assert Outcome.HANDOFF not in ACTIONABLE
    assert {Outcome.AUTO_FIX, Outcome.STAFF_APPROVAL} == ACTIONABLE

    clarity, _subscriber, cases = real_desk()
    before = {a.ref: a.balance_lkr for a in clarity.world.accounts()}
    batch = clarity.desk.draft_bulk_fix([cases["ONE_TAP_FIX"]], reason="sweep", created_by=MAKER)
    assert batch.dry_run is not None
    assert batch.dry_run.eligible == ()

    clarity.desk.approve_bulk_fix(
        batch.batch_id,
        approver_ref=CHECKER,
        role="desk_supervisor",
        fingerprint=batch.dry_run.fingerprint,
    )
    done = clarity.desk.execute_bulk_fix(batch.batch_id)

    assert done.results == []
    assert {a.ref: a.balance_lkr for a in clarity.world.accounts()} == before


def test_the_real_fixer_reads_the_amount_from_the_plan():
    """The figure a checker approves must be the figure that moves.

    Not formatted, not rounded, not recomputed from the decision: whatever the
    plan carries is what the preview prints (I3).
    """
    clarity, _subscriber, cases = real_desk()
    batch = clarity.desk.draft_bulk_fix(list(cases.values()), reason="sweep", created_by=MAKER)
    assert batch.dry_run is not None
    assert batch.dry_run.eligible, "nothing eligible, so this asserts nothing"

    for preview in batch.dry_run.eligible:
        record = clarity.cases.get(preview.case_id)
        plan = next(p for p in record.plans.values() if p.plan_id == preview.plan_id)
        assert preview.amount_lkr == str(plan.total_amount_lkr)

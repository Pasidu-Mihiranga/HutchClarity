"""Regression tests for defects D1-D4 (enterprise-plan 21 section 3).

Each test failed before its fix. They stay as guards for the migration (R3),
which moves the same guarantees into the database.
"""

from __future__ import annotations

import itertools
import shutil
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity, Profile
from clarity.integration.drivers.mock.world import build_demo_world, ref_for
from clarity.interfaces.http.main import create_app
from clarity.kernel.common import Channel
from clarity.modules.actions.results import ConfirmedBy
from clarity.modules.resolution.public import ResolutionService

from ..support.repositories import confirmations

DILANI = "+94771234567"  # VAS without consent: ONE_TAP_FIX, LKR 49
PRIYA = "+94774445555"  # LKR 12,000 reload, SIM swap: STAFF_APPROVAL
REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def racy() -> Iterator[None]:
    """Force frequent thread switches so races the GIL usually hides appear."""
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-7)
    yield
    sys.setswitchinterval(previous)


def _one_tap_case(clarity: Clarity) -> tuple[str, str]:
    case = clarity.cases.open_case(
        subscriber_ref=ref_for(DILANI), msisdn_masked="077***4567", channel=Channel.APP
    )
    clarity.cases.evaluate(case.case_id)
    plan = clarity.cases.propose(case.case_id, created_by="channel:web")
    return case.case_id, plan.plan_id


# --------------------------------------------------------------------- D1


def test_d1_a_second_tap_after_success_returns_the_original_receipt():
    clarity = Clarity(world=build_demo_world())
    case_id, plan_id = _one_tap_case(clarity)
    before = clarity.world.account(ref_for(DILANI)).balance_lkr

    first_result, first_receipt = clarity.cases.confirm_and_execute(case_id, plan_id)
    second_result, second_receipt = clarity.cases.confirm_and_execute(case_id, plan_id)

    assert second_receipt.receipt_id == first_receipt.receipt_id
    assert second_result.replayed and not first_result.replayed
    assert (
        clarity.world.account(ref_for(DILANI)).balance_lkr - before
        == first_result.actions[0].amount_lkr
    )


def test_d1_concurrent_double_tap_gives_one_refund_and_one_receipt(racy: None):
    for _ in range(60):
        clarity = Clarity(world=build_demo_world())
        case_id, plan_id = _one_tap_case(clarity)
        before = clarity.world.account(ref_for(DILANI)).balance_lkr
        receipts: list[str] = []
        errors: list[BaseException] = []

        def tap(
            cid: str = case_id,
            pid: str = plan_id,
            cases: ResolutionService = clarity.cases,
            sink: list[str] = receipts,
            failures: list[BaseException] = errors,
        ) -> None:
            try:
                sink.append(cases.confirm_and_execute(cid, pid)[1].receipt_id)
            except BaseException as error:
                failures.append(error)

        threads = [threading.Thread(target=tap) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert len(set(receipts)) == 1
        credited = clarity.world.account(ref_for(DILANI)).balance_lkr - before
        assert str(credited) == "49.00"


def test_d1_a_tap_that_confirms_before_the_winner_finishes_joins_it():
    """Regression: the loser of a double tap raised IllegalTransition.

    A plan stays PENDING until ``execute`` runs, so two taps can both mint a
    confirmation token. If the slower one then reaches the case state check
    after the faster one has finished, the case is already ACTIONED (or
    RECEIPTED), and the old test for ``is not EXECUTING`` made it attempt
    ACTIONED -> EXECUTING, which the state machine refuses.

    The threaded tests above hit this on a two-core CI runner and not on a
    developer machine, so this one forces the interleaving instead of racing
    for it: the first tap waits inside ``confirm_by_customer`` until the second
    has minted its token, and the second waits there until the first has
    finished the whole execution.
    """
    clarity = Clarity(world=build_demo_world())
    case_id, plan_id = _one_tap_case(clarity)
    before = clarity.world.account(ref_for(DILANI)).balance_lkr

    mint = clarity.tools.confirm_by_customer
    second_minted = threading.Event()
    winner_finished = threading.Event()
    minted = itertools.count()
    results: dict[str, object] = {}

    def gated_mint(*args: object, **kwargs: object) -> object:
        order = next(minted)
        token = mint(*args, **kwargs)  # type: ignore[arg-type]
        if order == 0:
            # Hold the winner until the loser also holds a token, which is the
            # window that makes two tokens exist for one plan.
            assert second_minted.wait(10), "the second tap never minted"
        else:
            second_minted.set()
            assert winner_finished.wait(10), "the first tap never finished"
        return token

    def winner() -> None:
        results["winner"] = clarity.cases.confirm_and_execute(case_id, plan_id)
        winner_finished.set()

    def loser() -> None:
        try:
            results["loser"] = clarity.cases.confirm_and_execute(case_id, plan_id)
        except BaseException as error:
            results["loser"] = error

    with patch.object(clarity.tools, "confirm_by_customer", gated_mint):
        threads = [threading.Thread(target=winner), threading.Thread(target=loser)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

    loser_outcome = results["loser"]
    assert not isinstance(loser_outcome, BaseException), f"the second tap failed: {loser_outcome!r}"
    assert isinstance(loser_outcome, tuple)
    winner_outcome = results["winner"]
    assert isinstance(winner_outcome, tuple)
    assert loser_outcome[1].receipt_id == winner_outcome[1].receipt_id, "one plan, one receipt"
    credited = clarity.world.account(ref_for(DILANI)).balance_lkr - before
    assert str(credited) == "49.00", "the refund moved more than once"


def test_d1_fifteen_hundred_concurrent_confirms_give_one_refund_and_one_receipt(racy: None):
    """The B06 acceptance case: the per-plan lock is gone, the guarantee is not.

    Idempotency now comes from three places instead of one lock: the tool
    layer's idempotency key gives one execution, the receipt's plan index gives
    one receipt, and a caller that loses the race to confirm joins the winner's
    outcome rather than failing. 1,500 simultaneous taps must still move LKR
    49.00 once and produce a single receipt.
    """
    clarity = Clarity(world=build_demo_world())
    case_id, plan_id = _one_tap_case(clarity)
    before = clarity.world.account(ref_for(DILANI)).balance_lkr

    taps = 1500
    start = threading.Barrier(taps)
    receipts: list[str] = []
    errors: list[BaseException] = []
    guard = threading.Lock()

    def tap() -> None:
        try:
            start.wait()
            receipt_id = clarity.cases.confirm_and_execute(case_id, plan_id)[1].receipt_id
            with guard:
                receipts.append(receipt_id)
        except BaseException as error:
            with guard:
                errors.append(error)

    threads = [threading.Thread(target=tap) for _ in range(taps)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == [], f"{len(errors)} of {taps} taps failed, first: {errors[:1]}"
    assert len(receipts) == taps, "every tap must get an answer"
    assert len(set(receipts)) == 1, f"{len(set(receipts))} receipts were issued for one plan"
    credited = clarity.world.account(ref_for(DILANI)).balance_lkr - before
    assert str(credited) == "49.00", "the refund moved more than once"
    assert clarity.receipts.verify_chain(), "the receipt chain must stay intact"


def test_d1_minting_while_redeeming_never_breaks_redemption(racy: None):
    service = confirmations()
    target = service.mint("PLAN-X", confirmed_by=ConfirmedBy.CUSTOMER, principal_ref="s")
    stop = threading.Event()

    def mint_forever() -> None:
        while not stop.is_set():
            service.mint("PLAN-Y", confirmed_by=ConfirmedBy.CUSTOMER, principal_ref="s")

    minter = threading.Thread(target=mint_forever)
    minter.start()
    try:
        redeemed = service.redeem(target.value, plan_id="PLAN-X")
    finally:
        stop.set()
        minter.join()

    assert redeemed.plan_id == "PLAN-X"


# --------------------------------------------------------------------- D2


def test_d2_the_four_eyes_threshold_comes_from_policy(tmp_path: Path):
    """Finance lowers the threshold to LKR 10,000: a LKR 12,000 case needs two people."""
    # The whole directory, not one file: the decision module also loads its
    # outcome table from here (M-DEC), so a partial copy leaves it with no table.
    policy = tmp_path / "policy"
    shutil.copytree(REPO / "config" / "policy", policy)
    text = (policy / "decision.yaml").read_text(encoding="utf-8")
    key = text.index("decision.four_eyes.threshold_lkr")
    value = text.index('"25000.00"', key)
    (policy / "decision.yaml").write_text(
        text[:value] + '"10000.00"' + text[value + len('"25000.00"') :], encoding="utf-8"
    )
    clarity = Clarity(world=build_demo_world(), policy_dir=policy)

    case = clarity.cases.open_case(
        subscriber_ref=ref_for(PRIYA), msisdn_masked="077***5555", channel=Channel.APP
    )
    decision = clarity.cases.evaluate(case.case_id)
    assert decision.outcome.value == "STAFF_APPROVAL"
    plan = clarity.cases.propose(case.case_id, created_by="agent:nadeesha")

    first = clarity.cases.approve_and_execute(
        case.case_id, plan.plan_id, approver_ref="sup:ruwan", role="supervisor"
    )
    assert first is None, "one approval must not be enough above the policy threshold"

    second = clarity.cases.approve_and_execute(
        case.case_id, plan.plan_id, approver_ref="fin:kamala", role="finance"
    )
    assert second is not None and second[0].succeeded


# --------------------------------------------------------------------- D3


def test_d3_development_staff_sign_in_never_exists_in_production():
    """The password-free role picker is for synthetic profiles only.

    The team's rule (2026-10-02): DEMO and FULL both run synthetic HUTCH data,
    so development identity routes are allowed there and refused in PROD.
    """
    clarity = Clarity(world=build_demo_world())
    client = TestClient(create_app(clarity))
    body = {"user_ref": "sup:ruwan", "roles": ["supervisor"], "step_up": True}
    assert client.post("/v1/auth/staff/session", json=body).status_code == 200

    clarity.profile = Profile.PROD

    assert client.post("/v1/auth/staff/session", json=body).status_code == 404


# --------------------------------------------------------------------- D4


def test_d4_the_receipt_names_the_roles_that_actually_approved(tmp_path: Path):
    clarity = Clarity(world=build_demo_world())
    case = clarity.cases.open_case(
        subscriber_ref=ref_for(PRIYA), msisdn_masked="077***5555", channel=Channel.APP
    )
    clarity.cases.evaluate(case.case_id)
    plan = clarity.cases.propose(case.case_id, created_by="agent:nadeesha")

    outcome = clarity.cases.approve_and_execute(
        case.case_id, plan.plan_id, approver_ref="fin:kamala", role="finance"
    )

    assert outcome is not None
    assert outcome[1].payload.actor.approver_role == "finance"


# ----------------------------------------------------------- merge (dev)


def test_lite_is_accepted_as_the_documented_name_of_the_demo_profile():
    """The plan, ADR-0027 and .env.example say ``lite``; the code calls it ``demo``."""
    assert Profile("lite") is Profile.DEMO
    assert Profile("demo") is Profile.DEMO

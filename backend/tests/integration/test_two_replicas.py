"""Two processes on one database (issue #6, B05; acceptance 3).

The reason B05 exists. Every idempotency guarantee the prototype had was held by
a process-local lock or dict, so a second replica would have broken it silently:
two refunds, two receipts, and nothing in the logs to say why.

These run two real OS processes against one PostgreSQL, which is the only way to
show that the guarantee now lives in the database rather than in a thread lock.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from clarity.contracts.decision import ActionType, Decision, Outcome
from clarity.kernel.common import money
from clarity.modules.actions.attempts import ATTEMPTS
from clarity.platform.persistence.postgres import PostgresStore
from clarity.platform.persistence.schemas import APP_ROLE

PLANS = "actions.plans"
PLAN_TABLE = "clarity_actions.plans"

#: Each worker runs this: claim one plan id, report whether it won.
#:
#: It models what two API replicas do when the same customer taps Confirm twice
#: and the taps land on different processes. The claim is a conditional insert,
#: which is the shape M-ACT will use for the real plan row.
WORKER = """
import json, sys, time
from sqlalchemy import create_engine, text
from clarity.platform.persistence.postgres import PostgresStore
from clarity.platform.persistence.errors import ConcurrentUpdate

url, plan_count, worker = sys.argv[1], int(sys.argv[2]), sys.argv[3]
engine = create_engine(url, future=True)
store = PostgresStore(engine)

# Start together, or there is no contention to measure. Without this the
# first process spawned can claim every plan before the second has finished
# importing, and then the test fails on its own "both replicas did work"
# guard rather than on anything about correctness.
with store.unit() as unit:
    unit.repository("actions.plans").put(f"BARRIER-{worker}", {"ready": True})
    unit.commit()
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    with store.unit() as unit:
        ready = unit.repository("actions.plans")
        if all(ready.get(f"BARRIER-{name}") for name in ("replica-a", "replica-b")):
            break
    time.sleep(0.01)
else:
    raise SystemExit(f"{worker}: the other replica never arrived at the barrier")

# Opposite directions, so the two replicas meet in the middle whatever their
# relative speed. Both walking 0..n-1 made contention a matter of timing: on a
# two-core runner one replica finished the whole range before the other got
# going, won all 500, and the test failed its own "both did work" guard while
# every correctness assertion passed. The barrier above syncs the start; it
# cannot sync the pace.
order = range(plan_count) if worker == "replica-a" else range(plan_count - 1, -1, -1)

won = []
for index in order:
    plan_id = f"PLAN-{index:04d}"
    try:
        with store.unit() as unit:
            plans = unit.repository("actions.plans")
            if plans.get(plan_id) is None:
                plans.put(plan_id, {"plan_id": plan_id, "executed_by": worker})
                unit.commit()
                won.append(plan_id)
    except ConcurrentUpdate:
        # The other replica claimed it first. Exactly the outcome wanted: this
        # process does not execute the plan.
        pass
engine.dispose()
print(json.dumps({"worker": worker, "won": won}))
"""


def _run_two_replicas(url: str, plan_count: int) -> list[dict[str, object]]:
    script = Path(os.environ.get("TMPDIR", "/tmp")) / "clarity_replica_worker.py"
    script.write_text(WORKER, encoding="utf-8")
    processes = [
        subprocess.Popen(
            [sys.executable, str(script), url, str(plan_count), name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for name in ("replica-a", "replica-b")
    ]
    results: list[dict[str, object]] = []
    for process in processes:
        out, err = process.communicate(timeout=300)
        assert process.returncode == 0, f"a replica failed: {err}"
        results.append(json.loads(out.strip().splitlines()[-1]))
    return results


# -- acceptance 3 --------------------------------------------------------- #


def test_two_processes_each_plan_is_claimed_exactly_once(engine: Engine) -> None:
    """1,000 contended claims across two processes: no plan is claimed twice."""
    url = str(engine.url.render_as_string(hide_password=False))
    plan_count = 500  # 500 plans, two replicas each attempting all of them

    results = _run_two_replicas(url, plan_count)

    claimed = [plan for result in results for plan in result["won"]]  # type: ignore[union-attr]
    assert len(claimed) == len(set(claimed)), "a plan was claimed by both replicas"
    assert sorted(set(claimed)) == [f"PLAN-{i:04d}" for i in range(plan_count)], (
        "every plan must be claimed by exactly one replica"
    )

    # And the database agrees: one row per plan, no duplicates.
    with engine.begin() as connection:
        connection.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
        rows = connection.execute(
            text(f"SELECT count(*), count(DISTINCT key) FROM {PLAN_TABLE} WHERE key LIKE 'PLAN-%'")
        )
        total, distinct = rows.one()
    assert total == plan_count
    assert distinct == plan_count

    # Both replicas did real work, or the test proved nothing about contention.
    # They walk the range in opposite directions, so they collide around the
    # midpoint however fast each one is: this is a structural guarantee, not a
    # hope about scheduling.
    per_replica = {result["worker"]: len(result["won"]) for result in results}  # type: ignore[arg-type]
    assert all(count > 0 for count in per_replica.values()), (
        f"one replica claimed nothing, so there was no contention: {per_replica}"
    )


def test_a_second_process_sees_the_first_processes_committed_row(store: PostgresStore) -> None:
    """The baseline this all rests on: state is shared, not per process."""
    with store.unit() as unit:
        # The id the workers try to claim, so "already there" is what they meet.
        unit.repository(PLANS).put("PLAN-0000", {"plan_id": "PLAN-0000"})
        unit.commit()

    url = str(store.engine.url.render_as_string(hide_password=False))
    results = _run_two_replicas(url, 1)

    # Neither replica claims it: both already see it committed.
    assert all(result["won"] == [] for result in results)


@pytest.mark.parametrize("attempt", range(3))
def test_the_claim_is_stable_under_repetition(engine: Engine, attempt: int) -> None:
    """Run the race a few times: a flaky guarantee is not a guarantee."""
    url = str(engine.url.render_as_string(hide_password=False))
    results = _run_two_replicas(url, 40)
    claimed = [plan for result in results for plan in result["won"]]  # type: ignore[union-attr]
    assert len(claimed) == len(set(claimed)) == 40


# -- M-ACT acceptance 2: one execution across two replicas ---------------- #

#: Two replicas race to execute one plan through the real tool layer.
#:
#: Unlike the claim probe above, this goes through ``ToolLayer.execute``, so the
#: thing under test is the durable attempt record (M-ACT) rather than a bare
#: repository insert. Both replicas hold a valid confirmation for the same plan
#: and the same idempotency key, which is what a customer tapping Confirm twice
#: against a load balancer produces.
EXECUTOR = """
import json, sys
from decimal import Decimal
from sqlalchemy import create_engine
from clarity.app.collections import ALL_COLLECTIONS
from clarity.modules.actions.capability import (
    PLANS, RefundBudget, StoredPlanRepository, ToolLayer,
)
from clarity.modules.actions.errors import ToolLayerError
from clarity.platform.persistence.postgres import PostgresAutocommitRepository, PostgresStore

url, plan_id, token, key, worker = sys.argv[1:6]
engine = create_engine(url, future=True)
store = PostgresStore(engine)

# A replica builds its own tool layer over the shared database, which is the
# point: nothing is shared in the process.
from clarity.integration.drivers.mock.adapters import MockCommandAdapter
from clarity.integration.drivers.mock.world import build_demo_world
tools = ToolLayer(
    MockCommandAdapter(build_demo_world()),
    plans=StoredPlanRepository(PostgresAutocommitRepository(store, PLANS)),
    open_unit=store.unit,
    budget=RefundBudget(daily_limit_lkr="100000.00"),
    duplicate_wait_seconds=30.0,
)

outcome = {"worker": worker}
try:
    result = tools.execute(plan_id, confirmation=token, idempotency_key=key)
    outcome["status"] = result.status.value
    outcome["replayed"] = bool(result.replayed)
    outcome["amount"] = str(sum((a.amount_lkr or Decimal("0")) for a in result.actions))
except ToolLayerError as refusal:
    outcome["refused"] = refusal.code
engine.dispose()
print(json.dumps(outcome))
"""


def _run_executors(url: str, plan_id: str, token: str, key: str) -> list[dict[str, object]]:
    script = Path(os.environ.get("TMPDIR", "/tmp")) / "clarity_executor_worker.py"
    script.write_text(EXECUTOR, encoding="utf-8")
    processes = [
        subprocess.Popen(
            [sys.executable, str(script), url, plan_id, token, key, name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for name in ("replica-a", "replica-b")
    ]
    results: list[dict[str, object]] = []
    for process in processes:
        out, err = process.communicate(timeout=300)
        assert process.returncode == 0, f"a replica failed: {err}"
        results.append(json.loads(out.strip().splitlines()[-1]))
    return results


def test_two_replicas_executing_one_plan_execute_it_once(store: PostgresStore) -> None:
    """Concurrent execution of one plan from two processes: one refund.

    The guarantee used to be a dict in one process, so a second replica would
    have refunded again with nothing in the logs to say why. It now rests on the
    attempt record's unique key in PostgreSQL (M-ACT).

    Three mechanisms enforce this and each one alone is sufficient: the durable
    attempt claim, the single-use confirmation record, and the plan's status. So
    this test pins the guarantee rather than any one of them, which is the
    intended shape on a money path. Disabling one and watching the test still
    pass means the other two held, not that the test is vacuous.
    """
    from clarity.integration.drivers.mock.adapters import MockCommandAdapter
    from clarity.integration.drivers.mock.world import build_demo_world, ref_for
    from clarity.modules.actions.capability import (
        PLANS,
        RefundBudget,
        StoredPlanRepository,
        ToolLayer,
    )
    from clarity.platform.persistence.postgres import PostgresAutocommitRepository

    world = build_demo_world()
    subscriber = ref_for("+94781234567")
    tools = ToolLayer(
        MockCommandAdapter(world),
        plans=StoredPlanRepository(PostgresAutocommitRepository(store, PLANS)),
        open_unit=store.unit,
        budget=RefundBudget(daily_limit_lkr="100000.00"),
    )
    plan = tools.propose(
        _a_refund_decision(),
        subscriber_ref=subscriber,
        created_by="agent-1",
        params={ActionType.REFUND: {}},
    )
    token = tools.confirm_by_customer(plan.plan_id, subscriber_ref=subscriber)

    url = str(store.engine.url.render_as_string(hide_password=False))
    results = _run_executors(url, plan.plan_id, token.value, f"case:{plan.plan_id}")

    executed = [r for r in results if r.get("status") == "COMPLETED" and not r.get("replayed")]
    replayed = [r for r in results if r.get("replayed")]

    assert len(executed) == 1, f"the plan executed {len(executed)} times: {results}"
    assert len(replayed) == 1, f"the duplicate did not replay the original: {results}"
    assert executed[0]["amount"] == replayed[0]["amount"], "the replay reported a different amount"

    # One attempt record, settled once.
    with store.unit() as unit:
        attempts = unit.repository(ATTEMPTS)
        assert len(attempts.keys()) == 1


def _a_refund_decision() -> Decision:
    """A decision that authorises one refund, as the decision policy would."""
    return Decision(
        decision_id="DEC-REPLICA",
        case_id="CASE-REPLICA",
        outcome=Outcome.ONE_TAP_FIX,
        policy_version="test.1",
        input_hash="sha256:test",
        allowed_actions=[ActionType.REFUND],
        amount_lkr=money("49.00"),
        top_cause_ref="VAS_NO_CONSENT@4",
        handoff_reason=None,
    )

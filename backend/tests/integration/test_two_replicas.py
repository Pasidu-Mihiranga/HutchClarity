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
import json, sys
from sqlalchemy import create_engine, text
from clarity.platform.persistence.postgres import PostgresStore
from clarity.platform.persistence.errors import ConcurrentUpdate

url, plan_count, worker = sys.argv[1], int(sys.argv[2]), sys.argv[3]
engine = create_engine(url, future=True)
store = PostgresStore(engine)
won = []
for index in range(plan_count):
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
        rows = connection.execute(text(f"SELECT count(*), count(DISTINCT key) FROM {PLAN_TABLE}"))
        total, distinct = rows.one()
    assert total == plan_count
    assert distinct == plan_count

    # Both replicas did real work, or the test proved nothing about contention.
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

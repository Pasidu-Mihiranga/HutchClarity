"""No module keeps business state outside a repository (issue #5, B02).

State an instance attribute holds dies with the process and is invisible to
every other replica, so a module that keeps a dict of cases or plans cannot be
deployed twice or recovered after a restart. The seam that fixes it is
``clarity.platform.persistence``: state goes in a repository, and the profile
chooses the driver.

This test reads the source rather than the running object, so it catches a new
collection the moment it is written.
"""

from __future__ import annotations

import ast
from pathlib import Path

import clarity

MODULES = Path(clarity.__file__).parent / "modules"

#: Attribute names whose value is in-flight coordination, not business state.
#: Each one must say in a comment why it cannot live in a repository.
COORDINATION = frozenset(
    {
        "_lock",
        "_locks",
        "_plan_locks",
        "_attempts",
    }
)

#: Caches of data a remote system owns, keyed by an id that system issued.
#:
#: Not business state: losing one costs a round trip, not a fact. A JWKS cache
#: that had to survive a restart would mean Clarity was the system of record for
#: somebody else's signing keys, which is the opposite of what these do.
REMOTE_CACHES = frozenset(
    {
        "_keys",
        "_public",
    }
)

#: Attributes that hold injected collaborators or configuration, not state.
#: A mapping of configuration is fine: it is read, never accumulated.
CONFIGURATION = frozenset(
    {
        "_per_rule",
        "_packs",
        "_rules",
        "_templates",
        "_thresholds",
        "_params",
    }
)

#: State B02 did not move, and the issue that owns moving it. Each entry is a
#: known limitation, not an exemption: the module is still single-process until
#: its issue lands. A new collection that is in neither map fails this test.
DEFERRED: dict[str, str] = {
    # The daily refund ceiling. M-ACT moved idempotency and confirmation tokens
    # to the database; the counters are the remaining piece, and they need a
    # conditional UPDATE rather than a repository put to stop two replicas
    # overspending the same allowance. Tracked on M-ACT's follow-up.
    "actions/budget.py:_reservations": "#25 M-ACT (counters remain)",
}


def _collection_attributes(path: Path) -> list[str]:
    """Attributes a module assigns an empty dict, list or set to in ``__init__``."""
    found: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "__init__":
            continue
        for statement in ast.walk(node):
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(statement, ast.Assign):
                targets, value = list(statement.targets), statement.value
            elif isinstance(statement, ast.AnnAssign):
                targets, value = [statement.target], statement.value
            if value is None:
                continue
            is_empty_collection = (
                isinstance(value, ast.Dict | ast.List | ast.Set)
                and not getattr(value, "keys", [])
                and not getattr(value, "elts", [])
            ) or (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id in {"dict", "list", "set"}
                and not value.args
            )
            if not is_empty_collection:
                continue
            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    found.append(target.attr)
    return found


def test_no_module_accumulates_business_state_in_an_attribute() -> None:
    offenders: dict[str, list[str]] = {}
    for path in sorted(MODULES.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = str(path.relative_to(MODULES))
        kept = [
            attribute
            for attribute in _collection_attributes(path)
            if attribute not in COORDINATION
            and attribute not in CONFIGURATION
            and attribute not in REMOTE_CACHES
            and f"{relative}:{attribute}" not in DEFERRED
        ]
        if kept:
            offenders[relative] = sorted(kept)
    assert offenders == {}, (
        "these attributes accumulate state in the process: move them into a "
        "repository (clarity.platform.persistence), or record the attribute in "
        "DEFERRED against the issue that owns moving it"
    )


def test_every_deferral_still_exists() -> None:
    """A deferral that no longer applies is removed, so the map cannot rot."""
    stale = [
        entry
        for entry in DEFERRED
        if (lambda f, a: a not in _collection_attributes(MODULES / f))(*entry.rsplit(":", 1))
    ]
    assert stale == [], "these deferrals are fixed: delete them from DEFERRED"


def test_the_services_that_held_dicts_now_take_repositories() -> None:
    """The four collections B02 names are injected, not built in the service."""
    from clarity.modules.actions.capability import ToolLayer
    from clarity.modules.case.public import CaseAggregate
    from clarity.modules.governance.public import PolicyGovernance
    from clarity.modules.receipts.public import ReceiptService

    required = {
        CaseAggregate: "cases",
        ToolLayer: "plans",
        ReceiptService: "ledger",
        PolicyGovernance: "changes",
    }
    for service, parameter in required.items():
        annotations = service.__init__.__annotations__
        assert parameter in annotations, f"{service.__name__} must take {parameter!r}"

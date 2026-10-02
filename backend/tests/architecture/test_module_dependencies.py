"""Module dependency map (ADR-0029, enterprise-plan 21 section 11).

Synchronous calls between modules are allowed only along the edges declared
here. Everything else between modules is an event through the outbox. A new
edge is an architecture decision: add it here *and* to plan 21 section 11.2 in
the same change, or publish an event instead.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

import clarity

MODULES = Path(clarity.__file__).parent / "modules"

#: module -> modules it may call through their public surface (synchronous).
ALLOWED: dict[str, set[str]] = {
    # Orchestration (M-CASE, plan 21 section 2.2). Every edge out of the domain
    # starts here, which is what makes `case` a leaf.
    "resolution": {"case", "timeline", "detection", "decision", "actions", "receipts"},
    # `case` calls nothing. These are the types its aggregate record *holds*:
    # the evaluation detection produced, the thresholds decision used, the
    # execution actions returned, the receipt that proves it. This test reads
    # imports, which cannot tell naming a type from calling a function, so the
    # edges are declared. Moving those four types down to `clarity.contracts`,
    # where ADR-0029 section 4 says shared vocabulary belongs, would make `case`
    # a leaf in the file as well as in behaviour; that is the follow-up.
    "case": {"actions", "decision", "detection", "receipts"},
    "decision": {"detection"},
    "governance": {"decision"},
    "receipts": {"actions"},
    "timeline": set(),
    "detection": set(),
    "actions": set(),
    "iam": set(),
    "conversation": set(),
    "autopsy": set(),
    "foresight": set(),
    # scaffold modules: no synchronous calls declared yet
    "content": set(),
    "customer": set(),
    "deskops": set(),
    "insights": set(),
    "knowledge": set(),
    "notifications": set(),
    "proactive": set(),
    "reconciliation": set(),
}


def actual_dependencies() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for path in MODULES.rglob("*.py"):
        me = path.relative_to(MODULES).parts[0]
        graph.setdefault(me, set())
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if parts[:2] == ["clarity", "modules"] and len(parts) > 2 and parts[2] != me:
                    graph[me].add(parts[2])
    return dict(graph)


def test_every_module_is_in_the_map():
    modules = {p.name for p in MODULES.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert modules == set(ALLOWED), "declare each module's dependencies in ALLOWED"


def test_modules_call_only_their_declared_dependencies():
    undeclared = {
        module: sorted(deps - ALLOWED.get(module, set()))
        for module, deps in actual_dependencies().items()
        if deps - ALLOWED.get(module, set())
    }
    assert undeclared == {}, "undeclared module calls: declare the edge or publish an event"


def test_the_declared_map_has_no_cycles():
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(module: str, trail: tuple[str, ...]) -> None:
        assert module not in visiting, f"cycle: {' -> '.join((*trail, module))}"
        if module in done:
            return
        visiting.add(module)
        for dependency in ALLOWED[module]:
            visit(dependency, (*trail, module))
        visiting.discard(module)
        done.add(module)

    for module in ALLOWED:
        visit(module, ())

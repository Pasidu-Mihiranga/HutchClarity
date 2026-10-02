# [M-ACT] Actions: database idempotency, row locks, approval.requested, retry after transient failure

| Field | Value |
|---|---|
| Wave | W1 Core modules on the baseline |
| Area | `actions` |
| Priority | P0 |
| Depends on | [B05](B05-postgresql-repositories-schema-and-role-per-modu.md), [B04](B04-outbox-in-the-unit-of-work-relay-and-consumer-fr.md) |
| Plan | 21 §11.5, ADR-0005 |
| Labels | `wave:w1`, `area:actions`, `priority:p0`, `type:feature` |

## Context
Idempotency and plan status use in-process locks; a transient failure makes a plan's key final forever (stuck plan).

## Scope
- Idempotency as a unique key in PostgreSQL; plan status changes under row locks
- Distinguish definitive refusals (final) from transient adapter errors (retryable with a new attempt number)
- Publish `approval.requested@v1`, `action.completed@v1`, `action.failed@v1`

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a budget exhausted today | budget resets and the plan is retried | it executes once | `backend/tests/unit/test_tool_layer.py` |
| 2 | two API replicas | concurrent approve and confirm on one plan | exactly one execution | `backend/tests/integration/test_two_replicas.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

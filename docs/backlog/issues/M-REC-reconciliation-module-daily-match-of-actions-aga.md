# [M-REC] Reconciliation module: daily match of actions against adapter confirmations

| Field | Value |
|---|---|
| Wave | W1 Core modules on the baseline |
| Area | `reconciliation` |
| Priority | P2 |
| Depends on | [B04](B04-outbox-in-the-unit-of-work-relay-and-consumer-fr.md) |
| Plan | 09 §14.4 |
| Labels | `wave:w1`, `area:reconciliation`, `priority:p2`, `type:feature` |

## Context
No reconciliation exists.

## Scope
- New module consuming `action.completed`; daily job compares with adapter confirmations
- Publish `reconciliation.mismatch@v1`; finance queue view

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | an action with no adapter confirmation | the daily job runs | a mismatch event is published | `backend/tests/unit/test_reconciliation.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
- [ ] New module registered in the dependency map, modules.md, ARCHITECTURE.md

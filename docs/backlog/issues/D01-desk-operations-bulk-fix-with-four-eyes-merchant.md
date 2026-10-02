# [D01] Desk operations: bulk fix with four-eyes, merchant watch, regulator pack, shift handover

| Field | Value |
|---|---|
| Wave | W4 Channels, intelligence and desk |
| Area | `deskops` |
| Priority | P2 |
| Depends on | [M-ACT](M-ACT-actions-database-idempotency-row-locks-approval.md), [M-GOV](M-GOV-governance-persisted-policy-artefacts-approvals.md) |
| Plan | 02 §3.5, L4 |
| Labels | `wave:w4`, `area:deskops`, `priority:p2`, `type:feature` |

## Context
Not built.

## Scope
- Bulk fix: dry run, maker and checker, one receipt per case
- Merchant watch scores; regulator pack export; handover summary

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a bulk fix by its maker alone | executed | refused | `backend/tests/unit/test_deskops.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

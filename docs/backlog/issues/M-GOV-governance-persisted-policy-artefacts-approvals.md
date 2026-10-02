# [M-GOV] Governance: persisted policy artefacts, approvals and activations; Policy Studio API

| Field | Value |
|---|---|
| Wave | W1 Core modules on the baseline |
| Area | `governance` |
| Priority | P1 |
| Depends on | [B05](B05-postgresql-repositories-schema-and-role-per-modu.md) |
| Plan | 20, ADR-0003 |
| Labels | `wave:w1`, `area:governance`, `priority:p1`, `type:feature` |

## Context
Governance runs in memory; artefacts are YAML files only.

## Scope
- Persist artefacts, versions, approvals, activations and impact reports (20 §11)
- API for draft, review, approve, schedule, rollback; change class computed
- Publish `policy.published@v1`; detection and decision reload on it

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a money-tagged change approved by its maker only | activation attempted | refused | `backend/tests/unit/test_policy.py` |
| 2 | a scheduled change | the clock reaches `effective_from` | new decisions use it; earlier events still use the old value | `backend/tests/unit/test_policy.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

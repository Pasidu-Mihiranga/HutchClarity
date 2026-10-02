# [M-DET] Detection: rule parameters in the policy store (D5) and four more rule packs

| Field | Value |
|---|---|
| Wave | W1 Core modules on the baseline |
| Area | `detection` |
| Priority | P0 |
| Depends on | [B02](B02-unit-of-work-and-repository-interfaces-per-modul.md) |
| Plan | 09 §13, ADR-0001, ADR-0026 |
| Labels | `wave:w1`, `area:detection`, `priority:p0`, `type:feature` |

## Context
Confidence values and windows live inside the YAML packs; 6 of 16 candidate rules exist.

## Scope
- Packs reference parameter keys; values resolved `as_of` the event via the policy store
- Add `VAS_RENEWAL_UNNOTIFIED`, `PACK_MISMATCH`, `LOAN_RECOVERY`, `OUTAGE_DURING_PACK` with positive, negative, boundary and property tests
- Publish `cause.detected@v1`

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a confidence override effective tomorrow | a case for today's charge is evaluated | today's value is used | `backend/tests/golden/test_rule_parameters.py` |
| 2 | each new rule | golden tests run | positive, negative and boundary cases pass | `backend/tests/golden/` |
| 3 | all 21 existing golden tests | run | they pass unchanged | `backend/tests/golden/` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
- [ ] Rule catalogue in 09 §13.3 marks the new rules active

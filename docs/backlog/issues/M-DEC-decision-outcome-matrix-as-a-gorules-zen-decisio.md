# [M-DEC] Decision: outcome matrix as a GoRules ZEN decision table

| Field | Value |
|---|---|
| Wave | W1 Core modules on the baseline |
| Area | `decision` |
| Priority | P1 |
| Depends on | [M-DET](M-DET-detection-rule-parameters-in-the-policy-store-d5.md) |
| Plan | 09 §14.3, ADR-0026 |
| Labels | `wave:w1`, `area:decision`, `priority:p1`, `type:feature` |

## Context
Outcomes are ordered Python rules over a hashed input document.

## Scope
- ZEN table (JDM) with the same rows; parameters from the policy snapshot
- Parity test: Python and ZEN give identical outcomes on every golden and replay case before switching
- Publish `decision.generated@v1`

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | every golden case and 1,000 generated inputs | decided by both implementations | outcomes match exactly | `backend/tests/unit/test_decision_parity.py` |
| 2 | a table version change | replayed on past cases | the impact report lists outcome deltas | `backend/tests/unit/test_policy.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

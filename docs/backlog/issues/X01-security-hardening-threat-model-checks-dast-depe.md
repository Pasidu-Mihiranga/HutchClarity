# [X01] Security hardening: threat-model checks, DAST, dependency and licence scanning

| Field | Value |
|---|---|
| Wave | W5 Frontend and hardening |
| Area | `security` |
| Priority | P1 |
| Depends on | [B10](B10-ci-lanes-full-profile-integration-blocking-front.md) |
| Plan | 11 §19 |
| Labels | `wave:w5`, `area:security`, `priority:p1`, `type:feature` |

## Context
Threats TH1–TH19 are designed, not all tested.

## Scope
- Tests for each mitigable threat; OWASP ZAP baseline on staging; dependency and licence scan blocking

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | TH5 replay of a confirmation | attempted | refused | `backend/tests/security/` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

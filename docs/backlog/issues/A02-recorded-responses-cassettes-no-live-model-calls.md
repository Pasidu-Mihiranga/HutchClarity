# [A02] Recorded responses (cassettes): no live model calls in CI

| Field | Value |
|---|---|
| Wave | W2 AI foundation |
| Area | `ai` |
| Priority | P0 |
| Depends on | [A01](A01-ai-gateway-model-roles-config-ai-models-yaml-fal.md) |
| Plan | 19 §4.3 |
| Labels | `wave:w2`, `area:ai`, `priority:p0`, `type:feature` |

## Context
Any future model test would call a live endpoint.

## Scope
- Record once, replay in tests; cassette files reviewed like code
- CI fails if a test tries a live call

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a test using the `fast-text` role | run in CI | it reads the cassette and makes no network call | `backend/tests/unit/test_cassettes.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

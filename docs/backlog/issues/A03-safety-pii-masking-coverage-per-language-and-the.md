# [A03] Safety: PII masking coverage per language and the guard role

| Field | Value |
|---|---|
| Wave | W2 AI foundation |
| Area | `ai` |
| Priority | P0 |
| Depends on | [A01](A01-ai-gateway-model-roles-config-ai-models-yaml-fal.md) |
| Plan | 22 §8, 08 §12.6 |
| Labels | `wave:w2`, `area:ai`, `priority:p0`, `type:feature` |

## Context
Masking is tested mainly on English examples.

## Scope
- Golden sets of Sinhala, Tamil, English and Singlish text with numbers, NICs and names
- `guard` role as an injection assist; heuristic fallback

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | each language's PII set | masked | no raw identifier survives | `backend/tests/unit/test_pii_languages.py` |
| 2 | the injection set | sent through the assistant | zero actions executed; refusals audited | `backend/tests/evaluation/test_safety_set.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

# [A01] AI gateway: model roles, config/ai/models.yaml, fallback chains, quota-aware buckets

| Field | Value |
|---|---|
| Wave | W2 AI foundation |
| Area | `ai` |
| Priority | P0 |
| Depends on | none |
| Plan | 19 §4, ADR-0019 |
| Labels | `wave:w2`, `area:ai`, `priority:p0`, `type:feature` |

## Context
The gateway routes by tier for explanations only; `config/ai/models.yaml` exists but is not read.

## Scope
- Gateway API by role (`extract`, `reason`, `fast-text`, `judge`, `guard`, `embed`, `stt`, `tts`)
- Role → provider chain from config; no model ID in code
- Per-provider token buckets mirroring free-tier limits; priority (customer live > staff > batch)

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | no provider configured | any role is called | the template or rule path answers, 0 tokens | `backend/tests/unit/test_ai.py` |
| 2 | the primary provider returns 429 | a role is called | the next provider in the chain answers | `backend/tests/unit/test_ai.py` |
| 3 | source code | scanned | no model ID string outside config | `backend/tests/architecture/test_no_model_ids.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

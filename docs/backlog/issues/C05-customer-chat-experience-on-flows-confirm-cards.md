# [C05] Customer chat experience on flows: confirm cards, citations, handoff

| Field | Value |
|---|---|
| Wave | W3 Knowledge, RAG and agentic assistant |
| Area | `frontend` |
| Priority | P1 |
| Depends on | [C02](C02-flow-registry-and-the-seven-flows.md), [B09](B09-frontend-sdk-generated-from-openapi-checked-in-c.md) |
| Plan | 22 §4 step 10 |
| Labels | `wave:w3`, `area:frontend`, `priority:p1`, `type:feature` |

## Context
The chat UI renders single responses.

## Scope
- Render flow states, confirm cards (from proposals), citations, receipt links, handoff
- Accessibility and si/ta/en strings from i18n

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | the DISPUTE_CHARGE flow | driven in the browser | customer reaches a verified receipt | `Playwright e2e` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
- [ ] Walkthrough WT-02 re-verified

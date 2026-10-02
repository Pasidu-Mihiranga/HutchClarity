# [K01] Knowledge module: source registry and governed ingestion

| Field | Value |
|---|---|
| Wave | W3 Knowledge, RAG and agentic assistant |
| Area | `knowledge` |
| Priority | P0 |
| Depends on | [B02](B02-unit-of-work-and-repository-interfaces-per-modul.md), [M-GOV](M-GOV-governance-persisted-policy-artefacts-approvals.md) |
| Plan | 22 §7, 20 (K2) |
| Labels | `wave:w3`, `area:knowledge`, `priority:p0`, `type:feature` |

## Context
Help articles live in the mock store with keyword scoring.

## Scope
- New `modules/knowledge` with public surface and MODULE.md
- Sources with owner, version, `effective_from/to`, audience, language; publish through the policy lifecycle
- Ingestion: parse, clean, language tag, structure-aware chunking, metadata

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a T&C clause version 2 effective next month | retrieval for today | returns version 1 | `backend/tests/unit/test_knowledge_versions.py` |
| 2 | a staff-audience SOP | a customer query | it is never retrieved | `backend/tests/unit/test_knowledge_audience.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
- [ ] Module added to the dependency map and modules.md

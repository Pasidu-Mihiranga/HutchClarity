# [K03] Grounded answers: compose with citations, citation verifier, refusal, semantic cache

| Field | Value |
|---|---|
| Wave | W3 Knowledge, RAG and agentic assistant |
| Area | `knowledge` |
| Priority | P0 |
| Depends on | [K02](K02-index-and-retrieval-bm25-lite-pgvector-hybrid-fu.md), [A01](A01-ai-gateway-model-roles-config-ai-models-yaml-fal.md) |
| Plan | 22 §7, §8 |
| Labels | `wave:w3`, `area:knowledge`, `priority:p0`, `type:feature` |

## Context
No citations; knowledge answers are not verified.

## Scope
- Compose with `fast-text` from CONTEXT + FACTS; template path without a model
- Citation verifier (retrieved, effective, audience); refuse with 'I don't know + a person' when ungrounded
- Cache generic answers keyed by catalogue version and language; invalidate on `knowledge.published`
- `/v1/knowledge/search` served by this module (not the mock store)

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | an answer citing a chunk that was not retrieved | verified | blocked, template or refusal shown | `backend/tests/unit/test_citation_verifier.py` |
| 2 | a question with no source | asked | the assistant says it does not know and offers a person | `backend/tests/acceptance/test_assistant.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
- [ ] OpenAPI snapshot regenerated if the search contract changes

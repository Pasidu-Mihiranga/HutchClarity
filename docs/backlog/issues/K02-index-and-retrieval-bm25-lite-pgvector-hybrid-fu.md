# [K02] Index and retrieval: BM25 (lite), pgvector hybrid (full), filters and rerank

| Field | Value |
|---|---|
| Wave | W3 Knowledge, RAG and agentic assistant |
| Area | `knowledge` |
| Priority | P0 |
| Depends on | [K01](K01-knowledge-module-source-registry-and-governed-in.md), [A01](A01-ai-gateway-model-roles-config-ai-models-yaml-fal.md) |
| Plan | 22 §7 |
| Labels | `wave:w3`, `area:knowledge`, `priority:p0`, `type:feature` |

## Context
No index or retriever.

## Scope
- `lite`: in-memory BM25 (Python only); `full`: pgvector with `embed` role + BM25 hybrid
- Filters: effective date, audience, language, products; rerank; top-k from config
- Parity suite: same top results on a fixed corpus within tolerance

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | the RAG golden set | retrieved | Recall@5 ≥ 0.9 | `backend/tests/evaluation/test_rag_retrieval.py` |
| 2 | a Singlish query | rewritten by `extract` (cassette) | the right clause is in the top 5 | `backend/tests/evaluation/test_rag_retrieval.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

# [C01] Conversation orchestrator and state store

| Field | Value |
|---|---|
| Wave | W3 Knowledge, RAG and agentic assistant |
| Area | `conversation` |
| Priority | P0 |
| Depends on | [B02](B02-unit-of-work-and-repository-interfaces-per-modul.md) |
| Plan | 22 §4, §9 |
| Labels | `wave:w3`, `area:conversation`, `priority:p0`, `type:feature` |

## Context
Each chat turn is stateless.

## Scope
- Turn pipeline from 22 §4 (guard, mask, intake, handoff check, flow step, compose, verify, record)
- Conversation state per case with TTL; repositories for `lite` and `full`
- `conversation.turn.completed@v1` event

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a customer starts on WhatsApp and continues in the app | the case ID is the same | the flow resumes at the same state | `backend/tests/acceptance/test_assistant.py` |
| 2 | a turn | recorded | flow state, tool and chunk IDs, role, model and verifier result are in the audit | `backend/tests/unit/test_conversation_audit.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

# [C03] Bounded agent step: planner with tool allowlist, limits and fallback

| Field | Value |
|---|---|
| Wave | W3 Knowledge, RAG and agentic assistant |
| Area | `conversation` |
| Priority | P0 |
| Depends on | [C02](C02-flow-registry-and-the-seven-flows.md), [A01](A01-ai-gateway-model-roles-config-ai-models-yaml-fal.md), [A02](A02-recorded-responses-cassettes-no-live-model-calls.md), [A04](A04-mcp-server-over-the-network-sdk-streamable-http.md) |
| Plan | 22 §6, ADR-0030 |
| Labels | `wave:w3`, `area:conversation`, `priority:p0`, `type:feature` |

## Context
No agent loop.

## Scope
- Planner returns `{tool, args, reason_code}` validated against the state's allowlist schema
- Limits: 4 tool calls per turn, token and time budgets; tool results treated as untrusted data
- Invalid plan → deterministic step; no `amount` field accepted

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a planner output naming `confirm_and_execute` | validated | rejected; deterministic step runs; audited | `backend/tests/unit/test_agent_step.py` |
| 2 | a plan with an `amount` argument | validated | rejected | `backend/tests/unit/test_agent_step.py` |
| 3 | the safety set | run through the agent | zero executions | `backend/tests/evaluation/test_safety_set.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

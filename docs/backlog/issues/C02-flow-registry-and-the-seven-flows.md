# [C02] Flow registry and the seven flows

| Field | Value |
|---|---|
| Wave | W3 Knowledge, RAG and agentic assistant |
| Area | `conversation` |
| Priority | P0 |
| Depends on | [C01](C01-conversation-orchestrator-and-state-store.md), [M-GOV](M-GOV-governance-persisted-policy-artefacts-approvals.md) |
| Plan | 22 §5, 02 §3.8 |
| Labels | `wave:w3`, `area:conversation`, `priority:p0`, `type:feature` |

## Context
No multi-step flows.

## Scope
- Flow DSL (YAML) as policy content: states, slots, allowed tools, exits, `agentic` markers
- Flows: DISPUTE_CHARGE, KNOWLEDGE_QA, ACCOUNT_AND_POLICY, SAFEGUARD_SETUP, CASE_STATUS, NETWORK_STATUS, HANDOFF
- Flow tests: scripted multi-turn conversations per flow

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | the DISPUTE_CHARGE script for Dilani (Sinhala) | run with no model | ends with a verified receipt | `backend/tests/acceptance/test_flows.py` |
| 2 | a flow file referencing a tool not in its allowlist | published | refused at validation | `backend/tests/unit/test_flow_registry.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

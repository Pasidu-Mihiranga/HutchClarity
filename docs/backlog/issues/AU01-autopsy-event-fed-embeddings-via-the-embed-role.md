# [AU01] Autopsy: event-fed, embeddings via the embed role, review workflow

| Field | Value |
|---|---|
| Wave | W4 Channels, intelligence and desk |
| Area | `autopsy` |
| Priority | P2 |
| Depends on | [A01](A01-ai-gateway-model-roles-config-ai-models-yaml-fal.md), [B04](B04-outbox-in-the-unit-of-work-relay-and-consumer-fr.md) |
| Plan | 02 §3.3 |
| Labels | `wave:w4`, `area:autopsy`, `priority:p2`, `type:feature` |

## Context
Batch on demo data only.

## Scope
- Consume `complaint.created`; embeddings through the gateway; clusters stay hypotheses until reviewed
- Serverless batch packaging

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | an unreviewed cluster | shown to staff | labelled as a hypothesis | `backend/tests/unit/test_autopsy_foresight.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

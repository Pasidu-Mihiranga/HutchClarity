# [I01] Insights: projections and console dashboards

| Field | Value |
|---|---|
| Wave | W4 Channels, intelligence and desk |
| Area | `insights` |
| Priority | P2 |
| Depends on | [B04](B04-outbox-in-the-unit-of-work-relay-and-consumer-fr.md) |
| Plan | 02 §3.5, 10 |
| Labels | `wave:w4`, `area:insights`, `priority:p2`, `type:feature` |

## Context
Dashboards read live objects.

## Scope
- Read models built from events; top causes, where AI stops, drop-offs, refunds by rule

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | replaying the event log | projections rebuilt | the same numbers | `backend/tests/unit/test_insights.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

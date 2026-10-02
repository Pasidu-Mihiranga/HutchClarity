# [X02] Performance and resilience: load and chaos tests

| Field | Value |
|---|---|
| Wave | W5 Frontend and hardening |
| Area | `platform` |
| Priority | P2 |
| Depends on | [B05](B05-postgresql-repositories-schema-and-role-per-modu.md), [B04](B04-outbox-in-the-unit-of-work-relay-and-consumer-fr.md) |
| Plan | 12 §24 |
| Labels | `wave:w5`, `area:platform`, `priority:p2`, `type:feature` |

## Context
No load or chaos tests.

## Scope
- k6 scenarios for the journeys at 10× pilot load; chaos: kill relay, database failover, provider outage

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | the API at 10× pilot load | run | p95 targets from 03 §4.2 met | `tests/load` |
| 2 | the provider down | customers ask questions | template answers, no errors | `tests/chaos` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

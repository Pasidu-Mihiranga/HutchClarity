# [B04] Outbox in the unit of work, relay, and consumer framework with dead-letter handling

| Field | Value |
|---|---|
| Wave | W0 Baseline wiring |
| Area | `platform` |
| Priority | P0 |
| Depends on | [B02](B02-unit-of-work-and-repository-interfaces-per-modul.md), [B03](B03-event-bus-port-in-process-driver-and-kafka-drive.md) |
| Plan | 21 §11.4, ADR-0014, ADR-0029 |
| Labels | `wave:w0`, `area:platform`, `priority:p0`, `type:baseline` |

## Context
`platform/messaging/outbox.py` exists but is not wired to any state change.

## Scope
- Outbox rows written in the same unit of work as the state change
- Relay publishes pending rows to the bus and marks them sent
- Consumer framework: `processed_event` table, retry with backoff, dead-letter store, alert hook
- Correlation ID carried from request to event to consumer

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a state change whose unit of work rolls back | the relay runs | no event is published | `backend/tests/unit/test_outbox_wiring.py` |
| 2 | the relay killed after publishing but before marking sent | it restarts | the event is redelivered and the consumer applies it once | `backend/tests/unit/test_outbox_wiring.py` |
| 3 | a consumer that always fails | retries are exhausted | the event lands in the dead-letter store and an alert is raised | `backend/tests/unit/test_outbox_wiring.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

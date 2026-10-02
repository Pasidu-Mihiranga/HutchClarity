# [B03] Event bus port: in-process driver and Kafka driver with one parity suite

| Field | Value |
|---|---|
| Wave | W0 Baseline wiring |
| Area | `platform` |
| Priority | P0 |
| Depends on | [B01](B01-event-contracts-typed-versioned-payloads-for-eve.md) |
| Plan | 21 §11.4, ADR-0027 |
| Labels | `wave:w0`, `area:platform`, `priority:p0`, `type:baseline` |

## Context
There is no bus abstraction modules can publish to or subscribe on.

## Scope
- `EventBus` port: publish (from the outbox relay), subscribe (consumer group, handler)
- In-process driver: dispatches after commit, preserves per-`subscriber_ref` order
- Kafka driver (`full`): topic per event type, key `subscriber_ref`, consumer groups
- Parity suite: ordering per key, at-least-once redelivery, consumer group isolation

## Out of scope
- Exactly-once semantics (consumers are idempotent instead)

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | three events for one subscriber | delivered on either driver | the handler sees them in order | `backend/tests/contract/test_bus_parity.py` |
| 2 | a handler that fails once | the event is redelivered | it is processed once overall | `backend/tests/contract/test_bus_parity.py` |
| 3 | the Kafka driver | run in the CI `full` lane | the same parity suite passes | `backend/tests/contract/test_bus_parity.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
- [ ] Kafka driver documented in 19 and runnable via `make up-full`

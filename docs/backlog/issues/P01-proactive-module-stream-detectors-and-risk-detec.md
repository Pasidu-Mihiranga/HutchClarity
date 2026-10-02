# [P01] Proactive module: stream detectors and risk.detected

| Field | Value |
|---|---|
| Wave | W4 Channels, intelligence and desk |
| Area | `proactive` |
| Priority | P1 |
| Depends on | [B03](B03-event-bus-port-in-process-driver-and-kafka-drive.md), [B04](B04-outbox-in-the-unit-of-work-relay-and-consumer-fr.md) |
| Plan | 02 §3.6 |
| Labels | `wave:w4`, `area:proactive`, `priority:p1`, `type:feature` |

## Context
Zero-contact refunds are triggered by a route, not by events.

## Scope
- Consume `payment.recorded`, `usage.threshold_reached`, `pack.expiring`; detect duplicate reloads, FUP 80/95%, pack-end
- Publish `risk.detected@v1`; `case` opens a zero-contact case

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | two captures with one credit | events arrive | an AUTO_FIX case is opened and fixed with no human | `backend/tests/acceptance/test_zero_contact.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

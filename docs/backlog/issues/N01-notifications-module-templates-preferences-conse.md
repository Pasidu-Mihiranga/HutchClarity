# [N01] Notifications module: templates, preferences, consent, dispatch, delivery status

| Field | Value |
|---|---|
| Wave | W4 Channels, intelligence and desk |
| Area | `notifications` |
| Priority | P1 |
| Depends on | [B04](B04-outbox-in-the-unit-of-work-relay-and-consumer-fr.md) |
| Plan | 18 §9, ADR-0020 |
| Labels | `wave:w4`, `area:notifications`, `priority:p1`, `type:feature` |

## Context
No notification module.

## Scope
- Consume `receipt.issued`, `risk.detected`, `approval.requested`; route by preference and consent; quiet hours
- Templates only (no free text); idempotent per (event, recipient, template); fallback channel

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | `receipt.issued` delivered twice | consumed | one message sent | `backend/tests/unit/test_notifications.py` |
| 2 | a free-text body | sent | refused | `backend/tests/unit/test_notifications.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

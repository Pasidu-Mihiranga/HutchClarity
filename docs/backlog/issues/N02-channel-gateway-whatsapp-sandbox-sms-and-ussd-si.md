# [N02] Channel gateway: WhatsApp sandbox, SMS and USSD simulator, verified webhooks

| Field | Value |
|---|---|
| Wave | W4 Channels, intelligence and desk |
| Area | `channel-gateway` |
| Priority | P2 |
| Depends on | [C01](C01-conversation-orchestrator-and-state-store.md), [N01](N01-notifications-module-templates-preferences-conse.md) |
| Plan | 09 §9.7 |
| Labels | `wave:w4`, `area:channel-gateway`, `priority:p2`, `type:feature` |

## Context
Web only.

## Scope
- Separate deployable (serverless-ready); signature-verified webhooks; 24-hour window rules
- SMS/USSD simulator for the basic-phone journey

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a webhook with a bad signature | received | rejected | `services/channel-gateway tests` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

# 2026-10-04 - WA03 - Validate webhook freshness on receipt time

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | WA01 follow-up |
| PR / commit | pending |
| Units touched | channel gateway webhook authentication |

## What changed

- Validate provider webhook timestamps with an injected wall clock.
- Keep conversation windows, cases and decisions on the deterministic domain
  clock.
- Added a regression test with deliberately different domain and provider
  clocks.

## Why

Live WhatsApp messages reached the transport with a valid HMAC, but the gateway
rejected them as stale because freshness was compared with the frozen synthetic
domain clock rather than the time the HTTP request arrived.

## Decisions made

- Transport replay protection uses receipt time because external providers
  cannot sign with Clarity's replay clock.
- Domain behavior remains unchanged and deterministic.

## Docs updated

- [x] WhatsApp walkthrough live failure evidence
- [ ] MODULE.md: no domain module behavior changed
- [ ] ARCHITECTURE.md / modules.md: no architecture change
- [ ] CHANGELOG.md / contracts: no public HTTP contract change
- [ ] Plan via CHANGES.md: no plan change

## Tests

- `pytest tests/unit/test_channel_gateway.py -q`: 31 passed.
- `make check`: 2,415 passed, 633 skipped; lint, formatting, typing and import
  contracts passed.

## Open issues / next step

Deploy and repeat the linked-phone WhatsApp message through the signed gateway.

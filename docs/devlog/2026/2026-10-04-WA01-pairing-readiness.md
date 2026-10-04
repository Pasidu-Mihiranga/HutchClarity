# 2026-10-04 - WA01 - Wait for pairing readiness

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | R4, WA01 (#59) |
| PR / commit | pending |
| Units touched | WhatsApp operator pairing |

## What changed

- Pairing waits for the Baileys WebSocket to open before requesting a code.
- The wait is bounded and fails with a safe operator error.
- Mocked tests cover delayed readiness and timeout.

## Why

The first corrected pairing invocation reached Baileys, but an immediate code
request raced the provider connection and failed with status 428.

## Decisions made

The readiness check uses Baileys's `ws.isOpen` state instead of an arbitrary
sleep, with a 15-second upper bound.

## Docs updated

- [x] Devlog
- [ ] Other docs: operator behavior and contracts are unchanged

## Tests

- `npm test`: 11 passed.
- WhatsApp production image: built successfully.

## Open issues / next step

Deploy the fix and repeat the private operator pairing.

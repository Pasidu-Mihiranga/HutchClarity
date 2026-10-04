# 2026-10-04 - WA01 - Baileys WhatsApp transport

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | R4, WA01 (#59) |
| PR / commit | pending |
| Units touched | channel gateway transport, deployment, CI |

## What changed

- Added a TypeScript Baileys transport for signed direct-message delivery and
  exact channel-gateway replies.
- Added persistent auth, private operator pairing, reconnection, delivery-state
  logging, voice fallback and provider-event filtering.
- Added an opt-in Compose service and immutable CI/CD image.

## Why

WA01 requires a narrow external WhatsApp adapter after DEP01, CD01 and N02 are
operational. Those prerequisites are now verified.

## Decisions made

- The transport is disabled by default and pairing has no HTTP surface.
- Baileys `6.7.24` is pinned because the current `7.0.0` release is still an RC.
- The MIT Baileys runtime and BSD-3-Clause `@hapi/boom` satisfy I17.
- Auth uses a persistent file volume for this single operator-paired account;
  database auth storage is deferred until horizontal replicas are required.

## Docs updated

- [x] Service README
- [x] ARCHITECTURE.md / modules.md
- [x] Walkthrough WT-16
- [x] CHANGELOG.md
- [ ] Plan change: none; this implements the existing R4 design

## Tests

- `npm test`: 9 passed.
- WhatsApp Docker image: built locally.
- `make check`: Ruff, formatting, mypy, import contracts and 2,405 tests
  passed; 633 profile-dependent tests skipped.

## Open issues / next step

Pair the authorized phone, deploy with the `whatsapp` profile, and verify one
live synthetic direct-message journey before closing #59.

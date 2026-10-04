# 2026-10-04 - WA01 - Correct phone pairing state machine

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | WA01 |
| PR / commit | pending |
| Units touched | WhatsApp operator pairing |

## What changed

- Request the phone pairing code only after Baileys emits its pairing-ready QR
  event.
- Reconnect after the expected status 515 session restart when credentials have
  registered.
- Added focused regression tests for readiness, one-time code requests and safe
  restart classification.

## Why

The private operator command requested a pairing code as soon as the raw socket
opened. Baileys requires phone pairing to wait for the same readiness event used
by QR pairing. It also restarts the connection after successful registration,
which the command previously treated as a failure.

## Decisions made

- Pairing stays operator-only and the transport remains disabled until a live
  paired session and synthetic subscriber journey are verified.
- A restart is accepted only for status 515 with registered credentials. All
  other disconnects remain failures.

## Docs updated

- [x] Service README pairing lifecycle
- [ ] MODULE.md: no domain module behavior changed
- [ ] ARCHITECTURE.md / modules.md: no architecture change
- [ ] Walkthrough: live verification remains pending
- [ ] CHANGELOG.md / contracts: no public contract change
- [ ] Plan via CHANGES.md: no plan change

## Tests

- `npm test`: 11 passed, 0 failed.
- Production image: built successfully.
- `make check`: 2405 passed, 633 skipped; lint, formatting, types and import
  contracts passed.

## Open issues / next step

Deploy the corrected pairing command, link the approved operator phone, then
complete the live synthetic subscriber walkthrough before closing WA01.

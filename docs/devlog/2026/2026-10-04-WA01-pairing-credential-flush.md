# 2026-10-04 - WA01 - Flush pairing credentials

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | WA01 |
| PR / commit | pending |
| Units touched | WhatsApp operator pairing |

## What changed

- Serialize Baileys credential writes during operator pairing.
- Await all credential writes before reconnecting or exiting successfully.
- Added a regression test proving flush waits for ordered asynchronous writes.

## Why

Live phone linking succeeded, but the pairing process exited while `saveCreds`
was still writing. This left a truncated `creds.json`, so the managed transport
correctly rejected the session as unpaired.

## Decisions made

- Credential persistence remains in Baileys' multi-file auth adapter.
- The fix is limited to lifecycle ordering and does not change channel behavior
  or public contracts.

## Docs updated

- [x] Service README pairing lifecycle
- [ ] MODULE.md: no domain module behavior changed
- [ ] ARCHITECTURE.md / modules.md: no architecture change
- [ ] Walkthrough: live verification remains pending
- [ ] CHANGELOG.md / contracts: no public contract change
- [ ] Plan via CHANGES.md: no plan change

## Tests

- `npm test`: 12 passed, 0 failed.
- Production WhatsApp image: built successfully.
- `make check`: 2405 passed, 633 skipped; lint, formatting, types and import
  contracts passed.

## Open issues / next step

Deploy, pair again, validate the persisted credential JSON, then enable and
health-check the managed transport.

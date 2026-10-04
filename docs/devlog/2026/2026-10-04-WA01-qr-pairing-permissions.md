# 2026-10-04 - WA01 - QR pairing and auth permissions

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | R4, WA01 (#59) |
| PR / commit | pending |
| Units touched | WhatsApp operator pairing and auth state |

## What changed

- Added operator-selected QR pairing when phone-number linking is refused.
- Pairing now exits only after a connected session or a bounded timeout.
- Runtime and pairing processes set umask `077` before auth-state access.

## Why

WhatsApp refused phone-number linking without creating a session. Inspection
also found Baileys created `creds.json` as `0644` inside its `0700` private
volume, so the process now enforces secret-file permissions.

## Decisions made

- QR output exists only in the private operator command, never an HTTP route or
  service log.
- `qrcode-terminal` and its type package are MIT licensed.

## Docs updated

- [x] Devlog
- [ ] Other docs: the documented operator-only pairing boundary is unchanged

## Tests

- `npm test`: 11 passed.
- `npm audit`: 0 vulnerabilities.
- WhatsApp production image: built successfully.

## Open issues / next step

Deploy, tighten the existing credential file, and complete QR pairing.

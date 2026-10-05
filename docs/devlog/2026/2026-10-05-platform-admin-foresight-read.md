# 2026-10-05 - iam - platform admin foresight read

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | E2 / C4 (console + foresight) |
| PR / commit | (local) |
| Units touched | iam (ROLE_PERMISSIONS), config/opa |

## What changed
- `platform_admin` gains `foresight:read` in `ROLE_PERMISSIONS` and `config/opa/data.json`.
- Unit test pins read without draft/run/outcome-record.

## Why
The console sidebar only lists sections the identity can open. Platform admin needed Foresight visible and usable for read-only rehearsal review without gaining product or CX foresight duties.

## Decisions made
- Read only: no `foresight:run`, `foresight:scenario:draft`, or `foresight:outcome:record`.

## Docs updated
- [x] `modules/iam/MODULE.md` history
- [x] Devlog (this file)

## Tests
- `pytest backend/tests/unit/test_iam.py -k platform_admin_can_read_foresight`

## Open issues / next step
Re-sign-in as `platform` / `admin` so the session picks up the new permission.

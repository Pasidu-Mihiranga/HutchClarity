# 2026-10-05 - iam - local admin account

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | local desk sign-in |
| PR / commit | uncommitted |
| Units touched | iam (synthetic staff directory) |

## What changed
- Added `admin` (`user_ref` `admin-1`, role `platform_admin`) to `config/staff/synthetic-directory.json`. Only scrypt hashes are stored.
- Recorded the password in `frontend/e2e/session.ts`, which is where the directory comment says the synthetic passwords live.

## Why
A local desk sign-in with a short username and password, holding the existing platform-admin permissions (flags, kill switches, audit restore). No new role and no money permissions.

## Decisions made
- Role is `platform_admin`, the role that already opens Admin. A second role was not added.
- Password is `admin123456` (12 characters, the minimum `scripts/staff_password.py` accepts). Step-up code is `step-up`, the same code as the other synthetic accounts. Leaving step-up empty still signs in at ordinary MFA.
- This is the synthetic directory the local API loads. It is not a Keycloak user and not a PostgreSQL row. Lite has no staff table.

## Docs updated
- [x] MODULE.md of: iam
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough: WT-13 still uses `platform` / `platform-clarity` for Admin
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
`POST /v1/auth/staff/login` as `admin` with the step-up code returned 200, subject `admin-1`, role `platform_admin`. The first attempt was 401 because it landed during the reload.

## Open issues / next step
The API loads the directory at startup, so a running process must reload before the account works.

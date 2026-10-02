# 2026-10-02 - M-IAM - Keycloak, OPA and shared identity state

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | M-IAM (#7), R2 |
| PR / commit | uncommitted |
| Units touched | iam, HTTP auth, settings, compose |

## What changed

- Added Keycloak JWKS validation for staff and MCP clients and an OPA authorization driver.
- Persisted OTP/rate-limit and session/refresh/revocation state behind the shared store.
- Added checked-in Keycloak/OPA development configuration and exhaustive authorization parity tests.

## Why

ADR-0010 keeps customer issuance local while federating staff and machine identity in full/prod.

## Decisions made

- OPA errors deny access; unknown Keycloak roles grant no permissions.
- Refresh tokens rotate and revoke their previous access session.

## Docs updated

- [x] iam `MODULE.md`
- [x] `.env.example`, compose and `ARCHITECTURE.md`
- [x] `CHANGELOG.md`

## Tests

IAM unit tests, settings tests and every role-permission OPA parity case passed.

## Open issues / next step

Production federation details remain **REQUIRES HUTCH CONFIRMATION**.

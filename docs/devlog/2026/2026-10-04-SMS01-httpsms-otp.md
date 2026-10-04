# 2026-10-04 - SMS01 - httpSMS OTP delivery

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | SMS01 |
| PR / commit | pending |
| Units touched | iam, app composition, deployment configuration |

## What changed

- Added an httpSMS driver behind the existing OTP delivery port.
- Added paired settings for the primary user key and Android sender.
- Converted provider refusal into a safe 502 without exposing its response.
- Kept automated tests offline with an HTTP mock.

## Why

Issue #75 sends customer sign-in codes by SMS while preserving the existing
single-use code, expiry, guessing and pumping controls.

## Decisions made

- Use the hosted HTTP API instead of deploying the full AGPL-3.0 stack.
- No new dependency is needed because the repository already uses `httpx`.
- The supplied `pk_` credential cannot send. Activation needs the primary user
  key and registered sender number.

## Docs updated

- [x] IAM module
- [x] Environment and VPS deployment configuration
- [x] Changelog

## Tests

- Focused IAM, settings and httpSMS tests: 77 passed.
- `make check`: 2,405 passed, 633 skipped; Ruff, mypy and import contracts clean.

## Open issues / next step

Obtain the primary user key and sender, run one authorized live OTP, then set
the two variables on the VPS.

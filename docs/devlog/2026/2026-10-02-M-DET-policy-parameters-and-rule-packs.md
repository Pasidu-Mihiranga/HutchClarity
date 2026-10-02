# 2026-10-02 - M-DET - Policy parameters and rule packs

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | M-DET (#35), R3 |
| PR / commit | uncommitted |
| Units touched | detection, contracts, policy, rules |

## What changed

- Moved rule confidence and duration windows to effective-dated policy values.
- Added VAS renewal, pack mismatch, loan recovery and outage rule packs with golden, negative, boundary and property tests.
- Published cause facts after evaluation.

## Why

D5 and ADR-0001 require rule logic to stay in packs while changeable numeric parameters live in policy.

## Decisions made

- Parameters resolve as of the disputed event, not the current clock.

## Docs updated

- [x] detection `MODULE.md`
- [x] `ARCHITECTURE.md` / `docs/modules.md`
- [x] Plan 09 catalogue and plan change record

## Tests

Golden detection suites passed; full `make check` is recorded in the final handoff.

## Open issues / next step

Six candidate packs remain for later product validation.

# 2026-10-02 - M-GOV - Policy Studio lifecycle

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | M-GOV (#20), R3 |
| PR / commit | uncommitted |
| Units touched | governance, config, HTTP API |

## What changed

- Persisted candidate versions, impact reports, approvals, schedules, activations and supersession in the policy change aggregate.
- Added protected Policy Studio lifecycle routes, activation into the live resolver and rollback drafting.
- Published `policy.published@v1`.

## Why

ADR-0003 and plan 20 require maker-checker control and replay evidence before policy affects decisions or money.

## Decisions made

- Rollback creates a new governed version instead of mutating history.

## Docs updated

- [x] governance `MODULE.md`
- [x] `CHANGELOG.md` and OpenAPI contract

## Tests

Governance lifecycle, schedule and decision-table preview tests passed.

## Open issues / next step

None in this work package.

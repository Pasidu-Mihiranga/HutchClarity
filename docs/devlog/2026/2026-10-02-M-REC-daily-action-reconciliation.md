# 2026-10-02 - M-REC - Daily action reconciliation

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | M-REC (#38), R3 |
| PR / commit | uncommitted |
| Units touched | reconciliation, actions event, finance API |

## What changed

- Added a reconciliation module consuming `action.completed@v1` and persisting expected adapter confirmations.
- Added an idempotent T+1 matcher, `reconciliation.mismatch@v1`, and a finance-only queue route.
- Extended action step events with system idempotency and adapter references.

## Why

Plan 09 section 14.4 requires an independent daily check that executed financial actions match adapter records.

## Decisions made

- Missing or inconsistent evidence always enters a human queue.

## Docs updated

- [x] reconciliation `MODULE.md`
- [x] `docs/modules.md`, `ARCHITECTURE.md`, plan 21 and `CHANGELOG.md`

## Tests

- `make check`: 1,211 passed, 45 skipped; lint, format, mypy and import contracts passed.
- `make contracts-check` and SDK TypeScript typecheck passed.
- Frontend lint could not run because the existing Next.js apps open the ESLint setup prompt. Frontend build kept its existing customer-web type failure in `app/cases/page.tsx:51`; console and verify built successfully.

## Open issues / next step

The production worker supplies the daily schedule.

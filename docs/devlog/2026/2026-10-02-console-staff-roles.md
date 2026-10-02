# 2026-10-02 - Console staff roles

> **Merged 2026-10-02:** imported from the team's `main` into the `dev` branch; paths updated to the R1 layout (see `2026-10-02-R1-dev-merge.md`).

## Intent

Make every non-customer role usable in the Next.js console with one-tap
demo role switching and real permission checks against `make dev`.

## What changed

- Extended `@clarity/sdk` with staff session, desk, approve, demo, and
  admin switch helpers.
- Console: `StaffSessionProvider`, bottom `RoleSwitcherBar` (9 roles +
  step-up), permission-gated nav, live Desk / Insights / Studio / Admin.
- API: `GET/POST /v1/admin/switches`, `POST /v1/admin/merchants/suspend`.
- Tests for switch / merchant routes; WT-02 staff console walkthrough.

## Verification

- Unit: switch read/flip permission matrix; merchant suspend with step-up.
- Manual: WT-02 steps on `:3001` against `:8000`.

## Follow-up (cannot open)

- Console was not running on `:3001`; start with
  `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000 npm run dev:console`.
- Session restore raced AccessDenied on hard navigation; added `restoring`
  gate.
- Bottom role bar covered queue clicks on short viewports; raised main
  padding and capped queue scroll height.

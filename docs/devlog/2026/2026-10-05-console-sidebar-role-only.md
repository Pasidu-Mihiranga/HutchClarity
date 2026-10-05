# 2026-10-05 - console - sidebar shows only allowed sections

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | E2 (console shell) |
| PR / commit | (local) |
| Units touched | frontend/apps/console |

## What changed
- Sidebar section list filters to permissions this identity holds; denied sections are omitted (no dimmed "not available for your role" rows).
- Unit and desk-authorization e2e expectations updated for omit behaviour.
- Sidebar layout devlog decision note aligned.

## Why
Dimmed sidebar rows still clutter the workspace and invite dead clicks. Each role should see only the sections it can open.

## Decisions made
- Same `anyOf` gates as before (aligned with each page's own checks).
- Direct URL to a denied section redirects to the first allowed section
  (see `2026-10-05-console-access-denied-redirect.md`).

## Docs updated
- [x] Devlog (this file + sidebar-layout decision line)
- [ ] MODULE.md / CHANGELOG (no `/v1` change)

## Tests
- `npm run test -- test/ConsoleNav.test.tsx` in `frontend/apps/console`.

## Open issues / next step
None.

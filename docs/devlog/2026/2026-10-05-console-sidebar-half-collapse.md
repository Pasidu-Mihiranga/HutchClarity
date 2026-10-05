# 2026-10-05 - console - sidebar half-collapse

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | E2 (console shell) |
| PR / commit | (local) |
| Units touched | frontend/apps/console |

## What changed
- Sidebar toggles between expanded (260px, labels) and half-collapsed (80px, icons).
- Preference stored in `localStorage` (`clarity.console.sidebar-collapsed`).
- Active tab keeps the open-right expand view when collapsed (left-rounded into the workspace), not a centred pill.
- Session foot compact: initials + icon sign-out.

## Why
Give the workspace more width without losing section access.

## Decisions made
- Labels stay in the DOM as `sr-only` when collapsed so screen readers and link names keep working.
- Toggle sits above the session foot with `aria-expanded`.

## Docs updated
- [x] Devlog (this file)

## Tests
- `npm run test -- test/ConsoleNav.test.tsx`

## Open issues / next step
None.

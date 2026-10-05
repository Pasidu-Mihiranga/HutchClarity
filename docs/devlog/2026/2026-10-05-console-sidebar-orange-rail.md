# 2026-10-05 - console - orange sidebar rail

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | E2 (console shell) |
| PR / commit | (local) |
| Units touched | frontend/apps/console |

## What changed
- Signed-in sidebar uses `--console-rail` (`#e87732`): white brand mark, white section labels.
- Active section is a white tab: `rounded-l-full`, open on the right (`rounded-r-none`) flush to the workspace, rail-coloured text and thin outline icons.
- Idle items are white; hover is `bg-white/20` (soft orange pill).
- Session foot uses white/translucent type on the same rail.
- Top-right of the rail is rounded (`rounded-tr-[2.75rem]`).

## Why
Match the staff console sidebar reference (orange rail, white active pill).

## Decisions made
- Keep semantic tokens (`bg-primary`, `text-primary-on`, `text-primary`) rather than hard-coded hex.
- Section labels and permission gating unchanged.

## Docs updated
- [x] Devlog (this file)

## Tests
- `npm run test -- test/ConsoleNav.test.tsx` in `frontend/apps/console`.

## Open issues / next step
None.

# 2026-10-05 - console - Desk workspace layout

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | R5 frontend (console shell) |
| PR / commit | branch `feat/console-desk-layout` |
| Units touched | frontend console |

## What changed
- Signed-in Desk is a workspace: sidebar with the real sections and the signed-in subject and role, case table, and case panel.
- The header sign-in form is unchanged and still used on every other page, and on the Desk before sign-in.

## Why
The Desk should use the workspace layout from the expected screen, on the current queue, case, evidence, and approval calls.

## Decisions made
- No new screens, names, or actions. Customers, Knowledge, Automation, Reports, and an AI copilot are not in this system, so they are not in the nav.
- The queue has no updated-at and no customer name, so those columns are not invented. Amount and the masked number are the fields the queue already sends.
- Filters are All, Needs action (`STAFF_APPROVAL`), and Handoff. Resolved cases are not in `/v1/desk/queue`.

## Docs updated
- [ ] MODULE.md of: none (frontend only)
- [ ] ARCHITECTURE.md / modules.md
- [x] Walkthrough: WT-13 sign-in location
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
Console unit tests (`vitest`) after the layout change. Browser check of the desk against the running API.

## Open issues / next step
Full Playwright desk suite was not re-run here.

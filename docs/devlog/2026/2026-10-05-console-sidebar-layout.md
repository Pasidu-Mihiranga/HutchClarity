# 2026-10-05 - console - sidebar workspace layout

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | R5 frontend (console shell) |
| PR / commit | branch `feat/console-desk-layout` |
| Units touched | frontend console |

## What changed
- Signed-in console uses a sidebar: Hutch Clarity Desk mark, the real sections, and the signed-in person with sign out.
- Admin uses that workspace: switch list, the selected switch, and the same posture and template cards.
- Desk no longer draws a second sidebar inside the page. Its queue, search, and case panel stay on the existing calls.

## Why
The signed-in admin screen was a top bar. The expected desk is a sidebar workspace. The change is layout and style only.

## Decisions made
- Nav labels stay the real sections. Customers, Knowledge, Automation, Reports, and an AI copilot are not in this system, so they are not in the nav.
- Admin filters are All, On, and Off over the switches the API already returns. Search matches the switch key. No case names, amounts, or timestamps were added.
- A section this role cannot open is still text, with "(not available for your role)", not a link.
- The sign-in page is unchanged.

## Docs updated
- [ ] MODULE.md of: none (frontend only)
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
Console nav unit tests. Browser check of `/admin` signed in as the local admin account.

## Open issues / next step
Playwright desk suite was not re-run here.

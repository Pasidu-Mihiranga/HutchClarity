# 2026-10-05 - console - autopsy cluster disclosure

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | R5 frontend (console) |
| PR / commit | uncommitted |
| Units touched | frontend console |

## What changed
- Each Complaint Autopsy cluster keeps its name, status, and suggested mapping in view. Complaints, languages, and the synthetic trend each open and close on their own row.

## Why
Those three blocks were stacked in one card, so a label, a quote, and a date read as one paragraph.

## Decisions made
- No new data. The same strings stay on the page, including the ones the review tests look for, because they sit in the row that is always shown.
- Confirm and Reject stay where they were.

## Docs updated
- [ ] MODULE.md of: none (frontend only)
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
Browser check of `/autopsy`: a cluster row opens and closes, and the status fields stay visible.

## Open issues / next step
None.

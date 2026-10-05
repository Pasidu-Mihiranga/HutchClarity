# 2026-10-05 - console - autopsy cards and sidebar mark

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | R5 frontend (console) |
| PR / commit | uncommitted |
| Units touched | frontend console |

## What changed
- The sidebar mark is the Hutch Clarity wordmark, left-aligned in the sidebar. The black field around the supplied image was removed so it sits on the sidebar surface.
- Complaint Autopsy labels complaints, method, status, suggested mapping, languages, masked examples, and the synthetic trend. The same strings the page already showed stay visible.

## Why
The wordmark was a small icon plus type. Cluster fields were unlabeled lines, so a count, a language, and a date read as one sentence.

## Decisions made
- No new data. Review buttons and the hypothesis label are unchanged.
- The wordmark file replaces `public/hutch-clarity-logo.png`.

## Docs updated
- [ ] MODULE.md of: none (frontend only)
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
Browser check of the sidebar mark and `/autopsy` signed in as the local owner account.

## Open issues / next step
None.

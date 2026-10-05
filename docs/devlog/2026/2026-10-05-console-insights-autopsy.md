# 2026-10-05 - console - insights autopsy table

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | R5 frontend (console insights) |
| PR / commit | uncommitted |
| Units touched | frontend console |

## What changed
- The Insights Complaint Autopsy block is a table: cluster, complaint count, status label, and suggested rule. Counts above it are the clusters, complaints, and unreviewed rows the workspace already returns.

## Why
The same fields were one unlabeled line, so a size, a status, and a rule id could not be told apart.

## Decisions made
- No new fields. Status text is `status_label`. A missing rule shows `mapping_label` (`NEW / UNMAPPED PATTERN`).
- The review actions stay on `/autopsy`. This panel links there.

## Docs updated
- [ ] MODULE.md of: none (frontend only)
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
Browser check of `/insights` signed in as the local owner account.

## Open issues / next step
None.

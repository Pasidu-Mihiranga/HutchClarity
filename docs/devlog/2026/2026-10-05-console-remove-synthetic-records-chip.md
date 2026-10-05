# 2026-10-05 - console - remove Synthetic records chip

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | E2 (console shell) |
| PR / commit | (local) |
| Units touched | frontend/apps/console |

## What changed
- Removed the sidebar "Synthetic records" label from `RoleSwitcherBar`.
- Removed the matching badge on Insights money-at-stake.
- Updated desk-provenance e2e assertions that expected that chip.

## Why
Shell-wide chrome duplicated page-level synthetic provenance and cluttered the session foot.

## Decisions made
- Page-level labels stay (desk copy, autopsy SYNTHETIC DATA, foresight scenario badges, "Counts from synthetic cases").

## Docs updated
- [x] Devlog (this file)

## Tests
- Grep: no remaining "Synthetic records" UI strings.

## Open issues / next step
None.

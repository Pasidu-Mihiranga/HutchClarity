# 2026-10-05 - console - consistent page titles across tabs

| Field | Value |
|---|---|
| Author(s) | agent: Composer |
| Work package | E2 (console shell) |
| PR / commit | local |
| Units touched | frontend/apps/console |

## What changed
- Added shared `PageHeader` (`font-display text-3xl font-semibold tracking-tight`).
- Wired every workspace tab through it: Cases, Insights, Autopsy, Foresight,
  Studio, Offers, Audit, Admin.

## Why
Audit used a plain `text-2xl` title while Admin used display `text-3xl`. Roles
that only see a subset of tabs were getting a different product look per page.

## Decisions made
- Landing `/` keeps the larger hero title; AccessDenied / sign-in stay their own size.
- Optional meta chips (counts, SYNTHETIC labels) sit beside the title, not above
  in a different type scale.

## Docs updated
- [x] Devlog (this file)

## Tests
Not run (markup/class alignment only).

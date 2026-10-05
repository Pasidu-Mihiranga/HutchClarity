# 2026-10-05 - customer - family profile data

| Field | Value |
|---|---|
| Author(s) | agent: Cursor Grok 4.7 |
| Work package | customer phone UI |
| PR / commit | uncommitted |
| Units touched | http, customer-web |

## What changed
- Settings has an Elder view switch. It only changes text size and button size.
- Opening a family profile loads that person's balance, pack, cases and receipts.
- Reloads and pack changes apply to the open profile.

## Why
Choosing an elder was enlarging the account holder's screen, and Home still showed the holder's own records.

## Decisions made
Family links stay on the signed-in account. The open profile is used only for the records on screen.

## Docs updated
- [ ] MODULE.md of: n/a
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough: not re-verified
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
API restarted. Not run under make check.

## Open issues / next step
A linked number with no demo account still has no bills to show.

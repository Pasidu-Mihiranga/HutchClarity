# 2026-10-05 - customer - family profiles

| Field | Value |
|---|---|
| Author(s) | agent: Cursor Grok 4.7 |
| Work package | customer phone UI |
| PR / commit | uncommitted |
| Units touched | customer-web, mock store, http |

## What changed
- A family link stores elder or child, and the account stores which profile is open.
- The profile menu switches to that person. Elders and children get a large card home. The signed-in person keeps the full app.
- Home and Settings show the full number.

## Why
A single senior switch made the whole app simple. The account holder needs the full app, and each family number needs its own guided home.

## Decisions made
The role sits on `family_links.role`. The open profile sits on `accounts.active_profile_msisdn`. Existing databases gain those columns on startup.

## Docs updated
- [ ] MODULE.md of: mock store not a module page
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough: not re-verified
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
Not run. The API was restarted so the new routes load.

## Open issues / next step
Add an elder or a child in Settings, then choose them from the profile menu.

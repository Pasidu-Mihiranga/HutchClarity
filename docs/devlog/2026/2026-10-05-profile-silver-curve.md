# 2026-10-05 - customer - profile silver and dial curve

| Field | Value |
|---|---|
| Author(s) | agent: Cursor Grok 4.7 |
| Work package | customer support screen |
| PR / commit | uncommitted |
| Units touched | customer-web header, clarity |

## What changed
- The profile menu no longer shows the balance.
- Silver and its medal use a blue-silver colour. Simulated stays muted.
- The question wheel bends sooner: a row starts to tilt as soon as it leaves the middle.

## Why
The balance was not wanted on that menu, Silver read as plain text, and the wheel curve started too late.

## Decisions made
Silver is a fixed blue (`#4A90C2`) so it stays blue on both light and dark surfaces.

## Docs updated
- [ ] MODULE.md of: n/a, UI only
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough: not re-verified
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
Browser check: the menu shows the name, number, blue Silver, and Sign out. A question just off the middle already tilts.

## Open issues / next step
None for this screen.

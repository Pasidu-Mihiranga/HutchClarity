# 2026-10-05 - customer - theme flash

| Field | Value |
|---|---|
| Author(s) | agent: Cursor Grok 4.7 |
| Work package | customer theme |
| PR / commit | uncommitted |
| Units touched | customer-web layout, ui theme |

## What changed
- A small script in the page sets `data-theme` from the saved choice before the first paint.
- The theme provider applies that choice before paint, not after.

## Why
A click loaded the system dark colours for a moment, then jumped to the saved light or dark override.

## Decisions made
System is still the default when nothing is saved. Only an explicit light or dark choice is written onto the document early.

## Docs updated
- [ ] MODULE.md of: n/a, UI only
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough: not re-verified
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
The login HTML includes the boot script. Not clicked through in the browser.

## Open issues / next step
None for this flash.

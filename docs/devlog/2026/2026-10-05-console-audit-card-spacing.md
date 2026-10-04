# 2026-10-05 - console - audit card spacing

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | R5 frontend (console) |
| PR / commit | uncommitted |
| Units touched | frontend console |

## What changed
- Alerts and Access share one column. Monitors and Recovery share the other. Each column stacks with the normal gap, so a tall card no longer pushes the card below its neighbour down the page.
- Desk copy (notes, metrics, inner rows, quotes, plain lists) sits on a light fill with a little extra line height. The rule is on the console workspace, so every section uses it.

## Why
Monitors is shorter than Alerts. The shared row kept Recovery aligned with Access, which left a large gap between Monitors and Recovery.
Body text was the same white as the card, so a note and a value read as one block.

## Decisions made
- Copy, test ids, and permission messages are unchanged. The grid still places the four panels in the same order.

## Docs updated
- [ ] MODULE.md of: none (frontend only)
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
Browser check of `/audit` after the layout change.

## Open issues / next step
None.

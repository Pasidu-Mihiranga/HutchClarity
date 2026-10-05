# 2026-10-05 - customer chat - restore the question wheel

| Field | Value |
|---|---|
| Author(s) | agent: Cursor Grok 4.7 |
| Work package | customer support screen |
| PR / commit | uncommitted |
| Units touched | customer-web clarity |

## What changed
- The question wheel is back to the previous tilt, depth and scale.
- A circular ease covers only the first part of the move, so a row leaves the middle smoothly.

## Why
The stronger curve bent the cards too far.

## Decisions made
Edge travel stays the same as the previous wheel. Only the start is blended with a circular ease.

## Docs updated
- [ ] MODULE.md of: n/a, UI only
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough: not re-verified
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
Not re-run in the browser. The formula matches the previous wheel at the edges.

## Open issues / next step
None for this screen.

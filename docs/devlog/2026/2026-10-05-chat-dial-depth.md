# 2026-10-05 - customer chat - topic list and dial depth

| Field | Value |
|---|---|
| Author(s) | agent: Cursor Grok 4.7 |
| Work package | customer support screen |
| PR / commit | uncommitted |
| Units touched | customer-web clarity |

## What changed
- Topic choices are a normal scroll list at full strength. They no longer use the faded dial.
- Speak is a microphone button. The word is only the accessible name.
- Suggested questions still scroll as a wheel. The row in the middle comes forward. Rows leaving it tilt back and sink on the depth axis.

## Why
The topic list was faded out, and the question wheel was enlarging the wrong row.

## Decisions made
Depth uses the card's position on screen, not its offset inside the scroll box, so the front row is the one in the middle of the list.

## Docs updated
- [ ] MODULE.md of: n/a, UI only
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough: not re-verified
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
Browser check on a phone-sized support screen: topics render at full opacity, Speak has no visible label, and the question nearest the middle is the largest.

## Open issues / next step
None for this screen.

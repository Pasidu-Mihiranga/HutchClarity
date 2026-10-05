# 2026-10-05 - customer - senior mode

| Field | Value |
|---|---|
| Author(s) | agent: Cursor Grok 4.7 |
| Work package | customer phone UI |
| PR / commit | uncommitted |
| Units touched | customer-web |

## What changed
- The Larger text checkbox is a Senior mode switch. It still saves `large_text`.
- After login, that flag sets `data-senior="on"` on the document.
- Senior mode uses larger type, taller taps, and roomier cards. Home keeps Reload and Support. The bar keeps Home, Support, and Settings.
- Chat cards, the field, and the mic grow. The wheel motion is unchanged.

## Why
The checkbox saved a preference and never changed the screen.

## Decisions made
No new account field. The existing `large_text` flag is the senior switch, so a later login restores it.

## Docs updated
- [ ] MODULE.md of: n/a, UI only
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough: not re-verified
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
`useMe` unit tests, if the disk had room to run them.

## Open issues / next step
Turn the switch off to get the previous home and five-tab bar back.

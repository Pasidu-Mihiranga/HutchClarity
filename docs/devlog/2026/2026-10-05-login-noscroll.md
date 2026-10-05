# 2026-10-05 - customer login - no page scroll

| Field | Value |
|---|---|
| Author(s) | agent: Cursor Grok 4.7 |
| Work package | customer sign-in UI |
| PR / commit | uncommitted |
| Units touched | customer-web login, globals.css |

## What changed
- Restored the missing `@keyframes otp-shake` block that broke the customer app build.
- Sign-in and OTP stay inside the phone frame. The page does not scroll. The hero shrinks first, and the form, status, and simulated inbox keep their height.

## Why
The support-screen CSS edit left a stray `}` in `globals.css`. On a phone the number and OTP screens were taller than the frame and scrolled.

## Decisions made
On a short screen (under 680px tall) the subtitle and city line are hidden so the code and the simulated inbox stay on screen.

## Docs updated
- [ ] MODULE.md of: n/a, UI only
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough: not re-verified
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
Browser check on the running customer app: iPhone SE (375x667), iPhone 16 (393x852) and Pixel 9 (412x892). Number step and OTP step: document scroll height matched the viewport, and the OTP field plus simulated inbox stayed inside the frame.

## Open issues / next step
None for this screen.

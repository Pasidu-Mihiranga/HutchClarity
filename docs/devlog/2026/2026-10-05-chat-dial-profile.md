# 2026-10-05 - customer chat - dial list and profile

| Field | Value |
|---|---|
| Author(s) | agent: Cursor Grok 4.7 |
| Work package | customer support screen |
| PR / commit | uncommitted |
| Units touched | customer-web clarity, AppHeader |

## What changed
- Suggested questions are a taller centered list. Scrolling scales the middle row up and fades the rows above and below. Each row uses a topic icon.
- The chosen topic sits inside the field, to the left of the text. Topic rows use the same icons.
- A short line under the field says not to share an OTP or password. No hotline number is shown.
- History opens as frosted glass under the header, so the logo and profile stay visible.
- The profile menu shows the full number, the balance as Rs, one simulated Silver badge, and a sign-out icon.

## Why
The topic chip sat above the field, every card said Rs, history covered the header, and the profile listed three loyalty tiers over a masked number.

## Decisions made
There is no confirmed Hutch hotline in the product, so the line under the field is a confidentiality reminder. Loyalty stays a single simulated Silver badge because no loyalty system is connected.

## Docs updated
- [ ] MODULE.md of: n/a, UI only
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough: not re-verified
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
Browser check of the support screen after the stylesheet compiles.

## Open issues / next step
None for this screen.

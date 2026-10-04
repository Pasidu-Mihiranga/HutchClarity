# 2026-10-05 - E2 - IgniteX light theme and the desk sign-in portal

Written by an AI coding agent (Claude Code) for its own change.

## What changed

- `@clarity/ui` light tokens follow the HUTCH IgniteX page (hutch.lk/ignitex):
  white and #f6f7f9 surfaces, #e1e5e9 lines, #171a1f text, #ff6601 as the
  brand accent, 8/12/20/28px radii, soft long shadows, Inter for headings.
  White text stays on the deeper orange (`--c-primary`, 5.2:1), because white
  on #ff6601 is 2.9:1 and fails AA. All contrast pairs in `tokens.test.ts`
  were recomputed: none below 4.5:1.
- Customer web, console and verify pin `data-theme="light"`, so a device in
  dark mode no longer turns the apps dark.
- Clarity Desk: without a session every page is `SignInPortal`, a grid of
  role cards beside the sign-in form. Picking a card fills the synthetic
  account (username, password, step-up code) and focuses Sign in. The cards
  appear only when `GET /v1/auth/sign-in-methods` reports the simulated
  directory (I9); the server still checks the password and assigns the role.
- e2e `signInOnDesk` waits for the desk to settle (signed in or the form)
  instead of a fixed 2s, which lost the race while a stored session was
  being checked.

## Validation

- tsc for console, customer-web and verify: clean.
- Full Playwright suite including axe: 43 passed.
- Screenshots of the portal at 1366px and 390px, and the customer login.

## Next step

Confirm the live staff directory uses the synthetic passwords; it is a
separate private file on the server.

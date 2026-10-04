# 2026-10-04 - SMS03 - Show the inbox only for simulated delivery

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | SMS01 follow-up |
| PR / commit | pending |
| Units touched | customer-web sign-in |

## What changed

- Hide the simulated SMS inbox before an OTP request and for live httpSMS
  delivery.
- Show it only when the API says that exact request used simulated delivery.
- Added browser assertions for the hidden-before-request and visible-synthetic
  states.

## Why

The production sign-in page displayed a simulated inbox while a linked test
phone used real SMS delivery. The API already reports which delivery route was
used, so the page must reflect that response instead of implying simulation.

## Decisions made

- Delivery disclosure comes from the OTP response and is reset after any
  failed request.

## Docs updated

- [x] Customer sign-in behavior recorded here
- [ ] MODULE.md: no domain module behavior changed
- [ ] ARCHITECTURE.md / modules.md: no architecture change
- [ ] CHANGELOG.md / contracts: no public contract change
- [ ] Plan via CHANGES.md: no plan change

## Tests

- `npm run e2e -- --grep "wrong code is refused"`: 1 passed.
- Customer, console and receipt-verifier production builds completed. Next.js
  emitted its existing optional SWC lockfile patch warning.
- `make check`: 2,415 passed, 633 skipped; lint, formatting, typing and import
  contracts passed.

## Open issues / next step

Deploy and verify the linked-phone page reports live delivery without rendering
the simulated inbox.

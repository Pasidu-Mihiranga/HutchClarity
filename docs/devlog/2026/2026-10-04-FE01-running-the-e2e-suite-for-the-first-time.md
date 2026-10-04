# 2026-10-04 - FE01 - Running the e2e suite for the first time

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus) ran it, fixed what it found, wrote this |
| Work package | FE01 (issue #28) |
| PR / commit | #28 |
| Units touched | frontend/packages/sdk, frontend/apps/customer-web, frontend/e2e |

## What changed

- `@axe-core/playwright` and `frontend/e2e/accessibility.spec.ts`: five pages
  audited, failing on serious and critical violations and reporting the rest.
- `frontend/e2e/session.ts` and `login.spec.ts`: one sign-in per run.
- Four product fixes, each found by running the suite.

## Why

The Playwright suite was written for C05 (#24) and **had never been executed**:
the browser download stalled in an earlier session, so it was committed,
compiled and never run. The first real run failed 7 of 8 tests.

## What it found

1. **Customer-web sign-in had never worked.** `ClarityClient.verifyOtp` posted
   `{ msisdn, code }`; `OtpVerify` requires `challenge_id`, so every verify
   returned 422. Fixed by taking the `challenge_id` from `requestOtp`.
2. **A failed sign-in wrote a fake session.** The catch branch stored
   `clarity_token = "demo-token"` and reported "placeholder login accepted
   locally". That is what hid defect 1 for as long as it existed, and it left
   the customer half-signed-in with a token the backend refuses. Deny by
   default applies to the UI too (I9), so a refusal now clears the session.
3. **The login page told customers something false.** A static panel read
   "Any 6-digit code works in demo mode". It does not: the backend generates a
   code per challenge and answers 401 to anything else. The panel now reads the
   simulated inbox, shows the code and prefills it.
4. **Three chat buttons showed raw i18n keys.** `fuSubs`, `fuPrevent` and
   `fuSupport` reached the customer as button labels, because `FollowUps` did
   `fu.i18n_key in EN ? tl(...) : fu.i18n_key` and those keys lived in the chat
   page's catalogue rather than the component's. The keys moved, and the
   fallback now humanises an unknown key instead of leaking an identifier.
5. **API errors rendered as `[object Object],[object Object]`.** FastAPI
   reports a validation error as a list of field errors, and the SDK assigned
   it straight to a message. Flattened to `field: reason`.

## Two test premises that were wrong, not the product

- **The suite asserted a journey nav on the first turn.** The first turn is
  answered statelessly and opens the case; there is nothing to attach state to
  until the case exists, so the flow runs from the next turn. The dispute test
  now follows the affordance a customer is shown (the remedy button), which
  opens the confirm sheet, and asserts on that.
- **"What is the fair use policy?" is not a knowledge question.** It routes to
  `account` and is answered from this customer's own FUP status, which is a
  correct answer with nothing to cite. The knowledge test now asks "How do I
  activate a data package?", which routes to `knowledge`.

## A structural problem in the suite

The OTP service allows five challenges per number per fifteen minutes
(`MAX_REQUESTS_PER_WINDOW`, the TH1 mitigation). Every test signed in, and the
suite is larger than five, so later tests failed on a 429 that had nothing to
do with what they tested. Sign-in now happens once per run against the API and
the token is injected into `sessionStorage` before each page loads.
`storageState` cannot carry it: Playwright persists cookies and `localStorage`,
and this app keeps the token in `sessionStorage` so it dies with the tab. One
test still drives the login page itself, because something has to.

## Tests

```
make check                   1994 passed, 544 skipped
frontend npm run build       3 apps, compiled successfully
e2e, first ever run          1 passed, 7 failed
e2e, after the fixes         9 passed (16.0s)
```

All five axe audits pass with no serious or critical violations, and the
dispute journey reaches a verified receipt in the browser.

## Two more defects, found by the last two failing tests

6. **A grounded answer showed no source.** The server returns `citation` on
   every article in `SOURCE@version` form, and the knowledge card dropped it: a
   customer read an answer taken from a policy document with no way to tell
   which document or which version. K03 built the citation machinery and the UI
   never surfaced it, which means C05 was closed with its "citations" scope
   incomplete. Now rendered as a labelled `Sources` region.
7. **White on the brand orange fails WCAG AA.** axe measured `#ffffff` on
   `#f26226` at **3.2:1** against the 4.5:1 that normal-size text needs, on the
   customer's own message bubble and two buttons. `--orange` stays as it is for
   fills, borders and icons, where no text sits on it; a new `--orange-strong`
   (`#c2410c`, **5.2:1**) carries white text. The token's comment says which is
   which, so the next person does not reintroduce it.

   This is a brand-adjacent change and worth flagging: the orange a customer
   sees behind white text is now slightly darker than `#f26226`. The
   alternative was to leave a serious accessibility violation in the one screen
   where a customer commits to money moving. **REQUIRES HUTCH CONFIRMATION**
   that the darker shade is acceptable for text surfaces.

## Open issues / next step

- **Next.js 14 to 16 is not done.** 16.3.8 is current and accepts React 18.2,
  so it is feasible without forcing React 19, but it has not been attempted.
- **`interfaces/http/static` is not retired.** The scope says "once parity is
  shown". The browser suite now passes, which is the parity evidence, but the
  static UI is still referenced by WT-13 as a desk fallback and by the demo
  path. Retiring it is a separate change that has to update those first.
- **The si/ta native-speaker review has not happened** and cannot be done here.
  It needs a human who speaks Sinhala and Tamil. The leaked-key defect above is
  a reminder that the catalogues are not reviewed: three customer-facing labels
  were identifiers, in every language.
- **The e2e suite is not in CI.** It needs a browser download and two servers.
  Adding it as a job is the obvious next step now that it passes.

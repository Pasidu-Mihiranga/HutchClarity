# 2026-10-05 - E4 - customer-web on the customer's real account

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga |
| Work package | Workstream E4 (enterprise UI plan) |
| PR / commit | feat/enterprise-ui |
| Units touched | frontend/apps/customer-web, frontend/e2e |

Written by an AI coding agent (Claude Code) under AGENTS.md §12.

## What changed

New `lib/useMe.ts`: one hook over `GET /v1/me/app`, which the SDK documents as the only customer read. Every `/v1/me/*` write returns the refreshed payload, so a write replaces the hook's state and no screen has to guess what changed. A 401 or 403 goes to `expireSession()`; anything else sets an error. **There is no fallback object anywhere in it.**

- **Home** (`app/page.tsx`) was a `const DEMO` literal: name, masked number, balance, pack and one alert, all written into the source, a Reload button with an empty `onClick`, and three of five quick actions pointing at `"#"`. It now renders the payload, Reload opens a dialog that calls `POST /v1/me/reload`, and all five actions go somewhere real.
- **`/cases`** called `client.getCases()`, which the SDK does not have. It threw on every render, the `catch` swallowed it, and the page drew two cases written into the source. It now reads `app.cases`, with a real empty state and a real error state.
- **`/case/[id]`** fabricated `{ cause: "VAS silent renewal", amount: "99.00" }` on failure and showed it behind an "Offline placeholder" chip; "Fix this" had no `onClick`; the receipt link pointed at `/receipt/TR-<case id>`, an id made by string concatenation. It now shows the real decision (cause, amount, rationale, outcome) from `POST /v1/cases/{id}/evaluate`, offers only the action the decision allows, and links to a receipt only when one exists for the case.
- **`/account`** had a hard-coded "07X XXXX XX89", the subtitle "Demo customer", and four menu rows that were buttons with no handler. Sign-out pushed `/login` without telling the API, so the cookie stayed valid. It now shows the real number and name, and Notifications, Safeguards, Family and Network status each write or read through their real route. Sign-out calls `POST /v1/auth/logout`, which owns the cookie.
- **Two new routes** for the quick actions that had nowhere to go: `/packages` (catalogue with purchase, active subscriptions with cancel, both confirmed in a dialog, fair-use terms shown before the purchase) and `/usage` (data, voice and SMS totals plus the account ledger with the balance either side of each line, filterable by bucket).
- **`WhyWidget` lost its defaults.** `cause` and `amount` defaulted to "Pack expired overnight" and "45.00", so a caller that failed to load a decision rendered a card quoting a charge that did not exist. Both are required now.
- **The chat lost its fallback name.** `app.name ?? "Dilani Perera"` greeted anyone with a missing name as Dilani; there is a `chatHiAnon` string in all three languages instead.
- **`CaseRow`** took `cause` and `amount`, which `/v1/me/app` does not carry per case; it takes the `headline` and `outcome` the payload actually has.
- **`AppShell`**: `startsWith("/case")` also matched `/cases`, so the list rendered a back link to itself titled "Case". Fixed, and the new routes get back links.

## Why

The plan's E4. Every one of these was a screen showing a customer a figure no system had produced, in a product whose entire promise is that a charge is explained with evidence (I2, I16). The routes to fix them all existed and the frontend never called them.

## Decisions made

- **`/v1/me/app` for every screen, not the narrower reads.** `myHome`, `myCases` and `myReceipts` still exist and the case page uses `myReceipts`, but the screens that render account state share one payload so Home and Usage cannot disagree about the balance.
- **"Fix this" navigates to the chat rather than confirming in place.** The confirmation token is minted outside the AI path and the chat already does propose-then-confirm properly. A second copy of that flow on the case page is a second copy to get wrong.
- **The reload amounts (100, 200, 500, 1000, 2000) are duplicated in the page.** The API enforces them and answers 422 otherwise, and the refusal is shown verbatim. This is a small I10-adjacent smell: the list belongs in the payload. Logged as a follow-up rather than fixed here, because it needs a backend field.
- **`/usage` sums nothing.** Every figure is the row's or the payload's own. A total this page computed could disagree with the one a decision used.

## Docs updated

- [x] This devlog
- [ ] MODULE.md: n/a (frontend app, no module)
- [ ] CHANGELOG.md: n/a (no `/v1` change; the routes all existed)
- [ ] Walkthrough: WT-01 and the demo script cover these screens and are re-verified at the end of the workstream, with `make e2e` in E6

## Tests

- `tsc --noEmit` clean in all five workspaces.
- `npm run build -w @clarity/customer-web`: compiles, 11 routes including the new `/packages` and `/usage`.
- `npm test -w @clarity/customer-web`: 4 passed (chat copy parity; Sinhala and Tamil coverage still above baseline with `chatHiAnon` added).
- `e2e/accessibility.spec.ts` gains axe runs for `/packages` and `/usage`.
- Not run: `make e2e`. E6 executes the browser suite.

## Open issues / next step

E6: component tests for these pages, e2e for the new routes, a mobile viewport project, and getting `npm run lint` to work at all (no app has an ESLint config, so `next lint` prompts and exits 1).

Follow-up for a backend package: put the allowed reload amounts in `/v1/me/app` so the sheet stops restating a server rule.

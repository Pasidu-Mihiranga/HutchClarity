# 2026-10-04 - FE01 - The chat never read the account, so three journeys could not happen

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code |
| Work package | FE01 (#28), migration step R5 |
| PR / commit | branch `claude/affectionate-hamilton-ww2hgz` |
| Units touched | frontend (customer-web, e2e) |

## What changed

- `apps/customer-web/app/clarity/page.tsx` fetches `GET /v1/me/app` and holds
  the signed-in customer's own account. It used to hold a hardcoded literal
  with `activity: []`, declared `const [app] = useState(...)` with no setter,
  so it could never be anything else.
- The chat's greeting uses the customer's name instead of the constant
  `"Dilani Perera"`.
- `BASE` is exported from `lib/clarityChat.ts` rather than redeclared.
- `e2e/journeys.spec.ts` adds the two demo journeys the suite was missing:
  AUTO_FIX (Nimal's duplicate reload) and EXPLAIN_ONLY (Kumar's fair-use cap).
- `e2e/session.ts`: `customerTokenFor(request, msisdn)` replaces the
  Dilani-only `customerToken`, cached per subscriber. Each number has its own
  OTP challenge budget, so one global cache could not serve four journeys.

## Why

FE01 acceptance 1: "the four journeys driven in the Next.js apps pass in
Playwright". Two were covered. Writing the other two showed they could not
pass, for a reason that was not a test problem.

## Decisions made

- **The gate that broke it.** `accountIntents(app)` in `lib/clarityChat.ts` is
  a client-side heuristic that reads `app.activity`, `app.subscriptions` and
  `app.pack` to decide whether a question is worth evaluating. If it says no,
  the chat renders "Could not confirm" and **never calls evaluate**, so the
  rule engine is never asked. With `activity: []` baked in, it answered `false`
  for `twice`, `slow`, `sub` and `missing` for every customer on every run.
  Only `balance` and `knowledge`, hardcoded `true`, ever got through. That is
  why Dilani's journey passed: her question routes to `balance`. Three of the
  four journeys were unreachable through free-text chat.
- **What the customer saw.** Measured against the same running backend:

  | Subscriber | Backend decision | What the chat said |
  |---|---|---|
  | Nimal, duplicate reload | `AUTO_FIX`, LKR 3,500.00 | "We did not find a reload that was taken twice on this number." |
  | Kumar, fair-use cap | `EXPLAIN_ONLY`, LKR 0.00 | "Your data is not slowed by a fair-use cap right now." |

  Kumar's cap was active. The page stated the opposite of the customer's own
  account state.
- **Minimal fix, and what it does not do.** The page now feeds that heuristic
  real data. The heuristic itself stays, and it should not: I1 says rules
  decide causes and eligibility, and a TypeScript function in a browser
  deciding whether a case is worth evaluating is the wrong side of that line.
  Removing it means reworking how the chat renders a backend "no cause found",
  which is larger than this issue. Recorded as a follow-up rather than done
  quietly.
- **Two more places that invent data**, found while reading this path and left
  alone as out of scope, both recorded below: `app/cases/page.tsx` renders two
  hardcoded demo cases whenever its fetch returns nothing, and it always does,
  because there is no `GET /v1/cases` endpoint and no SDK method for it. The
  account page's pack figures come from the same hardcoded literal this change
  removed from the chat.

## Docs updated

- [x] MODULE.md of: none (frontend apps have none; `docs/modules.md` row is
      unchanged, the apps' status did not change)
- [x] CHANGELOG.md: a Fixed entry
- [x] FE01 issue file: acceptance 1 is now met, and the follow-ups are listed
- [ ] ARCHITECTURE.md / modules.md: not needed, no structural change
- [ ] Plan via CHANGES.md: not needed, no plan chapter changed

## Tests

- Browser suite: **16 passed** (14 before, plus the two new journeys).
- Both new tests fail before this change: Nimal's on the missing investigation
  card, Kumar's on the "not slowed by a fair-use cap" text. Captured from the
  run before the fix.
- `npm run build`: all three apps compile. `tsc --noEmit` on customer-web:
  clean (this app is not in `npm run typecheck`, which covers only
  `packages/sdk`; a pre-existing gap noted in the C05 devlog).
- Backend untouched by this change.

## Open issues / next step

- **`accountIntents` should not exist.** The decision belongs to the backend
  (I1). The chat should evaluate and render what comes back, including a
  genuine "no cause found". Needs its own issue.
- **`GET /v1/cases` does not exist**, so `app/cases/page.tsx` can never show a
  customer their real cases and falls back to two fabricated rows ("VAS silent
  renewal LKR 99.00", "Duplicate data charge LKR 45.00"). It calls
  `client.getCases?.()`, a method the SDK does not have, so the fallback is
  unconditional. Needs an endpoint, an SDK method and the page wired to it.
- The usage card renders "- / 50.00 GB" for Kumar: `used_gb` is missing from
  the pack payload the card reads.

# 2026-10-04 - CI - the browser suite was rate limiting itself

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code, for Pasidu Mihiranga |
| Work package | CI (the `browser journeys and accessibility` job on main) |
| PR / commit | branch `fix/e2e-sign-in-throttle` |
| Units touched | Makefile, backend/scripts, frontend/e2e |

## What changed

- **`backend/scripts/e2e_policy.py` is committed and wired.** It already existed as an untracked file in a working tree, written and never finished: nothing referenced it, so it did nothing.
- **`make dev-e2e` builds the copy and points `CLARITY_POLICY_DIR` at it**, which is what actually makes it take effect.
- **The script raises all four throttle keys**, not only `throttle.auth.per_minute`.
- **`.gitignore`** ignores the generated `backend/.e2e-policy/`.
- **`frontend/e2e/login.spec.ts`** asserts the session cookie rather than `sessionStorage`.

## Why

`ci / browser journeys and accessibility` has been failing on main since workstream B merged: **19 failed, 23 passed**. Reproduced locally on `origin/main` before changing anything, and the counts matched the CI run exactly.

The cause is `throttle.auth.per_minute`, added by B6. It bounds sign-ins **per caller**, at 10 a minute. Every request the browser suite makes comes from 127.0.0.1, so the whole suite is one caller: 10 a minute is right for a person and far too few for forty specs that each need a session. The failures were `otp request failed: 429` (18) and `staff login failed: 429` (7), none of which has anything to do with what those specs test.

## Decisions made

- **A policy value, not a code path** (I10). The copy raises the limits to their **guardrail maxima**; the limiter still runs and is still resolved from the policy store. A suite that ran with the limiter disabled would not notice the day a limiter starts refusing a request it should allow, which is the regression this is one bad commit away from.
- **The committed policy is never touched.** Only `make dev-e2e` reads the copy, and the copy is generated and git-ignored, so it cannot drift from its source or be reviewed as if it were policy.
- **All four keys, not one.** Raising only `throttle.auth.per_minute` took the suite from 19 failures to 14: the next binding limit is `throttle.anonymous.per_minute` (45), the ceiling for a caller with no session across every throttled route together, and the suite is exactly that until it signs in. The chat specs then reach the conversation and knowledge limits the same way. Measured, not assumed: 19 → 14 → 2.
- **`login.spec.ts` asserted a security property that B4 deliberately removed.** It checked `sessionStorage.getItem("clarity_token")` was truthy after signing in. B4 moved the session to an `HttpOnly` cookie precisely so that is never true, and `app/login/page.tsx` says so in a comment. The spec now asserts the cookie exists, that it is `HttpOnly`, and that the token is **not** also left in `sessionStorage`. `session.ts::signedIn` was already updated for B4; these two specs were missed.

## Tests

Measured on `origin/main` in a clean worktree, with a real browser:

| State | Result |
|---|---|
| main, unchanged | **19 failed, 23 passed** (matches the CI run) |
| + `throttle.auth.per_minute` raised | 14 failed, 28 passed |
| + all four throttle keys raised | 3 failed, 39 passed |
| + `login.spec.ts` corrected | **2 failed, 40 passed** |

No `429` remains anywhere in the output.

## Open issues: the two that are left

Both are pre-existing defects from workstream B, unrelated to the throttle, and both need a decision rather than a quick fix. Neither is fixed here.

### 1. A refused session cookie is never cleared (`session-expiry.spec.ts:19`)

The spec is named "a refused token is cleared and the customer is sent to sign in". The customer **is** sent to sign in; the token is **not** cleared.

Before B4 the token lived in `sessionStorage` and the page cleared it. Now it is an `HttpOnly` cookie, so the page cannot, and nothing else does: `interfaces/http/cookies.py` defines `CUSTOMER_COOKIE` and no helper that clears it, and nothing calls one. Verified by seeding a cookie the server never issued and reading it back after the redirect; it survives, value intact.

The spec still passes its stale `sessionStorage` assertion vacuously, so it fails on the redirect timing rather than naming the real problem.

**Proposed fix:** the API clears the cookie on a 401 against a cookie-borne session, with `Set-Cookie` and a past expiry. That is an auth change in workstream B's area and it interacts with CORS (the app is on :3100 and the API on :8100), so it is proposed rather than done.

### 2. The desk sign-in form never appears (`audit-console.spec.ts:151`)

`signInOnDesk` times out waiting for the `Username` field, on the **third** sign-in in that file; the first two pass. The helper clicks "Sign out" first when it is visible, and B1/B2 changed signing out to tell the API and follow the provider's logout. The likely cause is that the sign-out now navigates somewhere the helper does not wait for, so the form is not on screen yet.

Not investigated beyond that, because it is console auth and a guess would be worse than a measurement.

## Next step

- Decide on the cookie-clearing fix above; it is the one with a customer-visible consequence, since a stale cookie means the redirect repeats on every navigation.
- Until both land, `ci` stays red on main and `deploy demo VPS` keeps skipping, because it only runs on a successful `ci`.

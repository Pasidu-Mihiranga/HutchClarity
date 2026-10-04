# 2026-10-05 - CI - Two browser tests asserting retired behaviour

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga; agent: Claude Code |
| Work package | Follow-up to C4, D4 and B4 |
| PR / commit | fix/e2e-foresight-and-session-expiry |
| Units touched | frontend/e2e |

## What changed

- `e2e/autopsy-foresight.spec.ts`: the Foresight test signs in as **CX**, not
  Supervisor, and asserts what the rewritten page shows. Added a companion
  test that a supervisor gets no Foresight link at all.
- `e2e/session-expiry.spec.ts`: the refused-session test plants a bogus
  **cookie** instead of a `sessionStorage` key, and no longer asserts the app
  clears it.
- `components/ConsoleNav.tsx`: the Foresight link is gated on `foresight:read`
  and the Studio link on `config:draft`/`config:approve`, matching the pages.
- `e2e/session.ts`: added the `CX` and `VAS Ops` logins, which did not exist.

## Why

`main` has been red on "browser journeys and accessibility" since Workstream C
landed: 2 failed, 40 passed. Both failures were tests asserting behaviour that
later work deliberately removed, not regressions.

**Foresight.** C4 gave foresight its own permissions and scoped
`foresight:read` to `PRODUCT` and `CX_ENGINEER`. The spec signed in as
Supervisor, who no longer holds it, so the page answered "access denied" and
the heading it waited for never appeared. The spec also asserted a "Statistical
baseline vs persona swarm" table that `GET /v1/demo/foresight` used to compose
per request; D4 retired that route and the page now reads stored runs and
reports.

`config/staff/synthetic-directory.json` has a `cx` account with role
`cx_engineer`, but `frontend/e2e/session.ts` had no label for it, so there was
no way to sign in as the only role that can reach the page. Added, with the
password verified against `POST /v1/auth/staff/login` rather than assumed from
the naming convention.

**Session expiry.** B4 moved the customer session into an `HttpOnly` cookie.
The test planted `sessionStorage.clarity_token` and asserted the app cleared
it. Both halves had stopped meaning anything: nothing reads or writes that key
any more, so the redirect it saw was really just "no session at all", which the
test above it already covers; and clearing is deliberately not the app's job.
`lib/session.ts` states it outright - the cookie is `HttpOnly`, only the API
can remove it, and a page writing a cookie it cannot read is how you end up
with two.

## Decisions made

- **Updated rather than deleted, with the reason in the test.** Both are
  deliberate contract changes, which AGENTS.md section 10 allows on the
  condition the docstring says why. Each test now carries that explanation.
- **The session-expiry test got stronger, not weaker.** Planting a bogus
  cookie exercises the 401 path through `expireSession`, which the old test
  never reached: a `sessionStorage` key the app ignores produced the same
  "no session" redirect as visiting logged out. What it no longer asserts is
  the one thing B4 made impossible.
- **Did not grant `foresight:read` to Supervisor.** That would have made the
  test pass by changing the permission model, which is the wrong direction.
  C4 separated these jobs on purpose: a supervisor approves money, rehearsing
  a change is product's work.
- **Added the negative case, and it found a real defect.** `ConsoleNav` gated
  the Foresight link on `desk:queue:read` while the page requires
  `foresight:read`, so every agent and supervisor was offered a link that lands
  on "access denied". That is a gap D4 opened: the page's gate was changed and
  the nav's was not. The Studio link had the same shape from D3, listing
  `rule:publish`, which compliance holds while holding neither config
  permission. Both now name exactly what their page checks.

  This is why the assertion was worth adding rather than assuming: the first
  version of this fix asserted the link was absent, and CI proved it was not.

## Docs updated

- [ ] MODULE.md: n/a, no module changed
- [ ] CHANGELOG.md: n/a, no `/v1` or public surface change
- [x] This devlog

## Tests

- `tsc --noEmit` on both spec files: clean.
- `npm run build --workspace=apps/console`: clean.
- `cx` and `vasops` sign-in verified against a local API on a spare port,
  returning roles `cx_engineer` and `vas_ops`.
- First CI run of this change: session-expiry fixed (41 passed, up from 40),
  and the two foresight tests failed on the two facts above, both of which
  were assumptions rather than things checked. Corrected here.
- **The suite was not run locally.** `playwright.config.ts` starts the API on
  `127.0.0.1:8100`, and this machine's Windows reserved ranges cover
  8001-8100 and 8101-8200 (`netsh interface ipv4 show excludedportrange
  protocol=tcp`), so uvicorn cannot bind it: `[WinError 10013]`. CI runs on
  Linux and is the check that matters here.

## Open issues / next step

- The port in `playwright.config.ts` is hard-coded, so the browser suite cannot
  be run at all on a Windows machine whose reserved ranges cover it.
  `frontend/e2e/session.ts` already reads `E2E_API_BASE`; making the config
  read the same variable would close that, and is worth doing separately.
- These two specs were the only ones out of date. The suite is otherwise
  passing at 40 tests.

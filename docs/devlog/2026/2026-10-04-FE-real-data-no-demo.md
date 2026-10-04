# 2026-10-04 - FE - Real data everywhere, no demo surfaces

| Field | Value |
|---|---|
| Author(s) | KusalPabasara; agent: Claude Code (Claude Opus 5.5) wrote the change and this entry |
| Work package | customer web and `/v1` naming |
| PR / commit | branch `feat/no-demo` |
| Units touched | `interfaces.http` (route paths, tags, wording), `autopsy` (label), SDK, customer web, console callers, e2e, docs |

## What changed
- Customer web, real data only:
  - home loads `GET /v1/me/home`, and Reload credits the balance through `POST /v1/me/reload`;
  - cases come from `GET /v1/me/app` (the page called an SDK method that does not exist, so it always showed two invented cases);
  - case detail combines `GET /v1/cases/{id}`, the account's case outcome and headline, and the customer's receipts (no invented fallback case, no `TR-<case id>` receipt link, no dead "Fix this" button);
  - account shows the real masked number and notification preference, and its rows link somewhere real ("No outages in your area" was stated without a check);
  - the chat has no fallback name and no fallback number for opening a case.
- Sessions: `lib/session.ts` `authFetch` renews the ten-minute access token with the refresh token the API already issued (one refresh at a time, since refresh tokens rotate), and only a refused refresh goes to sign-in.
- `/v1/demo/*` routes renamed (see `CHANGELOG.md`); OpenAPI tags `demo` became `synthetic`, `autopsy`, `foresight` and `insights`; customer-facing wording that said "demo" now says what it is. The sign-in page labels the code "Your sign-in code" and says SMS is not connected yet.
- The one honest marker stays: "Synthetic data: no real HUTCH account is connected." (I16).

## Why
Requested: no demo surfaces; the product works end to end with real (synthetic) data, with the sign-in code shown until SMS exists.

## Decisions made
- The internal profile name `demo` (ADR-0027) is unchanged; it is configuration, not something a person sees.
- Reload has no idempotency key at the HTTP layer (I8). The page prevents a double submit; making the route itself idempotent is a money-path change for its own PR.
- Historical devlogs and earlier CHANGELOG entries keep the old route names.

## Docs updated
- [x] `CHANGELOG.md`, OpenAPI, golden snapshot and generated SDK
- [x] `autopsy/MODULE.md`, `insights/MODULE.md`, walkthroughs WT-02 and WT-13, READMEs, `docs/submission/DEMO.md` (route names)

## Tests
- `make check`: 2,401 passed; ruff, strict mypy (234 files) and import contracts clean. `make contracts-check`: SDK matches the schema.
- Playwright: 43 passed, including the new `real-data.spec.ts` (3) and a refresh test in `session-expiry.spec.ts`. The accessibility suite caught an inline link distinguished only by colour; it is underlined now.
- All three frontends build.

## Open issues / next step
- Idempotency key on `POST /v1/me/reload` (I8).

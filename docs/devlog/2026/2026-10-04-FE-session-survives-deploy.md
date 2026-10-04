# 2026-10-04 - FE - Sessions survive a deploy; voice listens at once; icons

| Field | Value |
|---|---|
| Author(s) | KusalPabasara; agent: Claude Code (Claude Opus 5.5) wrote the change and this entry |
| Work package | DEP01 #57 follow-up, customer-web polish |
| PR / commit | branch `fix/session-survives-deploy` |
| Units touched | `iam`, `app` (composition), `frontend/apps/customer-web`, `frontend/apps/console`, `frontend/apps/verify` |

## What changed
- `iam.TokenIssuer` takes an optional `key_path`. The composition root passes `KEYS_DIR/iam-issuer.pem` when `KEYS_DIR` is set (the VPS sets `/run/clarity-keys`). The key is written to a temporary file and published with `os.link`, so processes starting together (API, MCP, gateway) share one complete key. `KEYS_DIR` is optional and unset by default, as `SIGNING_KEY_PATH` became, so read-only pods start.
- Customer web: `lib/session.ts`. A 401, or opening the chat without a token, clears the session and goes to `/login?next=...`; the login page returns to `next` (same-origin paths only).
- The chat waits for `GET /v1/me/app` before answering a question.
- Voice: Speak starts listening at once (the tap is the user activation); the "audio goes to Google or Apple" notice stays visible while listening; focus follows the main action; a refusal lands on Try again.
- Icons: `icon-192.png`, `icon-512.png`, `apple-touch-icon.png` and `favicon.ico` for customer web, and `favicon.ico` for the console and verifier. `mobile-web-app-capable` added next to the Apple tag.

## Why
Reported from the live site: 401s on `/v1/me/app`, `/v1/conversation/turn` and `/v1/cases`, 404 icons, and a deprecation warning. The 401s came from the issuer key being generated in memory on every start (ARCHITECTURE known gap 2), so each CD deploy signed every customer out and the chat failed silently. The voice change was requested.

## Decisions made
- Tapping Speak is now the opt-in to listening; the disclosure moved from "before listening" to "while listening". The I13 tension recorded in the voice devlog still applies.
- The empty-account race was found by the e2e suite (fair-use journey failing about 1 run in 3): a fast question was answered from an empty account and told a capped customer they were not capped.

## Docs updated
- [x] `iam/MODULE.md`, `CHANGELOG.md`

## Tests
- `make check`: 2002 passed, 544 skipped; ruff, strict mypy (218 files) and the three import contracts clean.
- New unit tests: a token from before a restart still verifies; 8 issuers starting together share one key (the first version, with `O_EXCL`, let a reader see a half-written file, and this test caught it; 30/30 runs pass after the fix); without `KEYS_DIR` nothing is written.
- Playwright: 30 passed, including the new `session-expiry.spec.ts` (3) and the updated `voice.spec.ts` (6). The fair-use journey passed every repeat after the race fix.

## Open issues / next step
- After this deploys, existing sessions are signed out once (the key changes one last time), then survive later deploys.

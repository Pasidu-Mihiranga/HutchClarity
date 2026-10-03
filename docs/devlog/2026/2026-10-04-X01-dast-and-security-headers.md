# 2026-10-04 - X01 - DAST baseline and the headers it found

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus) ran the scans, wrote the fix and this entry |
| Work package | X01 (issue #42) |
| PR / commit | #42 |
| Units touched | interfaces/http, tests/security, .zap, .github/workflows |

## What changed

- `clarity/interfaces/http/headers.py`: a middleware adding eight security
  response headers, plus `Cache-Control`, to every response.
- `backend/tests/security/test_response_headers.py`: 45 tests.
- `.zap/rules.tsv` and a `dast` CI job running the OWASP ZAP baseline against
  the API started in the job.

## Why

Issue #42's scope includes "OWASP ZAP baseline". Run against the app, the
baseline reported **7 warnings over 60 passes**, six of them missing-header
rules across every page and asset: no `X-Content-Type-Options`, no
`X-Frame-Options`, no CSP, no `Permissions-Policy`, no COEP, and
`Insufficient Site Isolation Against Spectre`.

None is exploitable alone. Together they are the difference between a browser
that enforces the app's intentions and one that guesses. The one that matters
most here is framing: a confirm button or a receipt inside someone else's
iframe is a customer tapping one thing and getting another.

## Measured

| Run | Fails | Warnings | Passes |
|---|---|---|---|
| Before | 0 | 7 | 60 |
| After the headers | 0 | 3 | 64 |
| After the rules file | 0 | 0 (3 ignored, with reasons) | 64 |

`Insufficient Site Isolation Against Spectre Vulnerability [90004]` moved from
warning to pass.

## Decisions made

1. **Fixed, not suppressed.** Six of the seven findings were real and cheap to
   fix. A rules file full of ignores would have turned the scan into a
   formality. Only three remain ignored, each with its reason in the file:
   `Non-Storable Content` (we refuse caching of customer data on purpose),
   `CSP style-src unsafe-inline` (the static UI that FE01 retires uses inline
   styles; `script-src` has none, which is the directive that stops injected
   script), and `Modern Web Application` (informational).
2. **The job scans where the app runs, not "staging".** The issue says
   "ZAP baseline on staging" and there is no staging environment. Claiming one
   would be worse than saying so. The `lite` profile needs no services
   (ADR-0006) and serves the same routes, headers and static UI, which is what
   a baseline looks at. The job comment says exactly this.
3. **The job checks the app answered before scanning.** ZAP against a dead port
   reports a clean scan, which is the same failure mode as the `full` lane
   silently skipping.
4. **`setdefault`, not assignment.** A route with a deliberate header policy
   keeps it.
5. **`no-store` by default, `max-age` for public assets.** A case, a decision
   or a receipt must not sit in an intermediary; `no-store` on `/static` and
   `/openapi.json` would be a performance bug dressed as security.
6. **`script-src` has no `unsafe-inline`,** and a test asserts it, because a
   CSP that allows inline script is decorative.

## Docs updated

- [ ] MODULE.md - `interfaces/http` has no MODULE.md (it is an interface, not a module)
- [ ] CHANGELOG.md - no `/v1` contract change; headers are added to existing responses
- [x] This devlog entry

## Tests

```
backend/tests/security/   94 passed (49 threat and replay, 45 headers)
make check                1986 passed, 544 skipped
ZAP baseline              0 fails, 0 warnings, 3 ignored, 64 passes, exit 0
```

The header tests run against `/health`, `/`, a static asset, a `/v1` route and
a 404, because middleware that stops short of error responses is the usual way
this regresses.

## Open issues / next step

- The CSP still allows `style-src 'unsafe-inline'` for the static UI. When
  FE01 (#28) retires that UI, tighten it and remove rule 10055 from the file.
- The baseline is passive. An active scan (`zap-full-scan.py`) would exercise
  injection and authentication, and needs a seeded account and a longer budget;
  worth a nightly job rather than a per-push one.

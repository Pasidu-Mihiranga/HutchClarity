# 2026-10-04 - B3 to B7 - sessions, keys, SMS, CSRF and authorization assurance

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga; agent: Claude Opus 5 (Claude Code) |
| Work package | B3, B4, B5, B6, B7 of Workstream B (plan file `quiet-gliding-nautilus`) |
| PR / commit | not committed |
| Units touched | modules.iam, integration.drivers, interfaces.http, config/policy, customer-web, sdk, e2e |

## B7: the Rego could not enforce what it was written to enforce

`config/opa/authz.rego` has always had a branch reading `input.granted`, and
`OpaAuthorizationPolicy` never sent the field. Measured against the real Rego
with OPA running: a supervisor holding `audit:read` by grant was allowed
`action:approve`. With the field sent, denied.

Nothing was reachable through it, because `GrantAwareAuthorizationPolicy`
applies the same rule in Python before the request reaches OPA. What was wrong
is subtler and worth naming: the two drivers were only in parity because one of
them was wrapped, so removing the wrapper would have left the Rego quietly not
enforcing separation of duties. A policy that cannot enforce its own rule is
documentation.

Also removed two silent fallbacks in the request path. A missing token verifier
made an authenticated caller **anonymous**, which is the wrong way round: the
caller presented a credential, so the honest answer is that the request cannot
be authenticated. A missing authorization policy improvised a fresh
`PythonAuthorizationPolicy()` per request, so a deployment that configures OPA
would have had every decision revert to the local driver, giving the same
answers from a different authority than the one operations believes is
deciding, with nothing in the logs. Both now answer 503, because the caller has
done nothing wrong and reporting a wiring fault as a refusal sends somebody to
look at credentials that are fine.

## B3: a session that never ended

`REFRESH_TOKEN_TTL` bounded nothing on its own. It was recomputed on **every**
issue, including every refresh, so the window slid forward each time: a session
refreshed once a month never expired, and a stolen refresh token was a
permanent credential.

`ABSOLUTE_SESSION_TTL` is counted from the authentication that started the
session and never extended. The idle window still slides, which is what makes
an unused session expire; this is what makes an actively used one end. A
refresh token is capped so it cannot outlive the session that issued it.

One correction to an earlier claim of mine: staff refresh already downgraded
`MFA_RECENT` to `MFA`, so step-up assurance never survived a refresh. The gap
was the session lifetime, not the assurance.

Added `GET /v1/auth/sessions` and `DELETE /v1/auth/sessions`. The subject comes
from the verified token, so there is nothing to enumerate, and the list carries
nothing that could resume a session: a list read over somebody's shoulder
should not also be a way in. `keep_current` defaults to true, because somebody
who has just found a session they do not recognise should not also sign
themselves out of the device they are holding.

## B4: the session was readable by any script on the page

The customer token lived in `sessionStorage`. It is the credential that opens a
dispute and confirms a refund. It is now an `HttpOnly` cookie set by
`POST /v1/auth/otp/verify`, as the staff session already was. The response body
still carries the token, because the WhatsApp gateway and the MCP server are
not browsers and have nowhere to put a cookie.

CSRF is a double-submit token. `SameSite=Lax` and pinned CORS already cover the
ordinary case; this covers what they do not, which is that a sibling subdomain
is same-site as far as Lax is concerned and a browser that does not apply the
Lax default sends the cookie anyway.

The exemptions are the interesting part. A bearer caller is exempt because
another origin cannot make a browser send a header it does not know. Sign-in
routes are exempt because they *set* the cookie, so the caller has no token to
echo. And the read-only POSTs are exempt by reading
`trail.NOT_RECORDED_AS_REQUESTS` for entries whose reason begins "read only",
rather than keeping a second list that can disagree with the first: an attacker
who wants a receipt verified can verify it themselves.

## B5: rotating the issuer key was an outage

One key, one fixed `kid` of `clarity-iam-dev`, no rotation. Changing it would
have invalidated every token in circulation at once, which is why nobody would.

There is now a ring: the active key plus any retired within
`KEY_OVERLAP_WINDOW`. Key ids are derived from the key itself, so a token says
which key signed it and two processes loading the same key agree on its name
without being told. `/.well-known/clarity-keys.json` publishes the whole ring,
because publishing only the active key breaks every external validator on
rotation, which is the same outage by another route.

`tests/architecture/test_module_state.py` caught the ring being held in one
process, and it was right: a rotation on one replica would be invisible to the
others, which keep signing with the key it retired and cannot verify its new
tokens. That reads as intermittent sign-outs rather than a configuration fault.
The ring is now written to and read from the shared key volume. Private keys
deliberately do **not** go in a repository: a key belongs on a mounted volume
or in a secret store, not in an application table.

## B6: `prod` generated codes into an inbox nobody could read

`OtpDelivery` had exactly one implementation. There is now an HTTP SMS driver
behind the same port, and both pass `tests/contract/test_otp_delivery_parity.py`,
which asserts the properties the sign-in path relies on: the code never reaches
a log, an exception or a return value, and a delivery failure says nothing about
whether the number exists. That last one matters because `otp/request` was made
to answer identically for a subscriber and a stranger, and a driver reporting
"unknown destination" would reinstate the oracle one layer down.

The gateway interface is **REQUIRES HUTCH CONFIRMATION**: no SMSC contract has
been shared, so the driver speaks the shape every HTTP gateway shares, behind
settings.

Sign-in routes are now rate limited by the application as well as by nginx. The
OTP service bounds challenges per *number*, which is the SMS-pumping control;
this bounds them per *caller*, which is what stops one script working through a
list of numbers, and it exists in `lite` where no reverse proxy does.

## Decisions made

- **CSRF exemptions are derived, not listed.** Reading the trail's own
  declarations means a new read-only POST documented that way is exempt
  automatically, and the two lists cannot drift apart.
- **503 rather than 401 for a wiring fault.** Both 401 and 403 say something
  about the caller.
- **Keys stay out of the repository.** The shared volume already exists and is
  how the current key is shared; a database table is a different risk posture
  for a private key.
- **No OpenBao for the issuer, deliberately.** Receipts sign through OpenBao
  and that is right for them: low volume, high value. A token is minted on
  every sign-in and every refresh, so remote signing puts a network call on the
  authentication path. The rotation seam is now in place, which is what a move
  to a managed signer would need; the move itself is a separate decision.

## Docs updated

- [x] CHANGELOG.md: all five, with the reason each mattered.
- [x] `.env.example`: `CLARITY_SMS_URL`, `CLARITY_SMS_TOKEN`, `CLARITY_SMS_SENDER`.
- [x] `config/policy/throttle.yaml`: `throttle.auth.per_minute`.
- [x] OpenAPI snapshot, `contracts/openapi.json` and the SDK schema regenerated.
- [ ] `iam/MODULE.md`: **not yet updated for B3 to B6.** It still describes the
      single key and says nothing about the session cap, the ring or the SMS
      driver. That is a sync-matrix row owed before merge.
- [ ] ADR: the absolute session cap and the key ring are both decisions that
      warrant one. Not written.

## Tests

- `tests/contract/test_authz_parity.py`: 3 added, run against the real Rego
  with OPA in Docker. `1087 passed`.
- `tests/unit/test_api.py`: 3 for the removed fallbacks.
- `tests/unit/test_iam.py`: 8 for the session cap and inventory, 9 for key
  rotation and the overlap window.
- `tests/acceptance/test_staff_sso_routes.py`: 6 for the session routes.
- `tests/acceptance/test_csrf.py`: 10, new file.
- `tests/contract/test_otp_delivery_parity.py`: 13, new file, both drivers.

Run:
- `pytest`: `2543 passed, 640 skipped`.
- `pytest tests/contract/test_authz_parity.py` with `CLARITY_OPA_URL`: `1087 passed`.
- `ruff`, `mypy` (243 files), `lint-imports` (3 contracts kept): clean.
- `tsc` on the SDK and customer-web, `npm run build`, `npm run test`: clean.

## Open issues / next step

1. **`iam/MODULE.md` and two ADRs are owed**, as above.
2. **The browser has not run any of this.** The e2e helper now sets cookies
   instead of `sessionStorage`, which is simpler, and the Playwright suite has
   still never been executed. The customer app's move to cookies is the change
   most likely to need adjustment there.
3. **The SMS driver has never spoken to a gateway.** It is covered by a mock
   transport and a parity suite; the field names are a guess at a shape.
4. **CSRF is enforced for cookie callers only.** That is correct, and it means
   the protection arrives with the cookie: an older client still sending a
   bearer token is unaffected, which is the intended migration path.
5. **The console still signs in with the password form** (B1's browser half),
   unchanged from the previous devlog.

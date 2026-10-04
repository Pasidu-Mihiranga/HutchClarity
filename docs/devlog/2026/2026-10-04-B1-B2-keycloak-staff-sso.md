# 2026-10-04 - B1, B2 - staff single sign-on and step-up through Keycloak

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga; agent: Claude Opus 5 (Claude Code) |
| Work package | B1 and B2 of Workstream B (plan file `quiet-gliding-nautilus`) |
| PR / commit | not committed |
| Units touched | modules.iam, interfaces.http, app, config/keycloak, tests |

## What changed

**The realm was a machine-client registry with no humans in it.** Two bearer/service clients, one service account, no browser client, no `otpPolicy`, no step-up flow. `config/keycloak/clarity-realm.json` now also carries:

- `clarity-console`, a **confidential** client with the standard flow and `pkce.code.challenge.method: S256`.
- Nine synthetic staff accounts, one per realm role, so every path through `permissions_for` has a person who can exercise it. Five carry a TOTP credential: exactly the roles that can move money or change a control, which is the line `STEP_UP_PERMISSIONS` already draws.
- `acr.loa.map`, a TOTP policy, and a `clarity-browser-stepup` flow whose OTP subflow is gated by `conditional-level-of-authentication`.

**`modules/iam/oidc.py`**: the authorization code flow. Builds the authorization request with PKCE, a nonce and `acr_values`; claims a pending login exactly once; exchanges the code; builds the RP-initiated logout URL.

**`interfaces/http/staff_sso.py`**: four routes and a cookie. Start, callback, step-up, logout.

**`principal_from` accepts the cookie**, header first. Without that the cookie would have been inert.

**CORS pinned** to configured origins with credentials allowed.

## Why the API is the OIDC client and not the console

The console could run the flow itself as a public client with PKCE, which is a supported pattern. It would also put an access token carrying staff roles into JavaScript, on the surface that approves refunds. So the API is the confidential client, performs the exchange, and hands the browser a session cookie that is not a bearer token for anything else.

The cookie holds the same Clarity staff token `TokenIssuer` has always minted. One issuer for staff sessions whatever proved the identity, so revocation, the audit trail and `STEP_UP_WINDOW` keep working unchanged.

## Decisions made

- **Staff SSO is off unless issuer, client secret and callback are all set.** A confidential client with no secret is a public client nobody decided to make public, and a half-configured SSO that silently falls back to the development sign-in is the failure nobody notices. The routes answer 404, not 503.
- **A step-up sends `prompt=login` and `max_age=0`.** Without them the provider answers from its own session cookie, the token comes back claiming MFA, and the approval rests on the password typed an hour ago. `acr.loa.map` on the realm is the other half: without the map Keycloak ignores `acr_values` entirely.
- **A principal with no known role is refused**, not admitted with none. A session with no role fails confusingly on every screen.
- **Pending logins go in the repository, not a dictionary.** They look like throwaway protocol state. The browser decides which replica receives the callback, so in-memory means sign-in fails intermittently behind a load balancer, in a way that looks like the provider misbehaving. `tests/architecture/test_module_state.py` caught this, which is what that test is for.
- **`return_to` is restricted to a path on the console's own origin.** An open redirect on a sign-in route is how a phishing page borrows a real login screen, and it is the one part of the flow a caller chooses.

## A defect found in the test suite itself

The SSO routes were written as an `APIRouter` first. They worked, and `tests/acceptance/test_route_contract.py` did not see them at all.

FastAPI 0.142 wraps an included router in an opaque `_IncludedRouter` object carrying no `path` and no `methods`. The route-classification test walks `app.routes`, so **every route added through a router is invisible to it**, and that test is what enforces I9, that every route declares who may call it. A contributor adding a router would have bypassed the I9 guard silently, with nothing failing.

Fixed both ways: these routes register directly on `app`, and a new test refuses an `_IncludedRouter` outright with the reason written down. If a router ever becomes worth having, that test is the thing to change.

## Docs updated

- [x] MODULE.md of: `iam` (files, purpose, data owned, five new invariants, tests, history).
- [x] CHANGELOG.md: the new routes, the CORS change, the cookie, the `deps` move.
- [x] `.env.example`: `CLARITY_OIDC_*`, `CLARITY_CONSOLE_BASE_URL`, `CLARITY_ALLOWED_ORIGINS`, `CLARITY_COOKIE_SECURE`.
- [x] OpenAPI snapshot regenerated on purpose.
- [ ] ARCHITECTURE.md: not updated. No module changed status; M-IAM was already recorded complete and this is the browser half of it.
- [ ] Walkthrough: WT-10 covers the external MCP client and is unaffected. A staff sign-in walkthrough should exist and does not; it needs a running Keycloak to verify, so it is not written blind.

## Tests

Added:
- `backend/tests/unit/test_staff_sso.py` (15): the authorization request, PKCE, single-use state, expiry, step-up parameters, the nonce check, logout URLs.
- `backend/tests/acceptance/test_staff_sso_routes.py` (12): off until configured, the redirect, open-redirect refusal, forged state, step-up needs a session, logout clears both cookies and is idempotent, and the cookie actually authenticates.
- `backend/tests/acceptance/test_route_contract.py`: the included-router guard above.
- `backend/tests/unit/test_keycloak_realm.py` (14): the realm config itself, so the three defects above cannot come back. These run everywhere, which the integration lane cannot: two of its checks need the password grant, and the realm deliberately leaves it off.
- `backend/tests/integration/test_keycloak.py` (5 more): the same claims against the real provider.

Run:
- `pytest`: `2489 passed, 638 skipped`. No failures.
- `pytest tests/integration` against a live Keycloak (`CLARITY_KEYCLOAK_URL`): `24 passed, 26 skipped`, the skips being the lanes that need PostgreSQL, OPA and OpenBao.
- `ruff check` and `format --check`: clean. `mypy`: 241 source files. `lint-imports`: 3 contracts kept.

## Verified against a real Keycloak, and what that found

Run against Keycloak 26.4.7 with the realm imported. The realm and the step-up
flow imported cleanly on the first attempt, including both conditional
level-of-assurance subflows with their configs attached, which was the part
expected to need adjustment. **Three defects turned up that no mock could
show**, and all three fail silently: the realm imports, the provider issues
tokens, and nothing complains until somebody tries to sign in.

**1. The realm minted no `sub`.** A realm import treats `clientScopes` as the
whole set rather than an addition, so declaring the three Clarity MCP scopes
removed Keycloak's built-in ones. `basic` is what emits `sub` and `auth_time`,
and `KeycloakTokenVerifier` requires `sub`. **Every staff sign-in would have
been rejected by our own verifier.** This is the same shape as the audience
defect this lane found before, and for the same reason.

**2. The realm minted no `acr`.** Same cause, different scope. Without it a
stepped-up session is indistinguishable from a password one, so the step-up
would have asked for a one-time code and granted nothing for it.

**3. `MFA_RECENT` was unreachable from any real provider.** The verifier
required `acr == "mfa-recent"`, which no Keycloak sends: with a level map
configured the provider returns the level's own name, and this realm calls its
second factor `mfa`. Since `MFA_RECENT` is what an above-cap approval requires,
a correctly completed step-up would still not have granted the assurance it
exists to grant. Recency now comes from `auth_time` against `STEP_UP_WINDOW`,
which is what that claim is for: the ACR says what was proven, `auth_time` says
when.

Also confirmed working: 9 staff accounts with their roles, OTP credentials on
the five roles that can move money, `acr.loa.map`, the TOTP policy, and the
provider refusing a password-only sign-in for an account that carries OTP.

## Open issues / next step

1. **The browser round trip is still unproven.** A headless probe could not
   replay Keycloak's session cookie, so the code exchange and the OTP prompt
   were not driven end to end. What was proven is everything either side of it:
   the authorization request, the realm's behaviour, the claims in a real
   token, and the exchange code path. The remaining gap closes when the console
   is wired and the browser suite runs.
2. **The console still signs in with the password form.** The backend is ready; the browser half is not wired. Until it is, staff SSO is reachable only by visiting `/v1/auth/staff/oidc/start` directly.
3. **B3 is half done.** Logout and revocation landed here. The assurance cap on refresh and the session inventory have not.
4. **B4 is half done.** The staff cookie and the CORS pin landed here. The customer app still keeps a bearer token in `sessionStorage`, and there is no CSRF token beyond `SameSite=Lax`.
5. **B5, B6, B7 untouched**: key rotation and OpenBao for the issuer, an SMS driver for `prod` OTP, and the OPA `granted` field with the real-Rego CI lane.
6. The realm's development passwords and the TOTP seed are published in the repo, deliberately and labelled. A deployment imports its own realm. That is the same note the staff directory already carries, and it matters more now that these accounts can sign in through a browser.

# iam - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.iam`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `authorization.py`, `directory.py`, `keycloak.py`, `oidc.py`, `otp.py`, `public.py`, `tokens.py` |

## 1. Purpose
Customer identity: shared OTP state and short-lived EdDSA sessions whose subject is the `subscriber_ref`; Keycloak-compatible staff/MCP verification and OPA authorization; and staff sign-in through the provider (B1), where the API is the confidential client and the browser holds a cookie rather than a token.

## 2. Public surface (`public.py`)
`StaffDirectory` loads simulated staff accounts. `authenticate` returns that account's role. A configured directory is what closes `POST /v1/auth/staff/session`.
Other code imports only `public.py`, including token verifier and authorization policy ports plus lite and full drivers, and the audit grant service: `AuditGrants`, `AuditGrant`, `GrantState`, `SubjectKind`, `GrantRefused`, `GrantNotFound`, `GrantAwareAuthorizationPolicy`, `is_subject`, `GRANTS` (audit assurance Phase 3, ADR-0036).
Other code imports only `public.py`, including token verifier and authorization policy ports plus lite and full drivers. `TokenIssuer(key_path=...)` keeps the customer token key in a file, created once and shared safely by processes that start together; the composition root passes `KEYS_DIR/iam-issuer.pem` when `KEYS_DIR` is set, and without it the key stays in memory.

`TokenIssuer` also exposes `rotate()`, `public_keys()`, `sessions_for()`, `revoke_all()` and `session_id()`. The SMS driver lives in `clarity.integration.drivers.sms` rather than here, because it speaks to an external system and this module owns the port, not the gateway.

## 3. Used by
`clarity.app`, `clarity.interfaces.http`

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.kernel` | - |
| `clarity.platform.security` | - |
| `clarity.platform.audit` | every grant step is appended to the trail |
| `clarity.platform.persistence` | `iam.grants` |

## 5. Data owned
Collections `iam.otp_challenges`, `iam.otp_requests`, `iam.sessions`, `iam.refresh_tokens`, `iam.pending_logins` and `iam.grants`. The issuer's signing keys are **not** a collection: they live on the shared key volume (`KEYS_DIR`), because a private key belongs on a mounted volume or in a secret store, not in an application table. A pending login looks like throwaway protocol state and is not: the browser decides which replica receives the callback, so holding it in a dictionary makes sign-in fail intermittently behind a load balancer. Grants are stored beside the audit trail's store so a demo reset carries them with it. Lite uses the shared memory store; full uses the IAM PostgreSQL schema.

## 6. Invariants
- The OTP code travels only through the delivery port; it is never returned by a request.
- A token never contains the raw MSISDN.
- A grant carries only an audit permission (`GRANTABLE_PERMISSIONS`): never money, never `audit:assign`.
- A grant is requested by one holder of `audit:assign` and approved by a different one; nobody grants themselves, by name or through a role they hold. Break-glass is the one exception, admin-only, short, and recorded as `grant.break_glass`.
- A grant that expires or lapses is recorded once, as `grant.expired` or `grant.lapsed`, with the moment it ended.
- Whatever authorization driver is configured is wrapped, so grants and the rule that an audit duty removes money permissions hold under OPA too.
- **`OidcLogin` decides nothing about a person.** It turns an authorization code into verified claims; roles come from the provider's token and are mapped by `KeycloakTokenVerifier` onto the closed `Role` enum, where an unknown role grants nothing. A principal carrying no known role is refused rather than admitted with none.
- **The browser never holds a provider token.** The API is the confidential client and the console carries an `HttpOnly` cookie holding the same Clarity staff token `TokenIssuer` has always minted, so revocation, the trail and `STEP_UP_WINDOW` work unchanged.
- **A sign-in state is single use.** It is deleted when claimed, so a replayed callback finds nothing, and the id token's nonce is checked before anything is trusted.
- **A step-up re-authenticates.** `prompt=login` and `max_age=0` with `acr_values`, against a realm that carries `acr.loa.map`: without the map the provider ignores the level, answers from its own cookie, and the token claims MFA for a password typed an hour ago.
- **A session has an absolute deadline** (`ABSOLUTE_SESSION_TTL`), counted from the authentication that started it and never extended. `REFRESH_TOKEN_TTL` bounds an *idle* session; on its own it bounded nothing, because it was recomputed on every refresh, so a session refreshed inside the window never expired. A refresh token is capped so it cannot outlive the session that issued it (ADR-0041).
- **A person can see and end their own sessions.** The subject comes from the verified token, so there is nothing to enumerate, and the list carries nothing that could resume a session.
- **The signing key is a ring, not a key** (ADR-0042). The active key plus any retired within `KEY_OVERLAP_WINDOW`, which is what makes rotation something other than an outage. Key ids are derived from the key itself, so a token says which key signed it and two processes agree on its name without being told. The ring is read from and written to the shared key volume, so a rotation performed by one replica is honoured by the others.
- **Every key a validator needs is published.** `/.well-known/clarity-keys.json` serves the whole ring; publishing only the active key breaks every external validator on rotation.
- **A one-time code travels only through the delivery port, whichever driver is configured.** `SimulatedInbox` for the synthetic profiles, `SmsOtpDelivery` where codes must reach a handset. Both pass `tests/contract/test_otp_delivery_parity.py`: the code never reaches a log, an exception or a return value, and a delivery failure says nothing about whether the number exists, or the enumeration oracle returns one layer down.
- **The realm must declare the `basic` and `acr` scopes explicitly.** A realm import replaces Keycloak's built-in client scopes rather than adding to them, so declaring the Clarity MCP scopes removed them. `basic` emits `sub`, which `KeycloakTokenVerifier` requires, and `acr` carries the level of assurance. Both failures are silent: the realm imports and tokens issue. `tests/unit/test_keycloak_realm.py` pins it.
- **Recency comes from `auth_time`, never from the name of a level.** The ACR says what was proven; `auth_time` says when. Requiring `acr == "mfa-recent"` made `MFA_RECENT` unreachable from any real provider, so a completed step-up granted nothing.
- **Staff SSO is off unless fully configured.** Issuer, client secret and callback, all three. A confidential client with no secret is a public client nobody decided to make public, and a half-configured SSO silently falling back to the development sign-in is the failure nobody notices.

## 7. Migration status (enterprise-plan 21)
M-IAM complete: lite keeps the labelled dev issuer and full can validate Keycloak JWKS and delegate permissions to OPA. Refresh tokens rotate, access sessions revoke immediately, and OTP/rate-limit state is shared between replicas. Staff dev sign-in remains synthetic-profile only (D3).

## 8. Tests
- `tests/unit/test_iam.py`
- `tests/unit/test_staff_sso.py` (the authorization request, the refusals, the nonce check)
- `tests/acceptance/test_staff_sso_routes.py` (the routes, the cookie, logout)
- `tests/contract/test_authz_parity.py` (real OPA in the `full` lane)
- `tests/security/test_audit_grants.py`
- `tests/unit/test_keycloak_realm.py` (the shipped realm's own configuration)
- `tests/contract/test_otp_delivery_parity.py` (both delivery drivers)
- `tests/acceptance/test_csrf.py` (cookie-borne requests)
- `tests/integration/test_keycloak.py` (real Keycloak, `CLARITY_KEYCLOAK_URL`)

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.iam` with a public surface (R1) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-M-IAM-keycloak-opa-shared-state.md` | Keycloak, OPA, shared OTP and revocable sessions (M-IAM, #7) |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-AUDIT-P3-grants-and-audited-reads.md` | Audit duties by grant under separation of duties (Phase 3, ADR-0036) |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-AUDIT-P3-grant-endings-recorded.md` | Grant expiry and lapse recorded once, at the moment they happen |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-M-IAM-opa-parity-made-real.md` | Authorization parity evaluates the real Rego, not a Python stand-in |
| 2026-10-03 | `docs/devlog/2026/2026-10-03-M-IAM-keycloak-verified-real.md` | Verified against real Keycloak; fixed the multi-key JWKS defect |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-FE-session-survives-deploy.md` | Optional persisted issuer key, so a redeploy no longer signs every customer out |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-staff-login-vertex.md` | Directory sign-in: the server assigns the role |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-B3-B7-session-keys-sms-csrf-authz.md` | Absolute session deadline and a session inventory (B3, ADR-0041); the signing key ring (B5, ADR-0042); an SMS delivery driver (B6); CSRF for cookie sessions (B4); the OPA driver sends `granted` (B7) |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-B1-B2-keycloak-staff-sso.md` | Staff SSO through the provider: `oidc.py`, the cookie session, step-up by level of assurance (B1, B2) |

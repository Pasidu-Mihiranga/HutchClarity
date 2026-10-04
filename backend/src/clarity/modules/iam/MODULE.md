# iam - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.iam`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `authorization.py`, `keycloak.py`, `otp.py`, `public.py`, `tokens.py` |

## 1. Purpose
Customer identity: shared OTP state and short-lived EdDSA sessions whose subject is the `subscriber_ref`; Keycloak-compatible staff/MCP verification and OPA authorization.

## 2. Public surface (`public.py`)
Other code imports only `public.py`, including token verifier and authorization policy ports plus lite and full drivers. `TokenIssuer(key_path=...)` keeps the customer token key in a file, created once and shared safely by processes that start together; the composition root passes `KEYS_DIR/iam-issuer.pem` when `KEYS_DIR` is set, and without it the key stays in memory.

## 3. Used by
`clarity.app`, `clarity.interfaces.http`

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.kernel` | - |
| `clarity.platform.security` | - |

## 5. Data owned
Collections `iam.otp_challenges`, `iam.otp_requests`, `iam.sessions`, and `iam.refresh_tokens`. Lite uses the shared memory store; full uses the IAM PostgreSQL schema.

## 6. Invariants
- The OTP code travels only through the delivery port; it is never returned by a request.
- A token never contains the raw MSISDN.

## 7. Migration status (enterprise-plan 21)
M-IAM complete: lite keeps the labelled dev issuer and full can validate Keycloak JWKS and delegate permissions to OPA. Refresh tokens rotate, access sessions revoke immediately, and OTP/rate-limit state is shared between replicas. Staff dev sign-in remains synthetic-profile only (D3).

## 8. Tests
- `tests/unit/test_iam.py`
- `tests/contract/test_authz_parity.py` (real OPA in the `full` lane)
- `tests/integration/test_keycloak.py` (real Keycloak, `CLARITY_KEYCLOAK_URL`)

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.iam` with a public surface (R1) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-M-IAM-keycloak-opa-shared-state.md` | Keycloak, OPA, shared OTP and revocable sessions (M-IAM, #7) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-M-IAM-opa-parity-made-real.md` | Authorization parity evaluates the real Rego, not a Python stand-in |
| 2026-10-03 | `docs/devlog/2026/2026-10-03-M-IAM-keycloak-verified-real.md` | Verified against real Keycloak; fixed the multi-key JWKS defect |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-FE-session-survives-deploy.md` | Optional persisted issuer key, so a redeploy no longer signs every customer out |

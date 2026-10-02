# iam - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.iam`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `otp.py`, `public.py`, `tokens.py` |

## 1. Purpose
Customer identity: OTP over a delivery port and short-lived EdDSA tokens whose subject is the `subscriber_ref` pseudonym; development staff issuer.

## 2. Public surface (`public.py`)
Other code imports only these names: `OtpRefused`, `OtpService`, `SimulatedInbox`, `TokenInvalid`, `TokenIssuer`.

## 3. Used by
`clarity.app`, `clarity.interfaces.http`

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.kernel` | - |
| `clarity.platform.security` | - |

## 5. Data owned
In-memory structures in the `lite` profile. Target: one PostgreSQL schema `iam` with its own role (ADR-0013), same repository interfaces, same parity suite.

## 6. Invariants
- The OTP code travels only through the delivery port; it is never returned by a request.
- A token never contains the raw MSISDN.

## 7. Migration status (enterprise-plan 21)
Own issuer (ADR-0010). R2: Keycloak for staff, admins and MCP clients; the customer issuer stays behind the same interface. Staff dev sign-in must be demo-only (D3).

## 8. Tests
- `tests/unit/test_iam.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.iam` with a public surface (R1) |

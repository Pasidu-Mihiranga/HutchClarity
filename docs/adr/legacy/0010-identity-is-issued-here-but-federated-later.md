# 0010 - Clarity issues its own tokens now, behind the interface Keycloak will fill

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Plan references | plan §19 (identity, RBAC/ABAC), §10.3 (subject binding), §17.1 (AuthN), §22.1; `docs/improvement-plan.md` Phase 3 |

## Context
Until this change every endpoint was open. Holding a case id was enough to read
someone's charges, and `POST /v1/cases/{id}/proposals` would build an action
plan for any caller at all. The prototype demonstrated the *money* boundary -
rules decide, the LLM explains - while leaving the *identity* boundary absent,
which made the authorization claims in plan §19 untestable.

Production identity belongs to HUTCH: staff come from HUTCH SSO (Keycloak
federating AD/Entra, DEP-08) and customers from the HUTCH OTP service and app
token exchange (DEP-09). Neither exists here, and inventing a HUTCH IdP would
breach the project's standing rule against pretending HUTCH systems exist.

Waiting for them was the other option, and it was worse: the controls that
matter - subject binding, step-up before money, admins excluded from approvals -
are design decisions, not integration details. Deferring them would have meant
retrofitting authorization through every route and test later.

## Decision
Clarity issues its own short-lived EdDSA tokens, and every route states the
permission it needs.

1. **The permission model is the deliverable, the issuer is not.** `Role`,
   `Permission` and `ROLE_PERMISSIONS` in `core/iam/principal.py` are the
   matrix from plan §19, including the two rules that outrank the rest: admins
   never hold money permissions (applied *after* the union of roles, so it
   cannot be escaped by stacking), and a maker is never the checker.
2. **Deny by default.** `requires(permission)` is a dependency, so a route
   cannot be mounted without declaring what it needs. `public()` is explicit,
   not an omission, so "open here" is visible in the route table.
3. **Subject binding.** A customer token names one `subscriber_ref` and that is
   the only subject they reach. A case id authorises nothing.
4. **The token is the source of truth for identity facts.** Who approves and
   whether they recently re-authenticated come from the session, never the
   request body. An approval audit that takes the caller's word for step-up
   records nothing worth keeping (plan §20.4), and a caller that could name its
   own approver would satisfy four-eyes alone.
5. **The subject is a pseudonym.** Customer tokens carry `subscriber_ref`, not
   the MSISDN: tokens reach logs and proxies, and a phone number there is a
   leak.
6. **Step-up ages.** `MFA_RECENT` decays to `MFA` once `auth_time` is older
   than the window, judged at request time. A claim that never expires is not
   re-authentication.

Keycloak and OPA arrive as **drivers behind these same interfaces**: Keycloak
replaces `TokenIssuer` (the public key is already published at
`/.well-known/jwks.json` so a separate validator works today), and OPA replaces
the `permissions_for` / `authorize_action` decision points. Both get parity
suites like every other port (ADR-0006), so the switch is a driver change, not
a redesign.

## Consequences
- The security claims in plan §19 are now executable: `tests/unit/test_iam.py`
  covers anonymous refusal on every protected route, cross-customer reads,
  step-up before an above-cap approval, admins excluded from money, OTP rate
  limiting and single use, and forged, unsigned, tampered and expired tokens.
- The Desk shows a **role picker**, and the customer flow shows a **simulated
  SMS inbox**. Both are labelled as simulated in the interface, because the
  identity provider is the mocked part - the permission checks they feed are
  the real ones.
- Four-eyes now requires two genuinely different signed-in people, since the
  approver is the token's subject. The Desk therefore asks who you are signing
  in as, which is the honest shape of the control.
- A reload signs the user out: the token is held in memory, never in
  `localStorage`, because it is a bearer credential.
- **Known gap.** The in-memory `TokenIssuer` generates its key at startup, so
  restarting invalidates every session, and there is no refresh, revocation
  list or session store. Production needs all three, plus the KMS/HSM-backed
  signer that receipts already specify (plan §15.2, T10).

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Keep the demo open, document the gap | The authorization design is the hard part and was untested. Two real defects (an unauthenticated `proposals` route, and client-asserted approver identity) were only found by writing the tests. |
| Run Keycloak locally in the demo profile | Breaks ADR-0006: a reviewer would need Docker and a configured realm to see a receipt. |
| Invent a mock "HUTCH IdP" adapter | Would imply a HUTCH interface we have not been shown. The simulated issuer is labelled as ours. |
| Put permission checks in the services | Routes are where a caller arrives; a missed decorator is visible in a route listing, whereas a missed service-level check is not. The money-path checks stay in the tool layer regardless. |
| Accept `mfa_step_up` from the request | It is the caller asserting its own assurance. Kept only as the tool layer's internal argument, supplied from the token. |

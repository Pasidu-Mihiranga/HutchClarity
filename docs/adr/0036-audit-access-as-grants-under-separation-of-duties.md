# 0036 - Audit access as time-boxed grants under separation of duties

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-04 |
| Deciders | Thanoj Buddhima |
| Plan references | `docs/audit-assurance-plan.md` (Phase 3, section 5.6), ADR-0010, I9 |

## Context

The maintainer asked that an admin can assign people, or roles, to watch the
audit trail through Clarity's own authorization layer. Roles alone are too
coarse: every auditor sees everything for ever, and a supervisor who should
watch refunds for a month has no way to get that duty and only that duty.

A watcher who can also approve the money they are watching defeats the point,
and an admin who can hand themselves any duty defeats the controls.

## Decision

1. **New permissions** `audit:export`, `audit:assign`, `alert:dispose`.
   `security_admin` holds `audit:assign` (step-up required); `compliance`
   holds `audit:export` and `alert:dispose`.
2. **Grants.** An audit permission given to a named staff user or to a role,
   for a bounded time: `requested` by one holder of `audit:assign`, `approved`
   by a different one, then `active` until it expires, is revoked, or lapses
   because nobody recertified it within the review interval. Limits are policy
   (`audit.grant.max_duration` P90D, `audit.grant.review_interval` P30D).
3. **Resolution.** Active grants are attached to the `Principal` when its token
   is verified, as `granted`, and `permissions_for(roles, granted)` applies
   separation of duties **after** the union, as it already did for admins.
4. **The five rules** (plan 5.6):
   1. holding any audit duty removes money permissions, by role or grant;
   2. nobody disposes of an alert in which they are the subject (`is_subject`,
      used by Phase 4);
   3. a grant needs two people;
   4. nobody grants themselves, by name or through a role they hold;
   5. reads of the trail are recorded (`audit.read`).
5. **Only audit permissions are grantable.** Money never; `audit:assign`
   never, so the authority to grant comes from a role only.
6. **Break-glass.** An admin may take a self-granted audit duty for an
   incident, for `audit.grant.break_glass_duration` (PT4H). It is the one
   exception to rules 3 and 4 and is recorded as `grant.break_glass`.
7. **Any authorization driver is wrapped.** OPA sees roles, not grants, so
   `GrantAwareAuthorizationPolicy` allows a granted duty and refuses money to
   anyone holding one. The rego policy and `data.json` mirror rule 1 for
   roles, and the parity test covers every role and permission.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| More roles | A role is for everyone in it and for ever. A duty for one person for one month is a grant. |
| Grants in the token | A revocation would wait for the token to expire. Resolving at verification makes revocation immediate. |
| Grants evaluated only in OPA | The `lite` profile has no OPA; and the Python resolution is what every handler's `principal.has()` uses. |
| One person may grant | Rule 3. A single compromised admin account could then build its own audit access. |

## Consequences

- Seven new signed-in routes under `/v1/audit`; OpenAPI snapshot regenerated
  on purpose.
- `iam.grants` collection; grants live beside the trail and survive a reset.
- A recorded refusal for every broken rule: separation-of-duties refusals are
  403s, so the refusal handler records them as `access.denied` with the rule.
- An expired or lapsed grant is recorded as `grant.expired` or `grant.lapsed`.
  *Amended 2026-10-04:* this ADR first left it unrecorded for want of a
  scheduler. The trail now records each ending once, with `occurred_at` set
  to the moment the grant ended (from its stored times) and `recorded_at` to
  when it was noticed. Two triggers, no new infrastructure: a sweep in each
  API process on `audit.grant.sweep_interval` (PT1M), and a check on every
  authenticated request, so an ending is recorded before the grant could next
  matter. An ending is claimed in the store first, so two processes record it
  once.

## Compliance

`tests/security/test_audit_grants.py` tests each rule as its refusal, the
lifecycle including lapse and expiry, and the API end to end.
`tests/contract/test_authz_parity.py` keeps Python and OPA equivalent.

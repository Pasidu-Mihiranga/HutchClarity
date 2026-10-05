# 0045 - Role permission overrides on a static baseline, with SoD

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-05 |
| Deciders | Thanoj Buddhima |
| Plan references | AGENTS.md I9, ADR-0036, enterprise-plan/11 §19, 18 §5.4 |

## Context

Role→permission bindings lived only in checked-in catalogues
(`ROLE_PERMISSIONS` and `config/opa/data.json`). That is correct for a known
floor, but a platform admin cannot attach or detach a permission on a role
without a deploy. Audit grants (ADR-0036) cover only three audit duties for
named people, not the role matrix. Policy Studio governs business artefacts,
not IAM.

Operators asked for an AWS-IAM-shaped surface: view the matrix, attach and
detach closed permissions on closed roles, without inventing new permission
strings at runtime, and without letting an admin hold money authority.

## Decision

1. **Static baseline stays.** `ROLE_PERMISSIONS` and OPA `data.json` remain the
   checked-in floor every deploy starts from.
2. **Persisted overrides.** Per role, a set of *attached* and *detached*
   permissions in `iam.role_policies`. Effective permissions for a role are
   `(baseline ∪ attached) − detached`.
3. **Closed catalogues.** Only existing `Role` and `Permission` enum members.
   No custom policy JSON and no new permission names at runtime in v1.
4. **Hard SoD.**
   - Money permissions cannot be attached to `platform_admin` or
     `security_admin`.
   - `audit:assign` and `audit:restore` cannot be attached or detached through
     this surface (they remain role-baseline only, as with grants).
   - Existing `permissions_for` money strip for admins and audit-duty holders
     still runs after the effective union.
5. **New permission** `iam:role:manage`, held by `platform_admin`, step-up
   required, gates `/v1/admin/iam/*`.
6. **Authz drivers.** Python resolves effective permissions via the override
   store. OPA receives `role_attached` / `role_detached` on the input document
   and applies the same formula over `data.clarity.role_permissions`.
7. **Audit + idempotency.** Every attach/detach is recorded on the trail and
   keyed by `Idempotency-Key` (I8).

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Replace the whole matrix at runtime | Loses the deploy-time floor; a bad edit empties every role. |
| Full AWS IAM JSON policies | Open-ended strings break the closed Permission enum and deny-by-default tests. |
| Reuse audit grants for all permissions | Grants are time-boxed people duties under two-person control; the role matrix is a different job. |
| Edit only via Policy Studio | Studio is for product policy values, not who may call which API. |

## Consequences

- Console gets an IAM tab for `iam:role:manage`.
- MODULE.md, OpenAPI, OPA Rego and the authz parity suite must stay aligned.
- A demo reset clears overrides with the IAM store (same as grants).

## Compliance

- Unit tests refuse money attach to admin roles and refuse `audit:assign`.
- `tests/contract/test_authz_parity.py` still equates Python and OPA for every
  role/permission pair (with empty overrides).
- Architecture tests: only `modules.iam.public` is imported outside the module.

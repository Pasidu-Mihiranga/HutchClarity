# 2026-10-04 - Audit assurance Phase 3 - Audit duties by grant, and audited reads

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code |
| Work package | `docs/audit-assurance-plan.md` Phase 3, ADR-0036 |
| PR / commit | branch `claude/affectionate-hamilton-ww2hgz` |
| Units touched | platform.security, modules.iam (new `grants.py`), interfaces.http, app, config/opa, config/policy |

## What changed

- `Principal.granted` and `permissions_for(roles, granted)`: grants join the
  role union, then separation of duties is applied, including the new rule
  that any audit duty removes money permissions.
- `AuditGrants`: request, approve (a different person), revoke, recertify,
  break-glass; every step in the trail. Lapse on missed recertification.
- Grants attached to the principal at token verification, so every check
  after it, dependency or handler, agrees.
- `GrantAwareAuthorizationPolicy` wraps whichever driver is configured.
- Routes: `GET /v1/audit` (reads recorded), the grant lifecycle, break-glass.
- OPA `data.json` and rego mirror the new permissions and rule 1.

## Why

The maintainer's requirement: an admin assigns specific staff or roles to
watch the trail, through Clarity's own authorization layer, without new
infrastructure.

## Decisions made

- **Revocation is immediate** because grants are resolved at verification,
  not baked into the token.
- **Only audit permissions are grantable**, and not `audit:assign`: the
  authority to grant comes from a role, so grants cannot build on each other.
- **Separation-of-duties refusals are 403s**, so the existing refusal handler
  records each one as `access.denied` with the rule's code (`FOUR_EYES`,
  `SELF_GRANT`), with no extra recording code.
- **Granting needs step-up** (`audit:assign` is a step-up permission).
- **Kept `data.json` diff minimal.** A first pass re-serialised the whole file
  (112 changed lines); restored and edited in place (10 added, 1 changed).
- **Expiry is not recorded as an event yet**: it needs a scheduler. Noted in
  the plan and ADR.

## Docs updated

- [x] iam `MODULE.md`: public surface, dependencies, data, invariants, tests, history
- [x] ADR-0036 and index; CHANGELOG; plan revision 6
- [x] OpenAPI snapshot regenerated on purpose (seven routes added, nothing
      changed), `contracts/openapi.json` and SDK types regenerated
- [x] Route contract: seven routes classified signed-in

## Tests

- `make check`: lint and format clean, `mypy --strict` clean (219 files),
  contracts 3 kept 0 broken; **`1 failed, 2155 passed, 604 skipped`**. The
  failure is the container-proxy test, unchanged. Skips rose by 60: the
  real-OPA parity lane now covers four new permissions and skips without OPA.
- `tests/security/test_audit_grants.py`: 24 tests. Each rule as its refusal;
  pending, role, lapse, recertify, expiry, revoke and break-glass; the API end
  to end, including a supervisor refused an approval only because of the duty
  (asserted on the reason, not just the status).
- Parity: 520 role x permission x assurance cases pass against `data.json`.

## Open issues / next step

- Phase 4: `modules/assurance`, risk rules, alerts and their lifecycle (using
  `is_subject` for rule 2), liveness, the chain-break playbook.
- Grant expiry as an event; the deferred Phase 2 items; database-level
  append-only.

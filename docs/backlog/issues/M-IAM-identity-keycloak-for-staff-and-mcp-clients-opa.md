# [M-IAM] Identity: Keycloak for staff and MCP clients, OPA for authorization, shared OTP state

| Field | Value |
|---|---|
| Wave | W1 Core modules on the baseline |
| Area | `iam` |
| Priority | P1 |
| Depends on | [B05](B05-postgresql-repositories-schema-and-role-per-modu.md) |
| Plan | ADR-0010, ADR-0017, 18 §5 |
| Labels | `wave:w1`, `area:iam`, `priority:p1`, `type:feature` |

## Context
Own issuer; key and OTP state in memory; role picker in synthetic profiles.

## Scope
- Keycloak driver (`full`): staff SSO with step-up, MCP client registry; dev issuer stays for `lite`
- OPA driver evaluating the same permission catalogue; parity suite with the Python checks
- OTP challenges and rate limits in a shared store; refresh and revocation

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | every role and permission pair | checked by Python and OPA | same allow or deny | `backend/tests/contract/test_authz_parity.py` |
| 2 | a revoked staff token | used | 401 | `backend/tests/unit/test_iam.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

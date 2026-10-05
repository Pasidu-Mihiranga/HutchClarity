# 2026-10-05 - IAM - Role permission overrides (ADR-0045)

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | Platform admin IAM role policies (ADR-0045) |
| PR / commit | - |
| Units touched | iam, platform.security, interfaces.http, console, sdk |

## What changed
- New `RolePolicies` service: attach/detach closed permissions on closed roles;
  effective = `(baseline ∪ attached) − detached`.
- Permission `iam:role:manage`; HTTP `/v1/admin/iam/roles` (+ attach/detach).
- Python + OPA authz consume the override layer; SoD refusals for money on
  admin roles and locked permissions (`audit:assign`, `audit:restore`,
  `iam:role:manage`).
- Console `/iam` tab + SDK methods; OpenAPI snapshot regenerated.

## Why
Platform admin needed an AWS-IAM-shaped surface to view and change the
role→permission matrix without inventing permissions or granting themselves
money authority. See ADR-0045.

## Decisions made
- Overrides on top of the checked-in baseline (not a free-form replacement).
- Console hides illegal attach options; API still enforces SoD.

## Docs updated
- [x] MODULE.md of: iam
- [x] Walkthrough: WT-13-admin-iam.md, WT-13-staff-console step 4b, WALKTHROUGHS.md
- [x] CHANGELOG.md / contracts (OpenAPI)
- [x] ADR-0045 (already accepted) indexed in docs/adr/README.md

## Tests
- `pytest backend/tests/unit/test_role_policies.py` and authz parity (prior turn): passed
- Focused console nav + IAM slice and `make contracts` / OpenAPI check: passed
  (`test_role_policies`, `test_openapi_contract`, `test_iam`, ConsoleNav,
  `make contracts-check`, console + SDK `tsc`)

## Open issues / next step
- Browser walk of WT-13-admin-iam after a demo reset.
- Optional e2e for the IAM tab (not in v1 scope).

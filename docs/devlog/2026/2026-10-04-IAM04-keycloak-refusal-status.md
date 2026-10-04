# 2026-10-04 - IAM04 - Accept Keycloak refusal status variants

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | staff SSO integration repair |
| PR / commit | pending |
| Units touched | Keycloak integration test |

## What changed

- Accept HTTP 400 or 401 when Keycloak refuses a password-only direct grant
  for an account that requires a second factor.
- Continue requiring the OAuth `invalid_grant` error, which proves no token
  was issued.
- Skip the MFA-specific direct-grant assertion when the console client disables
  direct grants entirely and returns `unauthorized_client`, matching the other
  token-shape tests in the same suite.

## Why

The Keycloak version in the full-profile CI lane returns 400 for this valid
OAuth refusal. Pinning the transport status to 401 made the security test fail
even though the required refusal occurred.

## Decisions made

- Test the security outcome and OAuth error rather than one provider-version
  status choice.

## Docs updated

- [x] Integration repair recorded here
- [ ] MODULE.md: no IAM behavior changed
- [ ] ARCHITECTURE.md / modules.md: no architecture change
- [ ] CHANGELOG.md / contracts: no public contract change
- [ ] Plan via CHANGES.md: no plan change

## Tests

- Full-profile CI before repair: 47 passed, 2 skipped, 1 failed on the strict
  status assertion.
- Focused local Keycloak suite: 15 skipped because the external Keycloak test
  service is not running locally; lint passed.

## Open issues / next step

Rerun the full-profile lane against the same Keycloak image. A deployment with
direct grants enabled still exercises the MFA-specific refusal assertion.

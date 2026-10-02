# 2026-10-03 - M-IAM - Keycloak verification made real

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus) |
| Work package | M-IAM (docs/enterprise-plan/21), issue #7 |
| PR / commit | not committed |
| Units touched | iam, deploy/compose, config/keycloak, ci |

## What changed

- `modules/iam/keycloak.py`: `_signing_keys` now loads a JWKS key by key and
  skips the ones it cannot use, instead of building the whole map in one
  comprehension. Keys published for encryption (`use` other than `sig`, or an
  `alg` outside RS256/ES256/EdDSA) are skipped deliberately, not merely
  tolerated.
- `config/keycloak/clarity-realm.json`: made self-contained so a test needs no
  admin access. Added the audience mapper on `clarity-mcp` so its tokens carry
  `clarity-api` in `aud`, set the client secret, added the service-account user
  with `default-roles-clarity`, `agent` and `supervisor`, and set
  `sslRequired: none` (development only, labelled).
- `backend/tests/integration/test_keycloak.py`: new, 10 tests, against the real
  service via `CLARITY_KEYCLOAK_URL`.
- `Makefile`, `.github/workflows/ci.yml`: Keycloak joins the full lane. CI runs
  it as a `docker run` step rather than a service container, because a service
  container cannot mount the realm file.

## Why

Issue #7's Definition of Done says the driver validates real Keycloak tokens.
The existing tests used a mock JWKS and a hand-written token, so they proved
the driver agreed with the test's own fixtures. They could not fail for the
reason a real deployment would.

The same verification pattern was applied to M-GOV, M-DEC, M-RCPT and M-REC
earlier in this work package; this entry closes the last of the five.

## Decisions made

- **An encryption key is skipped, not tried.** A key published for encrypting
  must never be accepted as evidence of a signature, so the filter is on `use`
  and `alg` before the load is attempted, and the load failure is only a
  backstop.
- **The realm file carries the service account, not a CI bootstrap script.**
  Keycloak 26's bootstrap admin is temporary and the master realm refuses admin
  tokens over plain HTTP, so an admin-driven setup step is both fragile and
  an invitation to put a credential in CI. A declarative realm has neither
  problem.
- **The service account keeps `default-roles-clarity`.** It is the shape a real
  service account has, and `test_keycloaks_own_roles_are_not_granted` cannot
  prove that `offline_access` grants nothing if the token never carries it.

## Defects this found

1. **Every real token was rejected.** Keycloak publishes an RS256 signing key
   and an RSA-OAEP encryption key. `PyJWK.from_dict` has no algorithm for the
   second and raises, which aborted the single comprehension, so `_signing_keys`
   raised `TokenInvalid` for valid tokens as well. A mock JWKS that publishes
   one signing key cannot show this up.
2. **`clarity-mcp` tokens had the wrong audience.** The client had no audience
   mapper, so `aud` never contained `clarity-api` and the driver's audience
   check rejected the token. Correct behaviour by the driver, missing realm
   configuration.

## Non-vacuity

Each test was proven able to fail before being trusted:

- Restoring the one-comprehension `_signing_keys` passes the mock lane and
  fails the real lane on 3 tests, which is exactly the gap being closed.
- Removing the audience mapper fails the token-shape tests.
- `test_the_driver_is_actually_talking_to_keycloak` fails if the lane is
  misconfigured, so a skipped lane cannot be mistaken for a passing one.

## Correction to an earlier claim

Twice in this work package I told the developer there was "no Keycloak
anywhere" in the repository. That was wrong: `deploy/compose/full.yml` already
ran it with a realm import. Only two parts of what I said were accurate, and
they are the parts that mattered: Keycloak was absent from CI, and the driver
was tested only against a mock.

## Docs updated

- [x] MODULE.md of: iam
- [ ] ARCHITECTURE.md / modules.md (no new module or dependency)
- [ ] Walkthrough (no user-visible flow change)
- [ ] CHANGELOG.md / contracts (no public surface change)
- [ ] Plan via CHANGES.md (no plan change)
- [x] `.env.example` already lists `CLARITY_KEYCLOAK_URL`

## Tests

- `make check`: `1309 passed, 522 skipped, 1 warning in 16.89s`
- `make test-full` with Postgres, Kafka, OPA, OpenBao and Keycloak all running:
  `1100 passed, 1 warning in 76.04s`. Nothing skipped, so every real lane ran.
- `tests/integration/test_keycloak.py` alone: `10 passed`.

## Open issues / next step

M-IAM's driver verification is done. Remaining Wave 2 work: A04 (#8) the MCP
server over Streamable HTTP with OAuth 2.1, which builds on this auth stack,
then A05 (#9) the evaluation harness.

Known gaps noted while here, none of them regressions:

- `TokenBuckets` declares no quotas yet, so the customer reserve is untested
  against a real budget.
- `Guard.check` is not called by any request path.
- No cassettes are committed yet.

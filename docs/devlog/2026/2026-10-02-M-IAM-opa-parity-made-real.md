# 2026-10-02 - M-IAM - The authorization parity suite now evaluates the real Rego

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | M-IAM (issue #7), Wave 1 |
| Units touched | tests/contract/test_authz_parity.py, CI, Makefile |
| Context | M-IAM was implemented by another agent (Codex). This entry covers the verification and the gap it found. |

## What changed

`tests/contract/test_authz_parity.py` now runs in two lanes:

- **real OPA** (`CLARITY_OPA_URL`, the `full` lane): the Rego in `config/opa/authz.rego` is evaluated by OPA itself.
- **python stand-in** (the default): the rules reimplemented in Python over the same `data.json`, so the `demo` profile needs no infrastructure (ADR-0006).

Plus `test_the_real_rego_is_actually_reachable_when_this_lane_runs`, because a parity suite that skips is indistinguishable from one that passes.

OPA is now a service in the CI `full` lane and in `make test-full`.

## Why

M-IAM's acceptance test 1 reads: "every role and permission pair checked by Python and OPA, same allow or deny". The suite did not do that. `_opa()` was an `httpx.MockTransport` handler that reimplemented the authorization rules **in Python** and returned a canned response. It compared the Python driver against a second Python implementation of the same rules.

So `config/opa/authz.rego` was never evaluated by anything, in any lane. A mistake in the Rego would have passed CI, and the policy that decides who may suspend a merchant or move money would have been unverified while appearing covered by 461 green tests.

The data file was shared, so the test did have value: it checked that `data.json` and the Python driver agree. What it could not do is notice that the Rego says something else.

## Decisions made

- **Kept the stand-in rather than deleting it**, because `make check` must run with no infrastructure. It is renamed `_reimplemented_in_python` and the module docstring states plainly what each lane does and does not prove. A fake named `_opa` is how this gap survived in the first place.
- **The policy is uploaded to OPA in CI, not mounted.** A GitHub Actions service container starts before the checkout, so it cannot see the workspace. The step PUTs the policy and the data through OPA's API and then asserts one known-true decision, because an OPA with no policy denies everything, which a parity suite would read as disagreement rather than as "the policy never loaded".

## Tests

- Against a real OPA: **922 passed** (461 stand-in, 461 real Rego). The Rego and the Python driver agree on every role, permission and assurance combination.
- Without OPA: 461 passed, 461 skipped.
- **Verified non-vacuous.** Commenting out `not step_up_missing` in `authz.rego`, a real policy bug that would let an operation proceed without MFA step-up, fails the suite on exactly the step-up-protected permissions (`merchant:suspend`, `admin:manage`). Before this change that edit was invisible to CI.
- The CI upload path was run end to end against an empty OPA container: policy PUT, data PUT, known-true probe, then the full suite green at 922.

## Open issues / next step

- The stand-in and the Rego can still drift in the `demo` profile. The real lane catches it, so the window is one CI run rather than a release, but the duplication is a cost to keep in mind if the policy grows.
- M-IAM's other scope (Keycloak staff SSO, the MCP client registry, shared OTP state, refresh and revocation) was implemented by the other agent and is covered by `tests/unit/test_iam.py`, including `test_a_revoked_staff_token_is_refused_with_401`, which is acceptance test 2. I have not independently reviewed the Keycloak driver against a running Keycloak; there is no Keycloak in the compose file or the CI lane, so that driver is in the same position the OPA driver was in before this change. Worth its own issue.

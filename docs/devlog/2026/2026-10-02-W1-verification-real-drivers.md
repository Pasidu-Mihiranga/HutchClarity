# 2026-10-02 - Wave 1 verification: parity suites against the real components

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work packages | M-GOV (#20), M-DEC (#36), M-RCPT (#37), M-REC (#38) |
| Context | These were implemented by another agent (Codex). This entry is the verification and what it found. |

The question asked of each was the one that caught the OPA gap: does the acceptance test exercise the real thing, or something written to agree with the code?

## M-RCPT (#37): a real gap, fixed

`_openbao_signer()` built the driver over `httpx.MockTransport` with a Python
stand-in of OpenBao's Transit API. A real OpenBao sat in `deploy/compose/full.yml`
and **no test ever used it**, so the driver's request shape, token header,
response parsing and signature format were unverified. The signing path is what
proves to a customer that a fix happened.

Added `openbao-real` to `SIGNING_DRIVERS`, provisioning its own Transit key per
run, and a key-rotation test (acceptance 1) against the real service.

**The driver turned out to be correct**, which is worth saying plainly: it signs
and verifies against real OpenBao, and rotation behaves as promised.

**The gap was real even so.** Changing the Transit path to `/v1/transit/v2/sign/...`,
a wrong-URL bug, leaves the stand-in lane passing 5 tests while the real lane
fails 4. The stand-in only looks for `/sign/` anywhere in the URL, so it cannot
disagree with the driver about where the endpoint is.

Also fixed: the compose healthcheck ran `bao status`, which defaults to HTTPS and
fails against a dev server speaking HTTP, so a working OpenBao reported unhealthy
and `make up-full` stalled. It now sets `BAO_ADDR`.

## M-DEC (#36): sound

`zen.py` evaluates the checked-in JDM artefact in process rather than through
the GoRules ZEN engine, and its docstring says so. Unlike the OPA case there is
no second implementation claiming to be the real one: the parity test compares
two genuinely different implementations, `DecisionPolicy` (ordered Python rules)
against `ZenDecisionPolicy` reading `config/policy/decision-table.json`, and it
loads the real governed file.

Verified non-vacuous. Changing one row's outcome from `HANDOFF` to `AUTO_FIX`
fails 15 tests including the 1,000 generated inputs. Swapping the first two rows
does **not** fail, which is correct rather than a weakness: those predicates are
mutually exclusive, so with `hitPolicy: first` the order between them cannot
change an outcome.

Remaining gap: the JDM file is never loaded by the real ZEN engine, so nothing
proves it is valid GoRules JDM. Lower risk than the OPA case, because the
adapter is the implementation rather than a claim about one, but it means a
cutover to the real engine is not yet de-risked.

## M-GOV (#20): sound

Both acceptance tests are present and substantive. Verified non-vacuous:
removing the `approver_ref == change.maker_ref` check fails
`test_the_maker_cannot_approve_their_own_change`. Separation of duties is really
enforced, not assumed.

## M-REC (#38): sound

Verified non-vacuous: disabling the mismatch publish fails
`test_missing_adapter_confirmation_publishes_a_mismatch`.

Note, from fixing the tree earlier: `reconciliation.expected_actions`,
`reconciliation.mismatches` and four `iam.*` collections had **no registered
schema owner**, which the B05 ownership guard refused rather than defaulting.
Without that they would have reached the `full` profile with no role grants and
no row-level security.

## Tests

- `make check`: **1210 passed, 512 skipped**. The skips are the real-driver lanes.
- Full profile with PostgreSQL, Kafka, OPA and OpenBao all running: **1090 passed, 0 skipped**.
- OPA and OpenBao added to the CI `full` lane and to `make test-full`.

## Open issues / next step

- **No Keycloak anywhere.** Not in compose, not in CI. The Keycloak driver is in exactly the position the OPA and OpenBao drivers were in before today: written and never run against the real service. This deserves its own issue before anyone relies on staff SSO.
- The real GoRules ZEN engine never loads the JDM file (above).
- Both stand-ins remain, so they can drift from the real services in the `demo` profile. The real lanes catch it within one CI run rather than at a release, but the duplication is a standing cost.

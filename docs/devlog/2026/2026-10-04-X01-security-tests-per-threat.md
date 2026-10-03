# 2026-10-04 - X01 - Security tests per threat

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus) wrote the tests and this entry |
| Work package | X01 (issue #42), plan 11 threat register |
| PR / commit | #42 |
| Units touched | tests/security |

## What changed

- `backend/tests/security/test_th05_replay.py`: the acceptance test for this
  issue plus eight more, all written as the attack rather than as the feature.
  A captured token cannot be redeemed twice, moved to another plan, or used
  after its TTL; a replayed confirm moves money once and returns the first
  receipt; and one customer cannot confirm another's plan.
- `backend/tests/security/test_threat_register.py`: parses the TH table out of
  plan 11 and requires every threat to appear in exactly one of `MITIGATED`
  (naming a test that demonstrates the mitigation) or `NOT_MITIGABLE_HERE`
  (with the reason). 16 threats are tested, 3 are explicitly out of scope.

## Why

Issue #42 asks for "tests for each mitigable threat", which is only a checkable
claim if something compares the test suite against the register. `MITIGATED` is
derived against the plan rather than hand-copied, so adding TH20 to plan 11
fails the suite until somebody decides which half it belongs in.

## Decisions made

1. **Three threats are recorded as not mitigable here, with reasons.** TH9
   (compromised API keys) needs upstream anomaly alerting; TH11 (insider
   tampering with the audit trail) needs WORM anchors and SIEM copies, and a
   test here would only re-check the hash chain and overstate the coverage;
   TH12 (denial of service) needs a WAF and edge rate limits, and load testing
   is issue #43. Writing a test that pretends to cover a deployment control
   would report coverage that does not exist, which is worse than no test. Same
   shape as an `UNEVALUABLE` evaluation gate.
2. **The map names one test per threat, chosen as the one that fails if the
   mitigation is removed.** Several threats have much wider coverage than the
   single test named; the map is a tripwire, not an inventory.
3. **`test_the_named_test_for_a_threat_exists` greps for the function.** A map
   entry pointing at a renamed test is a coverage claim with nothing behind it.
4. **Subject binding is tested at the route, not at the tool layer.** My first
   attempt asserted that `ToolLayer.confirm_by_customer` refuses a mismatched
   `subscriber_ref`, and it does not. That turned out to be correct rather than
   a defect: `ActionPlan` carries a `case_id` and no `subscriber_ref`, so the
   tool layer cannot check the subject without an `actions -> case` edge, which
   the dependency map forbids as a cycle (I22). The binding is enforced where
   the caller's identity exists, which is the route
   (`authorize_case_access`), and `ResolutionService` always passes the case's
   own ref down. The test was rewritten to attack the surface that can actually
   be attacked: a signed-in customer replaying another customer's case id and
   plan id, which gets 403.
5. **Refusals are asserted to be indistinguishable.** Unknown, spent, expired
   and plan-mismatched all raise the same message. A different message per
   reason is an oracle for searching the token space, so the sameness is the
   control and is tested as one.

## Docs updated

- [ ] MODULE.md - no module surface changed
- [ ] CHANGELOG.md - no contract change
- [x] This devlog entry

## Tests

```
backend/tests/security/   49 passed
make check                1936 passed, 544 skipped
```

Three non-vacuity probes on the register map:

| Probe | Test that failed |
|---|---|
| drop TH13 from both maps | every-threat-is-tested-or-out-of-scope[TH13] |
| point TH10 at a renamed test | the-named-test-for-a-threat-exists[TH10] |
| excuse TH12 with "not now" | an-out-of-scope-threat-says-why[TH12] |

## Open issues / next step

- **The ZAP baseline is not done.** The issue says "OWASP ZAP baseline on
  staging" and there is no staging environment. The plan is a CI job that
  starts the app locally and scans it, which is an honest substitute and must
  be labelled as one. Blocked today on the ZAP image failing to pull
  (`short read: expected 587795589 bytes but got 268559424`); it will not go
  into CI until it has been run locally first, because an unverified new job is
  how the lanes went red in the first place.
- Dependency and licence scanning is already blocking (the `sbom` and `secrets`
  lanes, #18), so that part of the scope is covered.

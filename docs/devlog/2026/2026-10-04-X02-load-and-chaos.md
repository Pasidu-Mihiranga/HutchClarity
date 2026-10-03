# 2026-10-04 - X02 - Load at 10x pilot, and the degradation ladder

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus) wrote the scenarios, tests and this entry |
| Work package | X02 (issue #43), plan 03 section 4.2, plan 15 sections 38-39 |
| PR / commit | #43 |
| Units touched | tests/chaos, tests/load, Makefile |

## What changed

- `backend/tests/chaos/test_degradation.py`: five end-to-end tests that break
  the model provider and drive the real customer journey over HTTP.
- `backend/tests/load/journeys.js`: a k6 scenario running the four journeys at
  10x pilot load, with the plan's own NFR thresholds.
- `make chaos`, `make load` and `make load-api`.

## Why

Issue #43, acceptance 1 (the API at 10x pilot load meets the p95 targets from
03 section 4.2) and acceptance 2 (the provider down, customers ask questions,
template answers, no errors).

## Where "10x pilot load" came from

NFR-SC-01 says "model tested to 10x pilot load" and never states the pilot.
Plan 15 section 38 does: the pilot column is 2K interactions/day, 16K API
requests/day, peak API RPS ~1. So 10x pilot is **~10 RPS peak**, which is what
the scenario drives. Both numbers are **ASSUMPTION / PROPOSED TARGET -
REQUIRES HUTCH VALIDATION**, and the scenario's header says so: passing it
means the prototype meets a target this project wrote down, not a measurement
of HUTCH's real load.

## Measured (lite profile, simulated adapters, 30s at 10 RPS)

| Metric | Target | Measured |
|---|---|---|
| Why? end to end, p95 (NFR-PERF-01) | 2,500 ms | **19.8 ms** |
| Receipt verification, p95 (NFR-PERF-05) | 800 ms | **4.0 ms** |
| Failed requests | < 1% | **0.00%** (0 of 775) |
| Sustained rate | 10 RPS | 9.97 iterations/s, 300 complete |

The margin is large because the `lite` profile's HUTCH adapters are in-process
simulations. NFR-PERF-01 excludes "HUTCH adapter latency beyond its SLA", so
the comparison is the right one, but it is not evidence about a deployment with
real adapters, PostgreSQL and Kafka.

## Decisions made, and two things the first runs got wrong

1. **The first run reported 92% failures, and the system was fine.** The script
   signed in on every iteration as one subscriber, and the OTP rate limit
   (plan 11 TH1) correctly answered 429. A load script that re-authenticates
   per iteration measures the rate limiter. Sign-in moved to `setup()`, outside
   the measured load, which is also what a real signed-in customer does.
2. **The second run reported 9.9% failures, and the system was still fine.**
   After three one-tap fixes, the same subscriber's next case was decided
   `STAFF_APPROVAL` and the customer confirm was refused with 403
   `CONFIRMATION_REQUIRED`. That is the refund-velocity policy (TH2) doing its
   job. The scenario now treats 403-with-a-code as an expected answer on that
   step, and separately asserts that the money path never returns a 5xx. The
   outcome check was loosened from "this subscriber is always ONE_TAP_FIX" to
   "a real outcome was reached", because pinning it would read correct policy
   as a regression.
3. **Both of those are recorded in the script, not just here.** The comments
   say what the first versions measured and why, so the next person does not
   re-derive them by rediscovering a 90% failure rate.
4. **The chaos tests are end to end, not at the gateway.**
   `tests/unit/test_ai.py::test_a_provider_outage_falls_back_to_a_template`
   already covers the unit. What these add is the rest of the path: the
   customer still gets a 200, the rules still decide, the amount is still in
   the answer, the whole money path still completes and the receipt still
   verifies.
5. **One chaos test asserts the outage was real.** `dead.attempts > 0`, because
   a fallback nobody can see is indistinguishable from a model that works, and
   a test that passes because the model path was skipped proves nothing.
6. **A degraded answer is checked for leaks.** `ConnectionError`, `Traceback`
   and the provider's own name must not reach the customer.

## Docs updated

- [ ] MODULE.md - no module surface changed
- [ ] CHANGELOG.md - no contract change
- [x] This devlog entry; `make chaos`, `make load`, `make load-api` in the Makefile

## Tests

```
make chaos    5 passed
make check    1941 passed, 544 skipped
k6 journeys   all thresholds passed, 0.00% failed, 300 iterations at 9.97/s
```

Non-vacuity: narrowing the AI gateway's `except Exception` to `except
ZeroDivisionError` fails all five chaos tests.

## Open issues / next step

- **Chaos covers one row of plan 39's table.** The provider-outage row is done
  end to end. The relay-killed row is covered at unit level by B04's
  `test_a_relay_killed_before_recording_redelivers_and_applies_once`, and the
  PostgreSQL failover and Kafka-delayed rows need the `full` stack plus a way
  to stop a container mid-test. Those are the next ones to add, and they belong
  in the full lane rather than here.
- **The load run is not in CI.** It needs k6 and a running API, and the
  per-subscriber protections mean each run needs a fresh process. `make load`
  and `make load-api` document that; wiring it as a nightly job against the
  `full` profile would be the useful next step, since the `lite` numbers above
  are not the ones that matter.

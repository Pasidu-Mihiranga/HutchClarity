# 2026-10-04 - AUDIT - tests follow the 078 subscribers

| Field | Value |
|---|---|
| Author(s) | agent: Grok |
| Work package | audit assurance, merge with main |
| PR / commit | #69 |
| Units touched | tests |

## What changed

- The audit coverage, grant and trail-wiring tests take Dilani and Priya from the acceptance fixtures.

## Why

Main moved the synthetic subscribers from the 077 prefix to Hutch's 078 prefix. Those three files still signed in as `+94771234567` and `+94774445555`, so the world answered 404 and nine tests failed in the lite CI lane.

## Decisions made

- The unknown-number case `+94770000001` stays. It is not a seeded subscriber, and the test is that a missing number is still recorded without the raw value.

## Docs updated

- [x] This devlog
- [ ] MODULE.md, CHANGELOG, plan: test fixtures only

## Tests

`pytest tests/security/test_audit_coverage.py tests/security/test_audit_grants.py::test_a_monitor_is_refused_an_approval_they_could_make_before tests/unit/test_audit_trail_wiring.py` passed locally.

## Open issues / next step

None for this failure.

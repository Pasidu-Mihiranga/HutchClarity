# 0005 - An idempotency key is claimed before anything is consumed

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Plan references | `docs/improvement-plan.md` F1, A1; alternative design 17 §12 |

## Context
`ToolLayer.execute` recorded the idempotency key **after** redeeming the
confirmation token and reserving budget. Under 2,000 concurrent identical
calls, 1,051 failed with `CONFIRMATION_INVALID` or `PLAN_NOT_PENDING`: a
duplicate arriving inside that window missed the key, then found the token
already spent.

Money was never at risk - exactly one refund every time - but a customer who
double-tapped Confirm would have seen an error after a successful fix. Separately,
`ConfirmationService.redeem` was a check-then-add with no lock, so single use
relied on the GIL and would not survive free-threaded Python.

## Decision
The key is claimed atomically **before** the token is redeemed. A duplicate
waits on the original and receives its outcome. The outcome of a key is
**final**, success or failure: releasing it on failure would let a duplicate
arriving moments later start fresh and get a different error for the same
request. A caller wanting a genuine new attempt uses a new key. Token
redemption and the mock command adapter take locks.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Release the key on failure so it can be retried | Creates the inconsistency above. Standard practice (for example Stripe) records the outcome either way. |
| Rely on the GIL | Not a design guarantee, and it breaks under free-threaded builds |

## Consequences
A duplicate may wait up to `duplicate_wait_seconds` and then receive
`EXECUTION_IN_PROGRESS`, which the caller retries with the same key.

## Compliance
`tests/unit/test_tool_layer.py::test_fifty_concurrent_identical_calls_execute_exactly_once`
runs 12 trials of 50 concurrent calls with `setswitchinterval(1e-7)` and
requires 1 fresh, 49 replayed, 0 errors, 1 credit.

# 2026-10-02 - M-ACT - Database idempotency, retry after transient failure

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | M-ACT (issue #25), Wave 1; plan 21 section 11.5, ADR-0005, I8 |
| Units touched | actions, case, contracts/events, app (collections), platform/persistence (schemas) |
| Review | money path: two approvals per AGENTS.md section 10 |

## What changed

- `actions/attempts.py` (new): one durable record per `Idempotency-Key`, claimed and settled through the repository, replacing the in-process `_attempts` dict.
- **A failure is now either final or transient.** `ToolLayerError.transient` marks the difference. A final refusal is replayed for the same key; a transient one leaves the key claimable, so the retry is a real attempt with the next attempt number.
- `actions/confirmation.py`: tokens are records in a repository, looked up by a SHA-256 of the value. The value itself is never stored.
- `RefundBudget.start_new_day()`: the ceiling is daily, so something has to mark the boundary. This is what makes a budget refusal transient in practice rather than in principle.
- Publishes `approval.requested@v1` (new payload) and `action.failed@v1`, which now carries `retryable` and `attempt`.
- `case`: a replayed execution no longer advances the case. Nothing happened, so nothing may move.

## Why

Issue #25. Idempotency was a dict, so a second replica would have refunded again. Worse, the first failure was stored against the key and replayed forever, so a plan refused because the day's refund allowance was spent could never execute, even after midnight. That is a stuck plan created by a correctly working guard.

## Decisions made

- **Final versus transient, decided by the error type, not the call site.** A refusal the policy made must replay, or a caller could get a different answer for one request by asking twice. A condition that has passed must not. Putting the distinction on the exception keeps it with the code that knows which it is.
- **An unexpected exception is treated as final.** Nothing is known about whether it is safe to retry, and on a money path a stuck plan is recoverable by a person while a double refund is not.
- **The budget is reserved before the confirmation token is redeemed.** This was a real bug found by the acceptance test: a confirmation is single use, so consuming it and then refusing for an unrelated reason burns the customer's authority. The retry M-ACT makes possible would then have failed with `CONFIRMATION_INVALID` forever instead of executing. Reserving applies nothing outside the budget and is released if anything after it refuses.
- **A token record stores a hash, not the value.** A dump of that table must not let anyone execute a plan.
- **`approval.requested` is published when an approval is still short**, so a supervisor can be told rather than the plan waiting for somebody to notice.

## Docs updated

- [x] Plan 21 section 11.3: `approval.requested` moved from planned to exists
- [x] `backend/src/clarity/modules/actions/MODULE.md`: events, collections, change history
- [x] `tests/architecture/test_module_state.py`: two of the three `DEFERRED` entries removed, because they are fixed
- [ ] ARCHITECTURE.md: the concurrency row already says two replicas can share one database; the set of state that holds for grew, which the MODULE.md records
- [ ] CHANGELOG.md: no `/v1` contract change; the OpenAPI snapshot is unchanged

## Tests

- **Acceptance 1** (`tests/unit/test_tool_layer.py`): a plan refused because the day's allowance was spent executes exactly once after the budget resets, using the same key and the same token, and a third call replays rather than refunding again. Verified to fail before the change.
- **Acceptance 2** (`tests/integration/test_two_replicas.py`): two real OS processes execute one plan through the real tool layer against one PostgreSQL. Exactly one execution, one replay, the same amount, one attempt record.
- `make check`: **682 passed, 45 skipped**. Full profile: **142 passed**.

Honest note on acceptance 2: three mechanisms enforce one execution, and each alone is sufficient (the durable claim, the single-use confirmation, the plan's status). Disabling one and watching the test still pass means the other two held, not that the test is vacuous. It pins the guarantee, which is the right shape on a money path, but it does not isolate a single mechanism. The test says so.

## Open issues / next step

- **The budget counters are still in the process.** Idempotency and confirmations moved; the daily counters need a conditional `UPDATE ... WHERE remaining >= :amount` rather than a repository put, because two replicas reading then writing a counter can both pass a version check on different rows. `DEFERRED` in `test_module_state.py` still lists `actions/budget.py:_reservations` against this issue, so the limitation is visible in CI. Until then two replicas can overspend the daily ceiling, though neither can double-execute a plan.
- `_settled_outcome` polls for an attempt that is still running. A listen/notify or a short lock would remove the poll.
- No reaper for attempt records or spent confirmations. Both grow without bound; a retention job belongs with X03.

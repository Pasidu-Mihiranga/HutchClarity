# reconciliation - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.reconciliation`) |
| Deployable | `clarity-worker` schedule; modular monolith today |
| Owner | TBD |
| Status | built |
| Files | `public.py`, `service.py` |

## 1. Purpose

Consume completed actions, perform the daily T+1 match against adapter confirmations, persist discrepancies and publish finance alerts.

## 2. Public surface (`public.py`)

`ReconciliationService`, `ExpectedAction`, `ReconciliationMismatch` and owned collection names.

## 3. Used by

`clarity.app`, `clarity.interfaces.http`

## 4. Depends on

Only lower layers: contracts, integration command status, kernel, messaging and persistence. It receives `action.completed@v1`; it never calls the actions module.

## 5. Data owned

Collections `reconciliation.expected_actions` and `reconciliation.mismatches`. The latter is the finance queue projection.

## 6. Invariants

- Matching uses the action step's idempotency key and adapter reference, never customer text.
- A missing or inconsistent confirmation becomes a mismatch for a person; it is never guessed away.
- One action produces at most one mismatch for a given reconciliation day.

## 7. Migration status

M-REC complete. The scheduler entry point is `ReconciliationService.run_daily`; deployment scheduling belongs to the worker runtime.

## 8. Tests

- `tests/unit/test_reconciliation.py`

## 9. Change history

| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-M-REC-daily-action-reconciliation.md` | T+1 matcher, mismatch event and finance queue (M-REC, #38) |

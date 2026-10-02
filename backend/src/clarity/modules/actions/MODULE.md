# actions - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.actions`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `budget.py`, `capability.py`, `confirmation.py`, `errors.py`, `layer.py`, `public.py`, `records.py`, `repository.py`, `results.py` |

## 1. Purpose
Tool layer: turns an allowed decision into action plans, mints and redeems single-use confirmation tokens, enforces four-eyes approval and the refund budget, executes idempotently and compensates on partial failure. The only code that moves money.

## 2. Public surface (`public.py`)
Other code imports only these names: `EXECUTABLE_OUTCOMES`, `ActionNotAllowed`, `ApprovalRequired`, `BudgetExhausted`, `ConfirmationInvalid`, `ConfirmationRequired`, `ConfirmationToken`, `ConfirmedBy`, `ExecutionFailed`, `ExecutionInProgress`, `ExecutionResult`, `OutcomeNotExecutable`, `PlanNotFound`, `PlanNotPending`, `ToolLayerError`.

**Capability surface** (`capability.py`, restricted to `modules.case` and `app`): `ToolLayer`, `ConfirmationService`, `RefundBudget`, `FOUR_EYES_THRESHOLD_LKR`.

## 3. Used by
`clarity.app`, `clarity.interfaces.http`, `clarity.interfaces.mcp`, `clarity.modules.case`, `clarity.modules.receipts`

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.contracts` | - |
| `clarity.integration.ports` | - |
| `clarity.kernel` | - |

## 5. Data owned
Plan records with their approvals, budget reservation and outcome, behind `PlanRepository` (B02). Collection: `actions.plans`. The `demo` profile binds the in-memory driver, `full` binds PostgreSQL schema `actions` with its own role (ADR-0013); both pass `tests/contract/test_repository_parity.py`.

Still in the process until M-ACT (#25): budget counters and reservations (`budget.py`) and confirmation tokens (`confirmation.py`). Both are money-path concurrency state, and M-ACT replaces the process-local lock with database row locks and a conditional `UPDATE`. They are recorded in `DEFERRED` in `tests/architecture/test_module_state.py`, so the limitation is visible in CI rather than forgotten.

## 5a. Events

| Event | Direction | Notes |
|---|---|---|
| `action.completed@v1` | **publishes** | Written to the outbox in the same unit of work that marks the plan completed, so no interleaving shows a completed plan with no event (I7). Keyed by `subscriber_ref`. Carries identifiers, step outcomes and amounts as `Money` strings only (ADR-0029 section 4). |

## 6. Invariants
- Executes only what `Decision.allowed_actions` permits; amounts come from the decision, never the caller.
- Nothing executes without a confirmation token minted outside the AI path (customer tap, staff approval, or system auto-fix for a whitelisted AUTO_FIX).
- One idempotency key per plan; a duplicate gets the original outcome, never a second execution (ADR-0005).
- A refund is never clawed back; other completed steps are compensated and the case goes to a person.

## 7. Migration status (enterprise-plan 21)
Plans, tokens, attempts and budget live in process memory (`lite`). R3: idempotency as a database unique key, plan status under row locks, budget as ledger rows; four-eyes threshold from the decision's policy snapshot (D2).

## 8. Tests
- `tests/architecture/test_module_boundaries.py`
- `tests/unit/test_receipts.py`
- `tests/unit/test_tool_layer.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.actions` with a public surface (R1) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-B02-unit-of-work-and-repositories.md` | Plan records moved behind `PlanRepository`; `PlanRecord` and the four-eyes threshold extracted to `records.py` (B02, #5) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-B06-receipts-on-action-completed.md` | Publishes `action.completed` in the plan-completion transaction; `ToolLayer` takes a unit-of-work factory (B06, #14) |

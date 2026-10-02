# actions - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.actions`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `attempts.py`, `budget.py`, `capability.py`, `confirmation.py`, `errors.py`, `layer.py`, `public.py`, `records.py`, `repository.py`, `results.py` |

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
Plan records with their approvals, budget reservation and outcome, behind `PlanRepository` (B02). Collections: `actions.plans`, `actions.attempts` (one durable record per idempotency key, M-ACT), `actions.confirmations` (minted tokens, stored as a hash of the value and never the value). The `demo` profile binds the in-memory driver, `full` binds PostgreSQL schema `actions` with its own role (ADR-0013); both pass `tests/contract/test_repository_parity.py`.

Still in the process: the daily budget counters (`budget.py`). They need a conditional `UPDATE ... WHERE remaining >= :amount` rather than a repository put, because two replicas reading then writing a counter can both pass a version check. Recorded in `DEFERRED` in `tests/architecture/test_module_state.py`, so the limitation is visible in CI. Two replicas cannot double-execute a plan, but they can overspend the daily ceiling.

## 5a. Events

| Event | Direction | Notes |
|---|---|---|
| `action.completed@v1` | **publishes** | Written to the outbox in the same unit of work that marks the plan completed, so no interleaving shows a completed plan with no event (I7). Keyed by `subscriber_ref`. Carries identifiers, step outcomes and amounts as `Money` strings only (ADR-0029 section 4). |
| `action.failed@v1` | **publishes** | A plan that did not execute, with `retryable` saying whether the same plan may be tried again and `attempt` saying which try this was (M-ACT). |
| `approval.requested@v1` | **publishes** | A plan is short of approvals, with how many are needed and the threshold that decided it, so a notification can ask without reading the policy (M-ACT). |

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
| 2026-10-02 | `docs/devlog/2026/2026-10-02-M-ACT-database-idempotency-and-retry.md` | Durable idempotency, transient-versus-final refusals, durable confirmations, `approval.requested` and `action.failed` published (M-ACT, #25) |

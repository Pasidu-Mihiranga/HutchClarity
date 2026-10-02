# actions - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.actions`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `budget.py`, `capability.py`, `confirmation.py`, `errors.py`, `layer.py`, `public.py`, `results.py` |

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
In-memory structures in the `lite` profile. Target: one PostgreSQL schema `actions` with its own role (ADR-0013), same repository interfaces, same parity suite.

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

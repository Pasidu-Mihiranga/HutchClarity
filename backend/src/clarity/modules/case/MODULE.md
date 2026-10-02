# case - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.case`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `aggregate.py`, `public.py`, `records.py`, `repository.py` |

## 1. Purpose
Case aggregate and the orchestration every channel shares: open a case, build the timeline, evaluate rules and policy, propose, confirm or approve, execute and issue the receipt.

## 2. Public surface (`public.py`)
Other code imports only these names: `CASES`, `CASE_SEQUENCE`, `NO_CONFIRMATION_CHANNELS`, `CaseAggregate`, `CaseNotFound`, `CaseNotReady`, `CaseRecord`, `CaseRepository`, `StoredCaseRepository`.

The orchestration that used to be `CaseService` moved to `clarity.modules.resolution` (M-CASE, #34). What remains is the aggregate: one case, its evidence, its decision, and the states it may move between.

## 3. Used by
`clarity.app`, `clarity.interfaces.http`, `clarity.interfaces.mcp`

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.contracts` | - |
| `clarity.kernel` | - |
| `clarity.modules.actions` | capability, public |
| `clarity.modules.decision` | public |
| `clarity.modules.detection` | public |
| `clarity.modules.receipts` | public |
| `clarity.modules.timeline` | public |
| `clarity.platform.config` | - |
| `clarity.platform.content` | - |

## 5. Data owned
Case records and the per-year case-number sequence, behind `CaseRepository` (B02). Collections: `case.records`, `case.sequence`. The `demo` profile binds the in-memory driver, `full` binds PostgreSQL schema `case` with its own role (ADR-0013); both pass `tests/contract/test_repository_parity.py`. The service holds no state of its own.

## 5a. Events

| Event | Direction | Notes |
|---|---|---|
| `action.completed@v1` | **consumes** (group `receipts`) | `on_action_completed` issues the one receipt for the completed plan, then caches it on the case record. Idempotent by plan id: delivery is at-least-once (B06, plan 21 section 11.5). |

## 6. Invariants
- The money path is identical whichever channel the customer starts from.
- Risk signals and safeguard parameters are derived from evidence, never supplied by callers (ADR-0008).
- Reading a case never re-decides it; an executed case keeps the decision its receipt cites.

## 7. Migration status (enterprise-plan 21)
**Done.** Orchestration moved to `clarity.modules.resolution` and receipts are issued from `action.completed` by an idempotent consumer (plan 21 section 2.2; M-CASE #34, B06 #14).

## 8. Tests
- `tests/unit/test_mcp.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.case` with a public surface (R1) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-B02-unit-of-work-and-repositories.md` | Case records and the case-number sequence moved behind `CaseRepository`; `CaseRecord` extracted to `records.py` (B02, #5) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-B06-receipts-on-action-completed.md` | Consumes `action.completed` and issues the receipt from it; per-plan lock removed, replaced by joining the winner's outcome (B06, #14) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-M-CASE-resolution-service.md` | Orchestration split out to `resolution`; the aggregate and its state machine remain (M-CASE, #34) |

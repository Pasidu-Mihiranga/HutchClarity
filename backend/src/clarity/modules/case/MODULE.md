# case - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.case`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `public.py`, `service.py` |

## 1. Purpose
Case aggregate and the orchestration every channel shares: open a case, build the timeline, evaluate rules and policy, propose, confirm or approve, execute and issue the receipt.

## 2. Public surface (`public.py`)
Other code imports only these names: `CaseNotFound`, `CaseNotReady`, `CaseRecord`, `CaseService`.

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
In-memory structures in the `lite` profile. Target: one PostgreSQL schema `case` with its own role (ADR-0013), same repository interfaces, same parity suite.

## 6. Invariants
- The money path is identical whichever channel the customer starts from.
- Risk signals and safeguard parameters are derived from evidence, never supplied by callers (ADR-0008).
- Reading a case never re-decides it; an executed case keeps the decision its receipt cites.

## 7. Migration status (enterprise-plan 21)
`CaseService` is the orchestrator today. R3 splits it: the case aggregate stays here, orchestration moves to a thin resolution service, and receipts are issued once from `action.completed` (fixes D1 by design).

## 8. Tests
- `tests/unit/test_mcp.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.case` with a public surface (R1) |

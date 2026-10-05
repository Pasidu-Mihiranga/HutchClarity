# resolution - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.resolution`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built; split out of `case` by M-CASE (#34) |
| Files | `public.py`, `service.py` |

## 1. Purpose
The orchestration every channel shares: open a case, build the timeline, evaluate rules and policy, propose, confirm or approve, execute, and read the receipt the resulting event produced.

It holds no state. The case aggregate owns the record and its state machine; this module owns the sequence of calls that fills it in (plan 21 section 2.2).

## 2. Public surface (`public.py`)
Other code imports only these names: `ResolutionService`.

Its method names and signatures are the ones `CaseService` had, so the HTTP and MCP interfaces were unchanged by the split.

## 3. Used by
`clarity.app`, `clarity.interfaces.http`, `clarity.interfaces.mcp`

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.contracts`, `clarity.kernel` | - |
| `clarity.modules.case` | public (the aggregate) |
| `clarity.modules.actions` | capability, public |
| `clarity.modules.decision` | public |
| `clarity.modules.detection` | public |
| `clarity.modules.receipts` | public |
| `clarity.modules.timeline` | public |
| `clarity.platform.config`, `clarity.platform.content` | - |
| `clarity.platform.messaging`, `clarity.platform.observability` | - |

It is the only module permitted to import `actions.capability`, the code that can move money (`tests/architecture/test_module_boundaries.py`). That right follows the orchestrator.

## 5. Data owned
None. Case state is the aggregate's, plan state is the actions module's, receipts are the receipts module's.

## 5a. Events

| Event | Direction | Notes |
|---|---|---|
| `case.created@v1` | **publishes** | On `open_case`, so insights and autopsy can follow a case from its start. |
| `action.completed@v1` | **consumes** (group `receipts`) | Issues the one receipt for the completed plan, idempotent by plan id (B06). |
| `conversation.turn.completed@v1` | **consumes** (group `case-handoff`) | When the turn handed off, records a `HandoffRequest` (queue, reason code, turn) on the case so `GET /v1/desk/queue` lists it. Idempotent: the first request is kept. |

## 6. Invariants
- The money path is identical whichever channel the customer starts from.
- Risk signals and safeguard parameters are derived from evidence, never supplied by callers (ADR-0008).
- Reading a case never re-decides it; an executed case keeps the decision its receipt cites.
- A replayed execution moves nothing: the original call advanced the case and issued the receipt.

## 7. Migration status (enterprise-plan 21)
Section 2.2 asked for orchestration in a thin resolution application service. Done as an L4 module rather than inside `clarity.app`, so the call edges stay declared and test-enforced in the dependency map, which the composition root is not covered by.

## 8. Tests
`backend/tests/unit/test_case_service.py`, `backend/tests/unit/test_receipts_consumer.py`, `backend/tests/acceptance/` (the R0 journeys), `backend/tests/architecture/`.

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-M-CASE-resolution-service.md` | Split out of `CaseService` (M-CASE, #34) |
| 2026-10-05 | `docs/devlog/2026/2026-10-05-E3-handoff-to-desk-and-receipt-link.md` | Conversation handoffs reach the desk queue |

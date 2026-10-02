# governance - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.governance`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `governance.py`, `public.py`, `replay.py` |

## 1. Purpose
Policy change governance: change classes, maker-checker publication, replay impact reports for candidate policy before it is activated.

## 2. Public surface (`public.py`)
Other code imports only these names: `Approval`, `ChangeRefused`, `ChangeState`, `ImpactReport`, `OutcomeChange`, `PolicyChange`, `PolicyGovernance`, `PolicyReplay`, `ReplayCase`, `cases_from`.

## 3. Used by
Tests only (no runtime caller yet).

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.contracts` | - |
| `clarity.kernel` | - |
| `clarity.modules.decision` | public |
| `clarity.platform.audit` | - |
| `clarity.platform.config` | - |

## 5. Data owned
In-memory structures in the `lite` profile. Target: one PostgreSQL schema `governance` with its own role (ADR-0013), same repository interfaces, same parity suite.

## 6. Invariants
- A money-affecting change needs a second approver and an impact report.
- A preview never touches the live resolver.

## 7. Migration status (enterprise-plan 21)
In memory. R2/R3 persist artefacts, approvals and activations (enterprise-plan 20 section 11).

## 8. Tests
- `tests/unit/test_policy.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.governance` with a public surface (R1) |

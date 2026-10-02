# governance - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.governance`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `artefacts.py`, `governance.py`, `public.py`, `replay.py`, `repository.py` |

## 1. Purpose
Policy change governance: change classes, maker-checker publication, replay impact reports for candidate policy before it is activated.

## 2. Public surface (`public.py`)
Other code imports only these names: `Approval`, `ChangeRefused`, `ChangeState`, `ImpactReport`, `OutcomeChange`, `PolicyChange`, `PolicyGovernance`, `PolicyReplay`, `ReplayCase`, `cases_from`.

## 3. Used by
`clarity.app`, `clarity.interfaces.http`

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.contracts` | - |
| `clarity.kernel` | - |
| `clarity.modules.decision` | public |
| `clarity.platform.audit` | - |
| `clarity.platform.config` | - |

## 5. Data owned
Policy change aggregates persist candidate versions, impact reports, approvals, schedules, activations and supersession history behind `PolicyChangeRepository`. Collection: `governance.changes`; full binds the governance PostgreSQL schema (ADR-0013).

## 6. Invariants
- A money-affecting change needs a second approver and an impact report.
- A preview never touches the live resolver.

## 7. Migration status (enterprise-plan 21)
M-GOV complete: Policy Studio exposes draft, replay review, approval, scheduling, activation and governed rollback. Activation updates the live resolver and publishes `policy.published@v1`.

## 8. Tests
- `tests/unit/test_policy.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.governance` with a public surface (R1) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-B02-unit-of-work-and-repositories.md` | Policy changes moved behind `PolicyChangeRepository`; `PolicyChange` and its vocabulary extracted to `artefacts.py` (B02, #5) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-M-GOV-policy-studio-lifecycle.md` | Persisted lifecycle and Policy Studio API (M-GOV, #20) |

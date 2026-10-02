# decision - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.decision`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `assessor.py`, `policy.py`, `public.py`, `zen.py` |

## 1. Purpose
Decision policy: turns ranked causes, evidence completeness and risk signals into an outcome (AUTO_FIX, ONE_TAP_FIX, STAFF_APPROVAL, EXPLAIN_ONLY, HANDOFF) with caps, budgets and a hashed input document.

## 2. Public surface (`public.py`)
Other code imports only `public.py`, including `ZenDecisionPolicy` and the parsed decision-table types.

## 3. Used by
`clarity.app`, `clarity.modules.case`, `clarity.modules.governance`

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.contracts` | - |
| `clarity.kernel` | - |
| `clarity.modules.detection` | public |
| `clarity.platform.config` | - |

## 5. Data owned
In-memory structures in the `lite` profile. Target: one PostgreSQL schema `decision` with its own role (ADR-0013), same repository interfaces, same parity suite.

## 6. Invariants
- Thresholds resolve from the policy store `as_of` the disputed event; the decision records `config_snapshot_hash`.
- Incomplete evidence never auto-fixes.

## 7. Migration status (enterprise-plan 21)
M-DEC complete: production wiring loads `config/policy/decision-table.json` through the GoRules ZEN-compatible driver. A 1,000-input parity suite pins it to the reference Python policy. Resolution publishes `decision.generated@v1`.

## 8. Tests
- `tests/unit/test_decision_policy.py`
- `tests/unit/test_journeys.py`
- `tests/unit/test_policy.py`
- `tests/unit/test_decision_parity.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.decision` with a public surface (R1) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-M-DEC-zen-decision-table.md` | ZEN decision table and reference parity (M-DEC, #36) |

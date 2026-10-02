# detection - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.detection`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `engine.py`, `pack.py`, `predicates.py`, `public.py` |

## 1. Purpose
Rule engine: evaluates versioned YAML rule packs (exists, absent, count, compare with backtracking) over an evidence snapshot, ranks causes and lists ruled-out causes.

## 2. Public surface (`public.py`)
Other code imports only these names: `RuleEngine`, `RuleEvaluation`, `RulePack`, `RulePackLoadError`, `RuleSyntaxError`, `load_packs`.

## 3. Used by
`clarity.app`, `clarity.modules.case`, `clarity.modules.decision`

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.contracts` | - |
| `clarity.kernel` | - |

## 5. Data owned
In-memory structures in the `lite` profile. Target: one PostgreSQL schema `detection` with its own role (ADR-0013), same repository interfaces, same parity suite.

## 6. Invariants
- Rules are data: a pack change is a publish with golden tests, not a deploy (ADR-0001).
- Evaluation is a pure function of snapshot and pack, so any result can be replayed.

## 7. Migration status (enterprise-plan 21)
6 of 16 candidate rules. R3 moves numeric parameters (confidence, windows) to the policy store (D5).

## 8. Tests
- `tests/golden/test_payment_and_pack_rules.py`
- `tests/golden/test_vas_no_consent.py`
- `tests/unit/test_autopsy_foresight.py`
- `tests/unit/test_journeys.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.detection` with a public surface (R1) |

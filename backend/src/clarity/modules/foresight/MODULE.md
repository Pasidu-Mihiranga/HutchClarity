# foresight - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.foresight`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `public.py`, `simulation.py` |

## 1. Purpose
Foresight: scenario simulation over aggregates only, reported as relative bands, not counts.

## 2. Public surface (`public.py`)
Other code imports only these names: `ChangeType`, `Foresight`, `ForesightReport`, `Prediction`, `Scenario`, `Segment`, `VolumeBand`.

## 3. Used by
Tests only (no runtime caller yet).

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.kernel` | - |

## 5. Data owned
In-memory structures in the `lite` profile. Target: one PostgreSQL schema `foresight` with its own role (ADR-0013), same repository interfaces, same parity suite.

## 6. Invariants
- Never uses individual customer data; not decision-ready until backtested.

## 7. Migration status (enterprise-plan 21)
Uncalibrated by design (states so in every report). Runtime target: serverless batch job.

## 8. Tests
- `tests/unit/test_autopsy_foresight.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.foresight` with a public surface (R1) |

# foresight - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.foresight`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `public.py`, `simulation.py`, `backtest.py`, `swarm.py` |

## 1. Purpose
Foresight: scenario simulation over aggregates only, reported as relative bands, not counts, plus the backtest that measures how wrong the baseline was and refuses to call that a calibration.

## 2. Public surface (`public.py`)
Other code imports only `public.py`, including the baseline and backtest names plus F02's `ScenarioRehearsal`, `PersonaSimulator`, `SeededPersonaSimulator`, `SwarmReport` and `Comparison`.

`Foresight.run(scenario, calibration=None)` returns a `ForesightReport`. `Backtest.run(launches)` replays recorded launch outcomes through the baseline and returns a `CalibrationReport`: mean absolute and signed band error, exact-band rate, top-theme hit rate, the pairs it could not compare, and a status.

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
- Persona rehearsal is seeded and aggregate-only. It emits relative bands,
  records its simulator version and has no executing capability.
- **Error is measured in band steps** (LOW=0, MEDIUM=1, HIGH=2), never in complaints, because bands are all the baseline emits.
- **A synthetic launch never moves the calibration status.** `Provenance.SYNTHETIC` outcomes are the predictor's own assumptions played back; they exercise the method and validate nothing (I16). `CalibrationStatus.CALIBRATED` needs `MIN_REAL_LAUNCHES` (3, plan 02 §3.4) launches with `Provenance.REAL`, of which the prototype has none (**REQUIRES HUTCH CONFIRMATION**).
- **Nothing comparable reports no error, not a perfect one.** With zero overlapping (theme, segment) pairs the error fields are `None`; a `0.000` would read as a flawless model. Same shape as an `UNEVALUABLE` evaluation gate.
- **An observed theme the model never predicted is reported, not scored.** It lands in `unpredicted` rather than being treated as a LOW prediction, so under-prediction cannot be averaged away. A prediction with no recorded outcome lands in `unobserved`: absence of a record is not a LOW observation.
- `ForesightReport.backtested` is derived from the calibration handed in, not hard-coded, so the plan §3.4 gate opens on evidence and on nothing else.

## 7. Migration status (enterprise-plan 21)
Uncalibrated by design (states so in every report). Runtime target: serverless batch job.

## 8. Tests
- `tests/unit/test_autopsy_foresight.py`
- `tests/unit/test_foresight_swarm.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.foresight` with a public surface (R1) |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-F01-foresight-backtest-and-calibration.md` | Added `backtest.py`: calibration report, band-step error, the real-launch gate (F01, #27) |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-F02-synthetic-scenario-rehearsal.md` | Added seeded aggregate personas and baseline-vs-swarm comparison |

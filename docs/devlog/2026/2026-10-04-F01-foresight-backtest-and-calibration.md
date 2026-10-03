# 2026-10-04 - F01 - Foresight backtest and calibration report

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus) wrote the code, tests and this entry |
| Work package | F01 (issue #27), plan 02 §3.4 |
| PR / commit | #27 |
| Units touched | foresight |

## What changed

- New `backend/src/clarity/modules/foresight/backtest.py`. `Backtest.run(launches)`
  replays recorded launch outcomes through the existing statistical baseline and
  returns a `CalibrationReport`.
- The error is **mean absolute band error in band steps** (LOW=0, MEDIUM=1,
  HIGH=2), with the signed mean alongside it, an exact-band rate and a top-theme
  hit rate. Bands are the only thing the baseline emits, so a band-step error is
  the only error it can honestly report. It is never a complaint count.
- `CalibrationStatus`: `NOT_CALIBRATED` (no real launch evidence),
  `INSUFFICIENT` (some, below the gate), `CALIBRATED` (at or above
  `MIN_REAL_LAUNCHES = 3`, the plan 02 §3.4 number).
- `HistoricLaunch.provenance` is `SYNTHETIC` or `REAL`. Only `REAL` launches
  count towards the gate. The prototype has none
  (**REQUIRES HUTCH CONFIRMATION**), so every report it can produce today says
  `not_calibrated`.
- `DEMO_LAUNCHES`: three SIMULATED historic launches so the report can be run
  and read now. Their outcomes are authored, not measured, and deliberately do
  not match the baseline: it scores 0.500 mean absolute band error, 0.500 exact
  bands and 0.667 on top themes over 12 comparable pairs.
- `Foresight.run(scenario, calibration=None)`. `ForesightReport.backtested` is
  now derived from the calibration it was handed, instead of the hard-coded
  `False` it carried before, and `ForesightReport.calibration` keeps the
  evidence. `is_decision_ready` therefore opens only on a `CALIBRATED` report.
- 18 tests in `backend/tests/unit/test_autopsy_foresight.py`.

## Why

Issue #27, acceptance 1: "a backtest run | completed | the report states
calibration error **and that results are scenarios**". Both halves are the
point. `simulation.py` already set the bar in its own docstring - "until it is
backtested on >= 3 real launches, neither should be used to make a launch
decision" - and modelled `backtested` as a concept with nothing behind it. This
is the machinery that claim needs.

## Decisions made

1. **A synthetic backtest cannot move the status.** A launch we authored is the
   predictor's own assumptions played back; averaging them produces a number,
   not evidence. So `Provenance.SYNTHETIC` exercises the method and never
   reaches `CALIBRATED`. This is the whole reason the field exists; without it,
   running `make check` would "calibrate" the model.
2. **Nothing comparable reports `None`, not `0.000`.** Zero overlapping pairs
   with a zero error reads as a flawless model. Same shape as A05's
   `UNEVALUABLE` gate: the report states that it could not measure, and
   `summary()` says "not measurable, no comparable pairs".
3. **Asymmetric treatment of the two kinds of mismatch.** An observed theme the
   model never predicted goes to `unpredicted` and is excluded from the error
   rather than scored as a LOW prediction, because scoring it would let
   under-prediction be averaged away. A prediction with no recorded outcome goes
   to `unobserved`: absence of a record is not a LOW observation. Both counts
   appear in the caveats, so the error number cannot be read as complete.
4. **Under-prediction is named as the dangerous direction** in a caveat when the
   signed error is negative. Over-prediction costs a planner some spare CX
   capacity; under-prediction costs customers a launch nobody staffed for.
5. No ADR: this is a module-internal addition that tightens an existing
   invariant rather than a new decision.
6. No `/v1` route. The issue scope is the backtest and the report; foresight
   still has no runtime caller, which is recorded in its MODULE.md.

## Docs updated

- [x] MODULE.md of: foresight (files, public surface, five new invariants, history)
- [ ] ARCHITECTURE.md / modules.md - no structural or status change (still `built`, still a batch-job target)
- [ ] Walkthrough - no user-visible flow
- [x] CHANGELOG.md - the public surface gained seven names and `Foresight.run` gained a keyword argument
- [ ] Plan via CHANGES.md - no plan chapter changed; `plan.md` ticked

## Tests

```
backend/tests/unit/test_autopsy_foresight.py  61 passed
make check                                    1793 passed, 544 skipped in 26.74s
```

Five non-vacuity probes, each breaking the real mechanism and each failing the
test that covers it and not the others:

| Probe | Tests that failed |
|---|---|
| `_status` always returns `CALIBRATED` | synthetic, below-gate, mixing, exact-match, both foresight gate tests |
| `HistoricLaunch.is_real` always `True` | synthetic, mixing, exact-match, both foresight gate tests |
| empty `_mean`/`_rate` return `Decimal("0.000")` | nothing-comparable |
| a missing prediction scored as LOW | observed-theme-missed |
| `backtested=False` hard-coded again | decision-ready-only-with-calibration |

## Open issues / next step

- **The gate cannot be opened from this repository.** It needs three real HUTCH
  launches with recorded per-segment complaint outcomes. `Provenance.REAL`
  exists so that data has somewhere to land; until it arrives, every report says
  `not_calibrated` and `is_decision_ready` is `False`.
- `DEMO_SEGMENTS` shares and complaint rates are still ASSUMPTIONS. A real
  backtest replaces them first, or it measures the baseline against the wrong
  base.
- Plan §3.4's MiroFish/OASIS swarm simulation is still not built. The
  calibration report is what it would be scored against when it is, and the
  band-step comparison works for any predictor that emits the same bands.
- Still no runtime caller and no `/v1` surface for foresight. A console view
  would need one; nothing asks for it yet.

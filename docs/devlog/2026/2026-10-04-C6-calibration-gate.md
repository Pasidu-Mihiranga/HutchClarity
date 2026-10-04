# 2026-10-04 - C6 (F09) - two metrics, and four locks on the calibration gate

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code, for Pasidu Mihiranga |
| Work package | C6 (workstream C, plan item F09) |
| PR / commit | branch `feat/foresight-calibration`, stacked on C4 |
| Units touched | platform/config (a real bug fix), foresight, app/container, interfaces/http |

## What changed

- **`Guardrail.permits` now checks a numeric string.** This is the headline and it is not foresight-specific.
- **`theme_recall` and `segment_rank_correlation`** on `CalibrationReport`, exact, with no float and no new dependency.
- **`RealLaunchCapability`**, a protocol the composition root supplies. `record_launch` with `Provenance.REAL` now needs it *and* a non-empty external `evidence_ref`.
- `StoredLaunch.authority` records which capability permitted a real launch.
- `app/container.py` passes `real_launches=None` explicitly, with the reason.
- The calibration view exposes both new metrics; the launch view exposes `authority`.
- **New ADR-0044** and the index row.

## Why

Plan C6 asks for the two metrics and names four locks that "keep the gate honestly closed". Writing them out found that one of the four did not work.

**The guardrail bug.** C1 moved `MIN_REAL_LAUNCHES` to `foresight.calibration.min_real_launches` with a `min: 3` guardrail, and I flagged in that devlog that the guardrail probably did not bite. It did not. Policy YAML quotes its numbers so they load as exact decimals rather than binary floats, so every value reaching `Guardrail.permits` was a `str`, and the first line was `if not isinstance(value, Decimal | int): return True`.

**Every guardrail in the repository was declared and none of them checked anything.** `detection.*.confidence_base` with `{min: 0.5, max: 1.0}`, the throttle limits, all of them. The fix is six lines and it is the most valuable thing in this package.

Nothing broke when it started checking, which is worth stating: every existing policy value was already inside its declared bounds. The guardrails were right, they were just not enforced.

## Decisions made

- **A capability, not a permission.** C4 already split the duties so `PRODUCT` cannot record outcomes. This is a different question: not *who* may write the row, but whether this **deployment** has real launch records at all. No role can answer that, so it comes from the composition root. No shipped profile wires one, because the prototype has none (REQUIRES HUTCH CONFIRMATION).
- **Two keys, not one.** A capability without an external reference would let somebody with the capability record anything; a reference without a capability would let any deployment claim to have real records. The check runs before anything is written, so a refusal leaves no partial row.
- **`describe()` is stored on the launch.** A report that reaches `CALIBRATED` can then say what permitted it, rather than leaving a reader to trust that something did.
- **A refusal is still an error, never a downgrade to `SYNTHETIC`.** Carried over from C2: a caller whose evidence silently did not count would find out at the gate.
- **`theme_recall` is pooled and deduplicated within a launch.** A theme observed in four segments is one theme the model did or did not anticipate, not four.
- **The rank correlation uses `Fraction` throughout.** Ranks are integers or halves when tied, so every step is rational and nothing needs a square root. Plan 08 §12.9 asks for the metric, not for scipy, and a dependency on a runtime path needs a licence check (I17).
- **An entirely tied observation has no ranking, so the correlation is `None`.** One band for every segment is not an ordering, and scoring it as agreement or disagreement would invent one nobody observed. Same instinct as the existing "nothing comparable reports no error, not a perfect one".
- **Recall matters more than it looks.** A model can have a small band error and be useless: themes it never predicted land in `unpredicted` and are excluded from the error, so without recall the error *improves* as the model predicts less.

## Docs updated

- [x] `MODULE.md` of: foresight (the four locks as an invariant, tests, history)
- [x] This devlog
- [x] `CHANGELOG.md`
- [x] **New ADR-0044** plus the `docs/adr/README.md` index row
- [ ] `/v1` contract: unchanged. The foresight routes return `dict[str, Any]`, so new response keys do not move the OpenAPI schema; `make contracts-check` confirms the committed schema and the SDK still match.
- [ ] `docs/modules.md` / `ARCHITECTURE.md`: not needed. No new module, no new dependency between modules.
- [ ] Plan via `CHANGES.md`: not needed. Plan 08 §12.9 already specified these two metrics; this implements them rather than changing the plan.

## Tests

- `tests/unit/test_foresight_calibration.py`: **32 new tests**, grouped by lock. The guardrail biting on a quoted number and still passing text and booleans; a published value under three refused at load; synthetic launches never reaching `CALIBRATED` at 1, 3, 10 and 50 of them; the two keys needed for a real launch and each one alone failing; the metrics including every `None` case.
- **The golden test**, `test_no_sequence_available_in_a_shipped_profile_reaches_calibrated`, drives every lever a caller has in a shipped profile: draft, try to record real (refused), record synthetic, record outcomes, backtest, ten times over, asserting the status never moves.
- `test_the_container_wires_no_real_launch_capability` asserts it on the composition root rather than on the intention.
- `test_three_real_launches_open_the_gate` exists so the gate is wired to evidence rather than hard-coded shut; without it a broken mechanism would look like a working one.
- `make check`: **2967 passed, 782 skipped** (2935 on C4's branch), ruff, mypy --strict over 250 files, import contracts 3 kept 0 broken.
- `make contracts-check`: SDK types still match the committed schema.

## Open issues / next step

- The guardrail fix is repository-wide. Every existing value passes, but a future numeric key now actually has to respect its bounds, which is the point.
- `segment_rank_correlation` uses the sum-of-squared-differences form. With tied ranks that is the usual approximation rather than Pearson over ranks; the approximation is in the statistic, never in the arithmetic, and it is noted where it is computed.
- A deployment with real launch records has to write and wire a `RealLaunchCapability`. That is a code change, deliberately: it is the moment somebody states what the source of truth is.
- C7 is the last package: the autopsy cluster-rate loop.

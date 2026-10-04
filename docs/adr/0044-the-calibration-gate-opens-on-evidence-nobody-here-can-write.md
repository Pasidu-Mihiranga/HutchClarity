# 0044 - The calibration gate opens on evidence nobody here can write

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-04 |
| Deciders | Pasidu Mihiranga |
| Plan references | workstream C item C6 (F09); enterprise-plan 02 §3.4, 08 §12.9; AGENTS.md I16, D2 |

## Context

Plan 02 §3.4 sets a gate: no launch decision rests on the foresight baseline until it has been backtested against at least three real launches. Every foresight report says so, and `CalibrationStatus.CALIBRATED` is what lifts it.

A gate is only worth the difficulty of opening it. The people who most want this one open are the people who have access to it: a product manager deciding whether to delay a launch, and whoever is asked why the report still says "not usable for a launch decision". There are four ways it could be opened without any real evidence existing, and before C6 three of them were available:

1. **Lower the threshold.** The gate was `MIN_REAL_LAUNCHES = 3`, a Python constant, until C1 made it `foresight.calibration.min_real_launches` with a `min: 3` guardrail. But the guardrail did not work: policy YAML quotes its numbers so they load as exact decimals rather than binary floats, so every value reaching `Guardrail.permits` was a `str`, and `permits` returned `True` for anything that was not a `Decimal` or an `int`. **Every guardrail in the repository was declared and none of them checked anything.**
2. **Relabel a synthetic launch.** `Provenance.REAL` was a field a caller set.
3. **Edit a recorded outcome** into one that scores better.
4. **Write a real launch record with nothing behind it.**

The fourth is the one that matters most, because it is the one that looks legitimate. A row saying `provenance=real` is indistinguishable from a true one unless something outside this system can be checked.

## Decision

**The calibration gate is held shut by four independent locks, and no single change opens it.**

1. **The threshold is a policy key whose guardrail bites.** `Guardrail.permits` now parses a numeric string, so `min: 3` refuses a published value of 2 at load. The key is tagged `regulatory`, so `class_for` derives change class C4 and lowering it needs a second approver. A string that is not a number still passes, because some keys are genuinely textual.
2. **`CALIBRATED` is computed from `Provenance.REAL` alone.** Synthetic launches are counted and reported, and excluded from the count the gate reads.
3. **Recording a `REAL` launch takes two keys**: a `RealLaunchCapability` supplied by the composition root, *and* a non-empty external `evidence_ref`. Neither alone is enough. The capability is not a permission a role carries: it answers whether this *deployment* has real launch records at all. No shipped profile wires one, because the prototype has none (REQUIRES HUTCH CONFIRMATION). The capability's `describe()` is stored on the launch, so a report that reaches `CALIBRATED` can say what permitted it.
4. **The history is append-only.** `foresight.launches`, `foresight.outcomes` and `foresight.calibrations` are append-only in the schema registry and backed by database grants (`INSERT`, `SELECT`, nothing else), so a recorded outcome cannot be edited into a better one.

Alongside this, plan 08 §12.9's two metrics are added: `theme_recall` and `segment_rank_correlation`, exact over integer ranks with no float and no new dependency.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| A permission (`foresight:calibration:override`) instead of a capability | A permission says *who* may write the row. The question here is whether the deployment has anything true to write, which no role can answer. C4 already splits the duties (`PRODUCT` cannot record outcomes); this is the separate question. |
| Trust `provenance=real` and audit it afterwards | The trail would record that somebody wrote it, not whether it was true. By the time an audit found a fabricated launch, a decision would have rested on it. |
| Hard-code the gate shut in the prototype | Then the gate is not wired to evidence and nobody would find out if it were broken. `test_three_real_launches_open_the_gate` exists precisely to prove the mechanism works. |
| Keep `MIN_REAL_LAUNCHES` as a constant | D2: a constant beside a policy key is the one that gets read by mistake, and a threshold nobody can change without a release is a threshold that gets changed in code review instead of in governance. |
| Use scipy for the rank correlation | A dependency for one metric, on a runtime path that must stay neutral and OSI-licensed (I17). The sum-of-squared-rank-differences form needs no square root and so stays exact on `Fraction`. |

## Consequences

**Positive**

- No sequence of calls available in any shipped profile reaches `CALIBRATED`, and a golden test exercises every lever a caller has to prove it.
- Fixing `Guardrail.permits` repairs **every** guardrail in the repository, not only this one. Nothing broke when it started checking, which means every existing policy value was already inside its declared bounds.
- `theme_recall` catches the dangerous direction that the band error cannot: a model that never predicts the themes that actually happen has those excluded from its error, so without recall the error *improves* as the model predicts less.

**Negative**

- A deployment that genuinely has real launch records must write and wire a `RealLaunchCapability`. That is a code change, not configuration, and deliberately so: it is the moment somebody states what the source of truth is.
- `segment_rank_correlation` uses the sum-of-squared-differences form, which with tied ranks is the usual approximation rather than Pearson over ranks. The approximation is in the statistic, never in the arithmetic, and it is noted where it is computed.

**What must now be true**

- No profile in `container.py` passes a `real_launches` capability. A test asserts it on the container itself.
- Any new numeric policy key states its guardrail, now that guardrails are enforced.

## Compliance

- `tests/unit/test_foresight_calibration.py::test_no_sequence_available_in_a_shipped_profile_reaches_calibrated` is the golden test: it drafts, records, observes and backtests ten times over and asserts the status never moves.
- `::test_lowering_the_gate_below_three_is_refused_at_load` fails if the guardrail stops biting.
- `::test_the_container_wires_no_real_launch_capability` fails if a profile ever wires one.
- `::test_three_real_launches_open_the_gate` fails if the gate is ever hard-coded shut instead of wired to evidence.
- Review rule: a change that makes `provenance` caller-settable without both keys, or that makes a foresight evidence collection mutable, supersedes this ADR.

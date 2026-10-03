"""The release gates, and the one thing they must never do (A05, issue #9).

Acceptance test 1 for A05 is the first test below: a regression under a gate
blocks the release and names the metric that failed. Naming matters as much as
blocking, because a nightly job that says only "evaluation failed" sends
somebody to read logs, and the thing most likely to happen then is that the
block gets overridden.

The rest of this file defends the property that makes the gates worth having:
**a gate that could not be evaluated blocks too.** Every test here that looks
like it is labouring the point is there because the opposite behaviour has
already shipped twice in this repository (a parity suite comparing Python with
Python, and a signing driver no test ever called). Both reported green.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from clarity.ai.evaluation import (
    RECORDED,
    GateConfigInvalid,
    GateSet,
    GateStatus,
    Observation,
    Report,
    build_release,
)
from clarity.ai.evaluation.metrics import UNMEASURED, Measurement

REPO = Path(__file__).resolve().parents[3]
GATES = REPO / "config" / "ai" / "gates.yaml"

#: A gate set small enough to reason about, with one per-language metric and
#: one overall metric, so both code paths are covered without reading config.
TWO_GATES = {
    "version": 1,
    "gates": {
        "intake": {
            "dataset": "intake",
            "min_per_language": 10,
            "languages": ["en", "si"],
            "metrics": {"intent_f1": {"min": 0.90, "per_language": True}},
        },
        "safety": {
            "dataset": "safety",
            "min_per_language": 0,
            "metrics": {"executes_refused": {"min": 1.0, "per_language": False}},
        },
    },
}


def _measured(value: float, *, n: int = 50) -> Observation:
    return Observation(value=value, sample_size=n)


def _intake(en: Observation, si: Observation) -> Measurement:
    return Measurement(
        metric="intent_f1",
        overall=_measured(0.95),
        per_language={"en": en, "si": si},
    )


def _safety(value: float) -> Measurement:
    return Measurement(metric="executes_refused", overall=_measured(value))


# --------------------------------------------------------------------------- #
# Acceptance test 1
# --------------------------------------------------------------------------- #


def test_a_regression_below_a_gate_blocks_the_release_and_names_the_metric():
    """A05 acceptance 1: the failing metric is named, not just counted."""
    gates = GateSet.from_document(TWO_GATES)

    release = build_release(
        gates,
        {
            # Sinhala has regressed under the 0.90 gate. English has not.
            "intake": {"intent_f1": _intake(en=_measured(0.94), si=_measured(0.71))},
            "safety": {"executes_refused": _safety(1.0)},
        },
    )

    assert release.blocked
    assert "intake.intent_f1 [si]" in release.failing_metrics
    # The passing language must not be dragged in with it.
    assert "intake.intent_f1 [en]" not in release.failing_metrics
    assert "safety.executes_refused" not in release.failing_metrics

    # The summary a CI job prints has to carry the name through.
    assert "intake.intent_f1 [si]" in release.summary()
    assert "BLOCKED" in release.summary()

    regressed = next(v for v in release.blocking if v.language == "si")
    assert regressed.status is GateStatus.FAIL
    assert regressed.observed == pytest.approx(0.71)
    assert regressed.required == pytest.approx(0.90)


def test_a_release_with_every_gate_clear_is_not_blocked():
    """The guard against test 1 passing for the wrong reason.

    If `blocked` were simply always true, the acceptance test above would pass
    while saying nothing. This is the case that has to come out the other way.
    """
    gates = GateSet.from_document(TWO_GATES)

    release = build_release(
        gates,
        {
            "intake": {"intent_f1": _intake(en=_measured(0.94), si=_measured(0.92))},
            "safety": {"executes_refused": _safety(1.0)},
        },
    )

    assert not release.blocked
    assert release.failing_metrics == ()
    assert "OK" in release.summary()


# --------------------------------------------------------------------------- #
# The property that makes the gates meaningful: unevaluable blocks
# --------------------------------------------------------------------------- #


def test_a_gate_with_no_dataset_blocks_rather_than_passing():
    """The flow and RAG gates today. Absence is not success."""
    gates = GateSet.from_document(TWO_GATES)

    release = build_release(
        gates,
        {"safety": {"executes_refused": _safety(1.0)}},
        reasons={"intake": "the intake set has not been built"},
    )

    assert release.blocked
    unevaluable = [v for v in release.verdicts if v.status is GateStatus.UNEVALUABLE]
    assert {v.language for v in unevaluable} == {"en", "si"}
    assert all("not been built" in v.reason for v in unevaluable)
    assert all(v.observed is None for v in unevaluable)


def test_a_dataset_below_the_required_size_blocks_even_when_the_score_is_perfect():
    """1.00 on four examples is not a pass. This is the intake gate today."""
    gates = GateSet.from_document(TWO_GATES)

    release = build_release(
        gates,
        {
            "intake": {
                "intent_f1": _intake(
                    en=Observation(value=1.0, sample_size=4),
                    si=Observation(value=1.0, sample_size=4),
                )
            },
            "safety": {"executes_refused": _safety(1.0)},
        },
    )

    assert release.blocked
    shortfall = next(v for v in release.blocking if v.language == "en")
    assert shortfall.status is GateStatus.UNEVALUABLE
    assert "below the 10 this gate requires" in shortfall.reason
    # The score is still reported. A gate that hides the number it measured
    # makes the shortfall impossible to size.
    assert shortfall.observed == pytest.approx(1.0)
    assert shortfall.sample_size == 4


def test_a_language_the_gate_requires_but_the_dataset_lacks_blocks():
    """Declaring si in the gate and shipping only en must not pass."""
    gates = GateSet.from_document(TWO_GATES)

    release = build_release(
        gates,
        {
            "intake": {"intent_f1": _intake(en=_measured(0.95), si=UNMEASURED)},
            "safety": {"executes_refused": _safety(1.0)},
        },
    )

    assert release.blocked
    missing = next(v for v in release.blocking if v.language == "si")
    assert missing.status is GateStatus.UNEVALUABLE
    assert "no examples for si" in missing.reason


def test_a_run_that_measured_nothing_at_all_is_blocked():
    """An empty run has not shown the release is safe."""
    gates = GateSet.from_document(TWO_GATES)
    release = build_release(gates, {})

    assert release.blocked
    assert all(v.status is GateStatus.UNEVALUABLE for v in release.verdicts)


def test_every_gate_in_the_set_is_evaluated_even_with_nothing_measured():
    """Iterating over measurements instead of gates is the fail-open bug.

    A gate must not drop out of the report by virtue of having no dataset,
    because that is precisely the gate most in need of reporting.
    """
    gates = GateSet.from_document(TWO_GATES)
    release = build_release(gates, {})

    covered = {(v.gate, v.metric) for v in release.verdicts}
    assert ("intake", "intent_f1") in covered
    assert ("safety", "executes_refused") in covered


# --------------------------------------------------------------------------- #
# The committed gate set
# --------------------------------------------------------------------------- #


def test_the_committed_gate_set_loads_and_carries_every_plan_gate():
    """config/ai/gates.yaml must hold all five datasets from plan 22 section 10."""
    gates = GateSet.from_file(GATES)
    assert set(gates.gates) == {"intake", "safety", "flow", "rag", "language_review"}

    intake = gates.spec("intake")
    assert intake.min_per_language == 300
    assert intake.languages == ("si", "ta", "en", "si-en")
    assert {t.metric for t in intake.thresholds} == {"intent_f1", "slot_accuracy"}
    assert all(t.per_language for t in intake.thresholds)

    # The absolute one: every injection attempt must execute nothing.
    safety = gates.spec("safety")
    assert [t.minimum for t in safety.thresholds] == [1.0]


def test_no_threshold_is_hard_coded_in_the_harness():
    """I10: the numbers live in config, so the harness must hold none of them.

    Checked by reading the source rather than by inspection, because a constant
    added later would otherwise shadow the config silently (D2).
    """
    harness = (REPO / "backend" / "src" / "clarity" / "ai" / "evaluation").glob("*.py")
    for module in harness:
        body = module.read_text(encoding="utf-8")
        for forbidden in ("0.90", "0.98", "4.0", "300"):
            code = "\n".join(line for line in body.splitlines() if not line.strip().startswith("#"))
            assert forbidden not in code, f"{module.name} hard-codes the gate value {forbidden}"


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"version": 1},
        {"version": 1, "gates": {}},
        {"version": 1, "gates": {"intake": {"metrics": {}}}},
        {"version": 1, "gates": {"intake": {"metrics": {"f1": {}}}}},
    ],
)
def test_a_malformed_gate_set_is_refused_rather_than_half_read(document):
    """A gate set that silently loses a gate is worse than one that fails."""
    with pytest.raises(GateConfigInvalid):
        GateSet.from_document(document)


# --------------------------------------------------------------------------- #
# The report, and the nightly job's exit code
# --------------------------------------------------------------------------- #


def test_the_report_names_the_failing_metric_in_both_forms():
    gates = GateSet.from_document(TWO_GATES)
    release = build_release(
        gates,
        {
            "intake": {"intent_f1": _intake(en=_measured(0.94), si=_measured(0.40))},
            "safety": {"executes_refused": _safety(1.0)},
        },
    )
    report = Report(
        run_at=datetime(2026, 10, 3, 2, 0, tzinfo=UTC),
        mode=RECORDED,
        gate_set_version=1,
        release=release,
        dataset_sizes={"intake": {"en": 50, "si": 50}},
    )

    document = report.to_document()
    assert document["release"]["blocked"] is True
    assert "intake.intent_f1 [si]" in document["release"]["failing_metrics"]

    markdown = report.to_markdown()
    assert "intake" in markdown and "si" in markdown
    assert "FAIL" in markdown
    # Simulated figures must never read as measured (I16).
    assert "REQUIRES HUTCH VALIDATION" in markdown


def test_the_report_timestamp_is_injected_not_read_from_the_clock():
    """I11: two reports over the same inputs must be identical."""
    gates = GateSet.from_document(TWO_GATES)
    release = build_release(gates, {"safety": {"executes_refused": _safety(1.0)}})
    fixed = datetime(2026, 10, 3, 2, 0, tzinfo=UTC)

    first = Report(
        run_at=fixed, mode=RECORDED, gate_set_version=1, release=release, dataset_sizes={}
    )
    second = Report(
        run_at=fixed, mode=RECORDED, gate_set_version=1, release=release, dataset_sizes={}
    )
    assert first.to_json() == second.to_json()


def test_the_nightly_job_exits_non_zero_when_a_gate_blocks():
    """The gate has to reach CI as a failed process, not only as a printed table.

    Run as a subprocess on purpose: an in-process assertion on `Release.blocked`
    would pass even if the script swallowed it and exited 0, which is the whole
    mechanism CI depends on.
    """
    script = REPO / "backend" / "scripts" / "evaluate.py"
    finished = subprocess.run(
        [sys.executable, str(script), "--report-dir", "-"],
        capture_output=True,
        text=True,
        cwd=REPO / "backend",
        timeout=180,
        check=False,
    )

    # The intake set is below its required size and flow/RAG have no dataset,
    # so today this must block. If it ever exits 0, something stopped gating.
    assert finished.returncode != 0, finished.stdout + finished.stderr
    assert "BLOCKED" in finished.stdout
    assert "intake.intent_f1" in finished.stdout

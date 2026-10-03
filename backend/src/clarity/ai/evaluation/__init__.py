"""The evaluation harness: datasets, metrics, gates and a report (A05, #9).

Plan 22 section 10 sets five datasets and a launch gate for each. This package
holds the machinery; the datasets and the runners that drive the system under
test live in ``backend/tests/evaluation/``, because running the system means
reaching L4 and this is L3 (I4).

The one rule worth carrying out of here: **an unevaluable gate blocks the
release**, exactly as a regression does. See ``gates`` for why.
"""

from __future__ import annotations

from clarity.ai.evaluation.datasets import (
    DatasetInvalid,
    IntakeDataset,
    IntakeExample,
    MissingDataset,
    SafetyDataset,
    SafetyExample,
    load_intake,
    load_safety,
)
from clarity.ai.evaluation.gates import (
    GateConfigInvalid,
    GateSet,
    GateSpec,
    GateStatus,
    Release,
    Threshold,
    Verdict,
    build_release,
    evaluate_gate,
)
from clarity.ai.evaluation.metrics import (
    UNMEASURED,
    Labelled,
    Measurement,
    Observation,
    accuracy,
    by_language,
    macro_f1,
    ratio,
    slot_signature,
)
from clarity.ai.evaluation.report import LIVE, RECORDED, Report

__all__ = [
    "LIVE",
    "RECORDED",
    "UNMEASURED",
    "DatasetInvalid",
    "GateConfigInvalid",
    "GateSet",
    "GateSpec",
    "GateStatus",
    "IntakeDataset",
    "IntakeExample",
    "Labelled",
    "Measurement",
    "MissingDataset",
    "Observation",
    "Release",
    "Report",
    "SafetyDataset",
    "SafetyExample",
    "Threshold",
    "Verdict",
    "accuracy",
    "build_release",
    "by_language",
    "evaluate_gate",
    "load_intake",
    "load_safety",
    "macro_f1",
    "ratio",
    "slot_signature",
]

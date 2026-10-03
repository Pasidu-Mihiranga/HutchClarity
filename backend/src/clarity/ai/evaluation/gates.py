"""Release gates: turning measurements into a decision to ship or not (A05).

The whole module exists for one rule, which is stated here once because
everything else follows from it:

    **A gate that could not be evaluated blocks the release.**

The tempting alternative is to skip it. A skipped gate reports green, and green
is what a release reads, so a suite whose dataset failed to load, or whose
dataset covers four examples, or whose subject has not been built yet, ships as
though it had passed. That failure mode has already been found twice in this
repository: the authorization parity suite that compared Python against Python,
and the signing driver with a real service in compose that no test ever called.
Both reported green. So here an unevaluable gate is not a third state that
reviewers learn to ignore; it is a block, with the reason attached.

Thresholds come from ``config/ai/gates.yaml`` and never from this file (I10).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from clarity.ai.evaluation.metrics import UNMEASURED, Measurement, Observation


class GateConfigInvalid(ValueError):
    """``gates.yaml`` is missing, malformed, or declares a gate with no metric."""


class GateStatus(StrEnum):
    """What a gate concluded. Two of the three block a release."""

    PASS = "PASS"
    FAIL = "FAIL"
    UNEVALUABLE = "UNEVALUABLE"
    """Measured nothing, or measured too little to mean anything. Blocks."""


@dataclass(frozen=True)
class Threshold:
    """One metric and the floor it has to clear."""

    metric: str
    minimum: float
    per_language: bool


@dataclass(frozen=True)
class GateSpec:
    """One gate: its dataset, its minimum size, and its thresholds."""

    name: str
    dataset: str
    min_per_language: int
    languages: tuple[str, ...]
    thresholds: tuple[Threshold, ...]


@dataclass(frozen=True)
class GateSet:
    """Every gate, as read from config."""

    version: int
    gates: dict[str, GateSpec]

    def spec(self, name: str) -> GateSpec:
        found = self.gates.get(name)
        if found is None:
            raise GateConfigInvalid(f"no gate named {name!r} in the gate set")
        return found

    @classmethod
    def from_file(cls, path: Path) -> GateSet:
        if not path.is_file():
            raise GateConfigInvalid(f"{path} does not exist")
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as error:
            raise GateConfigInvalid(f"{path}: {error}") from error
        return cls.from_document(document, source=str(path))

    @classmethod
    def from_document(cls, document: dict[str, Any], *, source: str = "<memory>") -> GateSet:
        raw_gates = document.get("gates")
        if not isinstance(raw_gates, dict) or not raw_gates:
            raise GateConfigInvalid(f"{source}: no gates declared")

        gates: dict[str, GateSpec] = {}
        for name, spec in raw_gates.items():
            if not isinstance(spec, dict):
                raise GateConfigInvalid(f"{source}: gate {name!r} must be an object")
            raw_metrics = spec.get("metrics")
            if not isinstance(raw_metrics, dict) or not raw_metrics:
                raise GateConfigInvalid(f"{source}: gate {name!r} declares no metrics")

            thresholds: list[Threshold] = []
            for metric, body in raw_metrics.items():
                if not isinstance(body, dict) or "min" not in body:
                    raise GateConfigInvalid(
                        f"{source}: metric {metric!r} of gate {name!r} needs a 'min'"
                    )
                thresholds.append(
                    Threshold(
                        metric=str(metric),
                        minimum=float(body["min"]),
                        per_language=bool(body.get("per_language", False)),
                    )
                )

            gates[str(name)] = GateSpec(
                name=str(name),
                dataset=str(spec.get("dataset", name)),
                min_per_language=int(spec.get("min_per_language", 0)),
                languages=tuple(str(entry) for entry in spec.get("languages") or ()),
                thresholds=tuple(thresholds),
            )
        return cls(version=int(document.get("version", 1)), gates=gates)


@dataclass(frozen=True)
class Verdict:
    """One gate's conclusion about one metric, in one language or overall."""

    gate: str
    metric: str
    status: GateStatus
    required: float
    observed: float | None
    sample_size: int
    reason: str
    language: str | None = None

    @property
    def blocks_release(self) -> bool:
        return self.status is not GateStatus.PASS

    @property
    def label(self) -> str:
        """How this verdict is named in a report, log line or CI annotation."""
        scope = f" [{self.language}]" if self.language else ""
        return f"{self.gate}.{self.metric}{scope}"

    def __str__(self) -> str:
        shown = "not measured" if self.observed is None else f"{self.observed:.3f}"
        return (
            f"{self.status.value:<12} {self.label}: {shown} "
            f"(gate {self.required:.3f}, n={self.sample_size}) {self.reason}".rstrip()
        )


@dataclass(frozen=True)
class Release:
    """The ship-or-not decision over every verdict in a run."""

    verdicts: tuple[Verdict, ...]

    @property
    def blocking(self) -> tuple[Verdict, ...]:
        return tuple(verdict for verdict in self.verdicts if verdict.blocks_release)

    @property
    def blocked(self) -> bool:
        """True when anything failed or could not be evaluated.

        An empty run is blocked too: a release that measured nothing has not
        been shown to be safe, it has only not been shown to be broken.
        """
        return bool(self.blocking) or not self.verdicts

    @property
    def failing_metrics(self) -> tuple[str, ...]:
        """The names a blocked release has to report (acceptance test 1)."""
        return tuple(verdict.label for verdict in self.blocking)

    def summary(self) -> str:
        if not self.verdicts:
            return "release BLOCKED: no gate was evaluated"
        if not self.blocked:
            return f"release OK: {len(self.verdicts)} gates passed"
        named = ", ".join(self.failing_metrics)
        return (
            f"release BLOCKED: {len(self.blocking)} of {len(self.verdicts)} "
            f"gate checks did not pass ({named})"
        )


def evaluate_gate(
    spec: GateSpec,
    measurements: Mapping[str, Measurement],
    *,
    reason_when_missing: str = "",
) -> tuple[Verdict, ...]:
    """Compare one gate's thresholds against what was measured.

    A threshold with no measurement, or whose sample is smaller than the gate's
    declared minimum, returns UNEVALUABLE and therefore blocks. The observed
    value is still reported when there is one, so a dataset that is merely too
    small shows both its score and its shortfall.
    """
    verdicts: list[Verdict] = []
    for threshold in spec.thresholds:
        measurement = measurements.get(threshold.metric)
        scopes: list[str | None] = [None]
        if threshold.per_language:
            declared = list(spec.languages) or sorted(
                measurement.per_language if measurement else {}
            )
            if declared:
                scopes = list(declared)

        for scope in scopes:
            observation = _observation_for(measurement, scope)
            verdicts.append(
                _verdict(
                    spec=spec,
                    threshold=threshold,
                    language=scope,
                    observation=observation,
                    measurement_present=measurement is not None,
                    reason_when_missing=reason_when_missing,
                )
            )
    return tuple(verdicts)


def _observation_for(measurement: Measurement | None, language: str | None) -> Observation:
    if measurement is None:
        return UNMEASURED
    if language is None:
        return measurement.overall
    return measurement.per_language.get(language, UNMEASURED)


def _verdict(
    *,
    spec: GateSpec,
    threshold: Threshold,
    language: str | None,
    observation: Observation,
    measurement_present: bool,
    reason_when_missing: str,
) -> Verdict:
    def build(status: GateStatus, reason: str) -> Verdict:
        return Verdict(
            gate=spec.name,
            metric=threshold.metric,
            status=status,
            required=threshold.minimum,
            observed=observation.value,
            sample_size=observation.sample_size,
            reason=reason,
            language=language,
        )

    if not measurement_present:
        return build(
            GateStatus.UNEVALUABLE,
            reason_when_missing or f"no {spec.dataset!r} dataset was measured",
        )
    if not observation.measured:
        scope = f" for {language}" if language else ""
        return build(GateStatus.UNEVALUABLE, f"no examples{scope} in the {spec.dataset!r} dataset")
    if observation.sample_size < spec.min_per_language:
        scope = f" for {language}" if language else ""
        return build(
            GateStatus.UNEVALUABLE,
            f"dataset holds {observation.sample_size}{scope}, "
            f"below the {spec.min_per_language} this gate requires",
        )
    # mypy: `measured` has already established the value is not None.
    assert observation.value is not None
    if observation.value < threshold.minimum:
        return build(GateStatus.FAIL, "below the gate")
    return build(GateStatus.PASS, "")


def build_release(
    gates: GateSet,
    measured: Mapping[str, Mapping[str, Measurement]],
    *,
    reasons: Mapping[str, str] | None = None,
) -> Release:
    """Evaluate every gate in the set and decide whether a release may go out.

    Every gate in the set is evaluated, including the ones nothing was measured
    for. Iterating over what was measured instead would mean a gate disappears
    from the report by virtue of having no dataset, which is the exact failure
    this module exists to prevent.
    """
    notes = reasons or {}
    verdicts: list[Verdict] = []
    for name, spec in gates.gates.items():
        verdicts.extend(
            evaluate_gate(
                spec,
                measured.get(name, {}),
                reason_when_missing=notes.get(name, ""),
            )
        )
    return Release(verdicts=tuple(verdicts))


__all__ = [
    "GateConfigInvalid",
    "GateSet",
    "GateSpec",
    "GateStatus",
    "Release",
    "Threshold",
    "Verdict",
    "build_release",
    "evaluate_gate",
]

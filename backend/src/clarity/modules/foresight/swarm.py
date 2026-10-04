"""Seeded segment-persona rehearsal over aggregates only (F02)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from clarity.modules.foresight.simulation import Foresight, Prediction, Scenario, VolumeBand


@dataclass(frozen=True)
class Comparison:
    theme: str
    segment: str
    baseline: VolumeBand
    swarm: VolumeBand
    agrees: bool


@dataclass(frozen=True)
class SwarmReport:
    seed: int
    simulator_version: str
    predictions: tuple[Prediction, ...]
    comparison: tuple[Comparison, ...]
    provenance: str = "SYNTHETIC"


class PersonaSimulator(Protocol):
    def run(self, scenario: Scenario, *, seed: int) -> tuple[Prediction, ...]: ...


class SeededPersonaSimulator:
    """Deterministic persona response, never an individual subscriber model."""

    version = "seeded-persona-v1"

    def run(self, scenario: Scenario, *, seed: int) -> tuple[Prediction, ...]:
        baseline = Foresight().run(scenario).predictions
        adjusted: list[Prediction] = []
        for item in baseline:
            material = f"{seed}:{scenario.name}:{item.theme}:{item.segment}".encode()
            step = int(hashlib.sha256(material).hexdigest()[:2], 16) % 3 - 1
            band = _shift(item.band, step)
            adjusted.append(
                Prediction(
                    item.theme,
                    item.segment,
                    band,
                    item.relative_score,
                    item.suggested_mitigation,
                )
            )
        return tuple(adjusted)


class ScenarioRehearsal:
    def __init__(self, simulator: PersonaSimulator | None = None) -> None:
        self._simulator = simulator or SeededPersonaSimulator()

    def run(self, scenario: Scenario, *, seed: int = 42) -> SwarmReport:
        baseline = Foresight().run(scenario).predictions
        swarm = self._simulator.run(scenario, seed=seed)
        by_key = {(item.theme, item.segment): item for item in swarm}
        comparison = tuple(
            Comparison(
                item.theme,
                item.segment,
                item.band,
                by_key[(item.theme, item.segment)].band,
                item.band is by_key[(item.theme, item.segment)].band,
            )
            for item in baseline
        )
        return SwarmReport(seed, SeededPersonaSimulator.version, swarm, comparison)


def _shift(band: VolumeBand, step: int) -> VolumeBand:
    bands = (VolumeBand.LOW, VolumeBand.MEDIUM, VolumeBand.HIGH)
    return bands[max(0, min(2, bands.index(band) + step))]

"""Spike radar, scenario runs, and backtest gate."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean, pstdev
from typing import Any

from clarity.kernel.common import utc_now
from clarity.kernel.ids import new_id


@dataclass(slots=True)
class Scenario:
    id: str
    name: str
    persona: str = "prepaid"
    baseline: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    runs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "persona": self.persona,
            "baseline": dict(self.baseline),
            "params": dict(self.params),
            "runs": list(self.runs),
        }


class SpikeRadar:
    """Detect spikes on rolling event counts (z-score style)."""

    def __init__(self, *, z_threshold: float = 2.5) -> None:
        self._counts: dict[str, list[int]] = defaultdict(list)
        self._z_threshold = z_threshold
        self._alerts: list[dict[str, Any]] = []

    def record(self, event_type: str, count: int = 1) -> dict[str, Any] | None:
        series = self._counts[event_type]
        series.append(int(count))
        # Keep a bounded window
        if len(series) > 48:
            del series[:-48]
        if len(series) < 5:
            return None
        hist = series[:-1]
        mu = mean(hist)
        sigma = pstdev(hist) or 1.0
        z = (series[-1] - mu) / sigma
        if z < self._z_threshold:
            return None
        alert = {
            "alert_id": new_id("SPK"),
            "event_type": event_type,
            "count": series[-1],
            "z_score": round(z, 3),
            "mean": round(mu, 3),
            "detected_at": utc_now().isoformat(),
        }
        self._alerts.append(alert)
        return alert

    def snapshot(self) -> dict[str, Any]:
        return {
            "series": {k: list(v) for k, v in self._counts.items()},
            "alerts": list(self._alerts[-50:]),
            "z_threshold": self._z_threshold,
        }

    def clear(self) -> None:
        self._counts.clear()
        self._alerts.clear()


def run_scenario(scenario: Scenario, *, ticks: int = 5) -> dict[str, Any]:
    """Lite persona simulation: synthetic complaint volume under params."""
    rate = float(scenario.params.get("complaint_rate", 1.0))
    uplift = float(scenario.params.get("uplift", 0.0))
    points = []
    total = 0.0
    for t in range(ticks):
        value = rate * (1 + uplift) * (1 + 0.05 * t)
        total += value
        points.append({"t": t, "complaints": round(value, 2)})
    result = {
        "run_id": new_id("RUN"),
        "scenario_id": scenario.id,
        "persona": scenario.persona,
        "points": points,
        "total_complaints": round(total, 2),
        "ran_at": utc_now().isoformat(),
    }
    scenario.runs.append(result)
    return result


def backtest_gate(
    *,
    baseline_metric: float,
    candidate_metric: float,
    max_regression: float = 0.05,
) -> dict[str, Any]:
    """Pass if candidate does not regress more than max_regression vs baseline."""
    if baseline_metric <= 0:
        delta = 0.0 if candidate_metric == 0 else 1.0
    else:
        delta = (candidate_metric - baseline_metric) / baseline_metric
    passed = delta <= max_regression
    return {
        "passed": passed,
        "baseline": baseline_metric,
        "candidate": candidate_metric,
        "delta": round(delta, 4),
        "max_regression": max_regression,
        "gate": "backtest",
    }


class ScenarioStore:
    def __init__(self) -> None:
        self._items: dict[str, Scenario] = {}

    def put(self, scenario: Scenario) -> Scenario:
        self._items[scenario.id] = scenario
        return scenario

    def get(self, scenario_id: str) -> Scenario | None:
        return self._items.get(scenario_id)

    def all(self) -> list[Scenario]:
        return list(self._items.values())

    def clear(self) -> None:
        self._items.clear()

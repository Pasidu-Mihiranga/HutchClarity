"""Public facade for the foresight module."""

from __future__ import annotations

from typing import Any

from clarity.kernel.ids import new_id
from clarity.modules.foresight.domain.radar import (
    Scenario,
    ScenarioStore,
    SpikeRadar,
    backtest_gate,
    run_scenario,
)

_scenarios = ScenarioStore()
_radar = SpikeRadar()


def reset_foresight() -> None:
    _scenarios.clear()
    _radar.clear()


def create_scenario(
    *,
    name: str,
    persona: str = "prepaid",
    params: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scenario = Scenario(
        id=new_id("SCN"),
        name=name,
        persona=persona,
        params=dict(params or {}),
        baseline=dict(baseline or {}),
    )
    return _scenarios.put(scenario).to_dict()


def get_scenario(scenario_id: str) -> Scenario:
    scenario = _scenarios.get(scenario_id)
    if scenario is None:
        raise KeyError(scenario_id)
    return scenario


def run_scenario_by_id(scenario_id: str, *, ticks: int = 5) -> dict[str, Any]:
    scenario = get_scenario(scenario_id)
    result = run_scenario(scenario, ticks=ticks)
    # Feed radar with synthetic complaint count
    _radar.record("complaint.created", count=int(result["total_complaints"]))
    gate = None
    if scenario.baseline.get("complaints") is not None:
        gate = backtest_gate(
            baseline_metric=float(scenario.baseline["complaints"]),
            candidate_metric=float(result["total_complaints"]),
        )
        result["backtest"] = gate
    return result


def record_event_count(event_type: str, count: int = 1) -> dict[str, Any] | None:
    return _radar.record(event_type, count=count)


def radar_snapshot() -> dict[str, Any]:
    return _radar.snapshot()


__all__ = [
    "Scenario",
    "backtest_gate",
    "create_scenario",
    "get_scenario",
    "radar_snapshot",
    "record_event_count",
    "reset_foresight",
    "run_scenario_by_id",
]

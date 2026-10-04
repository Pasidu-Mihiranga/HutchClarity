"""Synthetic Foresight scenarios for a fresh world.

The rehearsal workspace reads stored scenarios. A process that has never
drafted one shows an empty list, which looks like missing data rather than
an honest empty store. These two are illustrative changes of types the
policy catalogue already knows. They are not measured HUTCH launches, and
this file does not record a calibration: there is no real launch to
backtest against.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from clarity.modules.foresight.public import ChangeType, Scenario

if TYPE_CHECKING:
    from clarity.modules.foresight.public import ForesightService

#: A date the foresight policy catalogue already covers. The run resolves
#: its parameters as of this day.
_EFFECTIVE = date(2027, 10, 1)

_ACTOR = "seed:synthetic"

SYNTHETIC_SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        scenario_id="SIM-seed-pack-retired",
        name="Synthetic rehearsal: retire a data pack",
        change_type=ChangeType.PACK_RETIRED,
        effective_date=_EFFECTIVE,
        business_context=(
            "Illustrative synthetic scenario. Not a measured HUTCH change."
        ),
    ),
    Scenario(
        scenario_id="SIM-seed-price-increase",
        name="Synthetic rehearsal: a price increase",
        change_type=ChangeType.PRICE_INCREASE,
        effective_date=_EFFECTIVE,
        business_context=(
            "Illustrative synthetic scenario. Not a measured HUTCH change."
        ),
    ),
)


def seed_synthetic_scenarios(service: ForesightService) -> int:
    """Draft the synthetic scenarios and store one rehearsal of each.

    Returns how many were drafted. A world that already has a scenario is
    left alone, so a second call does not add another family.
    """
    if service.scenarios():
        return 0
    drafted = 0
    for scenario in SYNTHETIC_SCENARIOS:
        version = service.draft(scenario, by=_ACTOR)
        run, _created = service.request_run(
            version.version_id,
            by=_ACTOR,
            idempotency_key=f"seed:{scenario.scenario_id}",
        )
        service.execute(run.run_id)
        drafted += 1
    return drafted

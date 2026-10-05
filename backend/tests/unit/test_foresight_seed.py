"""The synthetic Foresight seed drafts stored scenarios and does not repeat."""

from __future__ import annotations

from datetime import UTC, datetime

from clarity.app.foresight_seed import seed_synthetic_scenarios
from clarity.modules.foresight.catalogue import ForesightCatalogue
from clarity.modules.foresight.service import ForesightService
from clarity.platform.config.resolver import PolicyResolver
from clarity.platform.persistence import MemoryStore, MemoryUnitOfWork
from tests.conftest import POLICY_DIR

_AT = datetime(2027, 10, 1, tzinfo=UTC)


def _service() -> ForesightService:
    store = MemoryStore()
    return ForesightService(
        open_unit=lambda: MemoryUnitOfWork(store),
        catalogue=ForesightCatalogue(PolicyResolver.from_directory(POLICY_DIR)),
        clock=lambda: _AT,
    )


def test_the_seed_stores_a_rehearsal_for_each_synthetic_scenario() -> None:
    service = _service()

    drafted = seed_synthetic_scenarios(service)

    names = {version.scenario.name for version in service.scenarios()}
    assert drafted == 2
    assert names == {
        "Synthetic rehearsal: retire a data pack",
        "Synthetic rehearsal: a price increase",
    }
    assert {run.status.value for run in service.runs()} == {"succeeded"}
    assert seed_synthetic_scenarios(service) == 0
    assert len(service.scenarios()) == 2

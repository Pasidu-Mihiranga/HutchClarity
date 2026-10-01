"""Adapter selection by configuration (deck S13: "plugs into Hutch systems by config").

Only ``mock`` drivers exist. ``sandbox`` and ``production`` raise a clear error
naming what HUTCH must confirm first, so nothing in this codebase can pretend a
HUTCH interface exists.
"""

from __future__ import annotations

from clarity.integrations.base import (
    CommandPort,
    DriverMode,
    ReadPort,
)
from clarity.integrations.mocks.adapters import MockCommandAdapter, MockReadAdapter
from clarity.integrations.mocks.world import SyntheticWorld, build_demo_world
from clarity.schemas.common import EventSource

#: The eight log sources the Timeline Builder joins (plan §9.2).
ALL_SOURCES: tuple[EventSource, ...] = tuple(EventSource)


class NotYetIntegrated(NotImplementedError):
    """Raised when a non-mock driver is requested.

    HUTCH interfaces, owners and protocols are unconfirmed (Guidelines §4), so
    there is deliberately no implementation to fall back on.
    """

    def __init__(self, mode: DriverMode, source: EventSource) -> None:
        super().__init__(
            f"No {mode.value} driver for {source.value}: the HUTCH interface is not "
            f"confirmed. See docs/enterprise-plan/06-integration-tmf.md §9.3."
        )


class AdapterRegistry:
    """Holds one read port per source and the single command port."""

    def __init__(
        self,
        *,
        mode: DriverMode = DriverMode.MOCK,
        world: SyntheticWorld | None = None,
    ) -> None:
        if mode is not DriverMode.MOCK:
            raise NotYetIntegrated(mode, EventSource.CHARGING)
        self.mode = mode
        self.world = world if world is not None else build_demo_world()
        self._reads: dict[EventSource, ReadPort] = {
            source: MockReadAdapter(source, self.world) for source in ALL_SOURCES
        }
        self._command = MockCommandAdapter(self.world)

    def read_port(self, source: EventSource) -> ReadPort:
        return self._reads[source]

    def read_ports(self) -> dict[EventSource, ReadPort]:
        return dict(self._reads)

    @property
    def command_port(self) -> CommandPort:
        """Only the tool layer should hold this (plan §9.1 principle 2)."""
        return self._command

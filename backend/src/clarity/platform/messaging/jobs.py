"""In-process job queue (lite). Procrastinate wires in full."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JobQueue:
    """Minimal cron/job registry. Lite runs jobs in-process on demand."""

    jobs: dict[str, tuple[str, Callable[[], Any]]] = field(default_factory=dict)
    ran: list[str] = field(default_factory=list)

    def register(self, name: str, *, cron: str, fn: Callable[[], Any]) -> None:
        self.jobs[name] = (cron, fn)

    def run(self, name: str) -> Any:
        if name not in self.jobs:
            raise KeyError(name)
        _, fn = self.jobs[name]
        result = fn()
        self.ran.append(name)
        return result

    def run_all(self) -> list[str]:
        for name in list(self.jobs):
            self.run(name)
        return list(self.ran)

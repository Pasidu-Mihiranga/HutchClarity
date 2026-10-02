"""Injectable clock for point-in-time replay."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from clarity.kernel.common import utc_now


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return utc_now()


class _FrozenClock:
    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment


def frozen_clock(moment: datetime) -> Clock:
    return _FrozenClock(moment)

"""Adapter framework: the only way Clarity touches a HUTCH system (plan §9.1).

Four rules this module enforces:

1. **No direct calls.** Core services depend on these ports, never on a driver.
2. **Read first, write only via the tool layer.** Read and command ports are
   separate types, and the tool layer is the only caller of a command port.
3. **Swappable by config.** ``mock`` today; ``sandbox``/``production`` drivers
   plug in behind the same contract once HUTCH interfaces are confirmed.
4. **Completeness is reported, never assumed.** Every read says how well the
   source answered, so a rule can refuse to decide on partial evidence
   ("missing log -> a human, never a guess", deck S7).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import Field

from clarity.contracts.decision import ActionType
from clarity.contracts.timeline import SourceStatus, TimelineEvent
from clarity.kernel.common import ClarityModel, Completeness, EventSource


class DriverMode(StrEnum):
    """Which implementation sits behind an adapter."""

    MOCK = "mock"
    """Synthetic data in the Clarity process (the lite profile)."""
    HUTCH_SIM = "hutch-sim"
    """Synthetic data over HTTP from the separately running hutch-sim service."""
    SANDBOX = "sandbox"
    """HUTCH non-production. REQUIRES HUTCH CONFIRMATION."""
    PRODUCTION = "production"
    """Approved HUTCH production interfaces. REQUIRES HUTCH CONFIRMATION."""


class AdapterError(RuntimeError):
    """A source could not be read or a command could not be executed."""

    def __init__(self, source: EventSource, code: str, message: str) -> None:
        super().__init__(f"[{source.value}/{code}] {message}")
        self.source = source
        self.code = code


class AdapterUnavailable(AdapterError):
    """Transient failure: timeout, circuit open, upstream down.

    The case is held for evidence rather than decided on what is missing.
    """


class AmbiguousResult(AdapterError):
    """A command may or may not have applied.

    Never retried blindly: the tool layer must query status first (plan §18.4).
    """


class SourceRead(ClarityModel):
    """What one source returned for one case."""

    source: EventSource
    events: list[TimelineEvent] = Field(default_factory=list)
    completeness: Completeness = Completeness.COMPLETE
    note: str | None = None
    queried_window_days: int | None = None

    def to_status(self) -> SourceStatus:
        return SourceStatus(
            source=self.source,
            completeness=self.completeness,
            event_count=len(self.events),
            queried_window_days=self.queried_window_days,
            note=self.note,
        )


@runtime_checkable
class ReadPort(Protocol):
    """Canonical read interface. Shape is TMF-inspired (plan §10)."""

    source: EventSource

    def read(
        self, subscriber_ref: str, window_from: datetime, window_to: datetime
    ) -> SourceRead: ...


class Command(ClarityModel):
    """A requested change to a HUTCH system.

    ``idempotency_key`` is mandatory: replaying the same command must never
    move money twice (plan §14.4).
    """

    action_type: ActionType
    subscriber_ref: str
    idempotency_key: str
    amount_lkr: Any | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class CommandResult(ClarityModel):
    """Outcome of a command, including the state the receipt will quote."""

    accepted: bool
    adapter_ref: str | None = None
    before_state: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] = Field(default_factory=dict)
    replayed: bool = Field(
        default=False,
        description="True when the idempotency key matched an earlier execution.",
    )
    error_code: str | None = None


class CommandPort(ABC):
    """Write interface. Only the tool layer may hold one of these."""

    source: EventSource

    @abstractmethod
    def execute(self, command: Command) -> CommandResult:
        """Apply the command, or return a non-accepted result with a code."""

    @abstractmethod
    def status_of(self, idempotency_key: str) -> CommandResult | None:
        """Look up a previous execution. Used instead of a blind retry."""

    @abstractmethod
    def supports(self, action_type: ActionType) -> bool:
        """Whether this system can perform the action."""

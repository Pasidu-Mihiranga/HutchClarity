"""Ports that refuse to touch HUTCH, for replay and reconciliation (Phase 6).

Rebuilding state after a restore means running the same code over the same
events. That code calls adapters, and during a replay every one of those calls
would be a second real effect: a refund made twice, an SMS sent again for a case
closed last week, a credit applied to a bill already paid. The acceptance test
for Phase 6 is therefore **zero adapter calls**, and a test that merely hopes for
zero is not a test. These wrappers make it structural: a call does not quietly
succeed, it raises, and the count of attempts is on the object afterwards.

Two different seals, because replay and reconciliation need different things.

``SealedCommandPort`` refuses everything, including ``status_of``. That is what a
replay runs under: it rebuilds from records it already has and has no business
asking HUTCH anything.

``ReadOnlyCommandPort`` refuses ``execute`` and allows ``status_of``. That is what
reconciliation runs under, where asking "did you already do this?" is the entire
method, and executing is the one thing that must never follow from it.
"""

from __future__ import annotations

from clarity.contracts.decision import ActionType
from clarity.integration.ports import Command, CommandPort, CommandResult
from clarity.kernel.common import EventSource


class SideEffectRefused(RuntimeError):
    """Something tried to reach HUTCH from inside a replay.

    Raised rather than returned, and never swallowed by the wrapper, because the
    caller is code that believes it is running live. A quiet no-op would let a
    replay report success having silently skipped the step a real run would have
    taken, which is worse than failing.
    """

    def __init__(self, what: str, *, during: str) -> None:
        super().__init__(
            f"{what} was refused during {during}: a replay rebuilds state from "
            "records it already holds and must not reach a HUTCH system"
        )


class SealedCommandPort(CommandPort):
    """A command port that reaches nothing and counts what was asked of it."""

    def __init__(
        self, source: EventSource = EventSource.CHARGING, *, during: str = "replay"
    ) -> None:
        self.source = source
        self._during = during
        self.attempts: list[str] = []

    @property
    def call_count(self) -> int:
        """What the drill asserts is zero."""
        return len(self.attempts)

    def execute(self, command: Command) -> CommandResult:
        self.attempts.append(f"execute:{command.action_type.value}:{command.idempotency_key}")
        raise SideEffectRefused(f"executing {command.action_type.value}", during=self._during)

    def status_of(self, idempotency_key: str) -> CommandResult | None:
        self.attempts.append(f"status_of:{idempotency_key}")
        raise SideEffectRefused("looking up a command status", during=self._during)

    def supports(self, action_type: ActionType) -> bool:
        """Answered locally and not counted: it asks about this port, not HUTCH.

        ``False`` so that code checking whether an action is possible takes its
        unavailable branch instead of going on to call ``execute`` and raising.
        """
        return False


class ReadOnlyCommandPort(CommandPort):
    """Reconciliation's port: ``status_of`` passes through, ``execute`` never does."""

    def __init__(self, inner: CommandPort) -> None:
        self._inner = inner
        self.source = inner.source
        self.lookups: list[str] = []
        self.refused: list[str] = []

    def execute(self, command: Command) -> CommandResult:
        self.refused.append(f"{command.action_type.value}:{command.idempotency_key}")
        raise SideEffectRefused(f"executing {command.action_type.value}", during="reconciliation")

    def status_of(self, idempotency_key: str) -> CommandResult | None:
        self.lookups.append(idempotency_key)
        return self._inner.status_of(idempotency_key)

    def supports(self, action_type: ActionType) -> bool:
        return self._inner.supports(action_type)


__all__ = ["ReadOnlyCommandPort", "SealedCommandPort", "SideEffectRefused"]

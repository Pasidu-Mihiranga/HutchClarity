"""Persistence seam: units of work, repositories and their drivers (B02)."""

from __future__ import annotations

from clarity.platform.persistence.errors import (
    ConcurrentUpdate,
    PersistenceError,
    UnitOfWorkClosed,
)
from clarity.platform.persistence.memory import (
    AutocommitRepository,
    MemoryStore,
    MemoryUnitOfWork,
)
from clarity.platform.persistence.ports import Repository, UnitOfWork, UnitOfWorkFactory

__all__ = [
    "AutocommitRepository",
    "ConcurrentUpdate",
    "MemoryStore",
    "MemoryUnitOfWork",
    "PersistenceError",
    "Repository",
    "UnitOfWork",
    "UnitOfWorkClosed",
    "UnitOfWorkFactory",
]

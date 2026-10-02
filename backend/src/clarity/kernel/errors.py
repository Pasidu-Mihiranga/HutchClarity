"""Kernel errors — typed failures every layer can raise or catch."""

from __future__ import annotations


class ClarityError(Exception):
    """Base error for Hutch Clarity."""


class ValidationError(ClarityError):
    """Input failed validation."""


class NotFoundError(ClarityError):
    """Resource does not exist."""


class ConflictError(ClarityError):
    """State conflict (e.g. duplicate idempotency payload)."""


class ForbiddenError(ClarityError):
    """Authorization denied (deny by default)."""

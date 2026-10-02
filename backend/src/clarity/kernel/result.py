"""Typed Result and domain errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E", bound="ClarityError")


class ClarityError(Exception):
    code: str = "CLARITY_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class NotFoundError(ClarityError):
    code = "NOT_FOUND"


class ForbiddenError(ClarityError):
    code = "FORBIDDEN"


class ConflictError(ClarityError):
    code = "CONFLICT"


class ValidationError(ClarityError):
    code = "VALIDATION"


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T

    @property
    def ok(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    error: E

    @property
    def ok(self) -> bool:
        return False


Result = Ok[T] | Err[E]

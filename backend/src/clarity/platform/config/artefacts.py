"""Policy artefacts: the things that change without a code release.

Telecom policy changes constantly - caps, thresholds, windows, campaign
offers - and every decision must still be explainable years later. So policy is
**data with a lifecycle**, not constants in code:

1. Nothing is edited in place. A change is a new version with its own window.
2. Time is explicit. A decision is evaluated ``as_of`` the disputed event, not
   "now", so a customer is judged by the rules that applied when it happened.
3. The most specific scope wins, but never beyond a guardrail ceiling that a
   separate, more strictly approved artefact sets.

Adopted from the alternative design's chapter 19 and ADR-0011.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Self

from pydantic import Field, field_validator, model_validator

from clarity.kernel.common import ClarityModel, ensure_utc


class ChangeClass(StrEnum):
    """Risk class, which decides how much approval a change needs.

    Computed from the artefact's tags and never lowered by hand.
    """

    C0_COSMETIC = "C0"
    C1_CUSTOMER_VISIBLE = "C1"
    C2_OUTCOME_AFFECTING = "C2"
    C3_MONEY_AFFECTING = "C3"
    C4_REGULATORY = "C4"
    E_EMERGENCY = "E"

    @property
    def needs_second_approver(self) -> bool:
        return self in {
            ChangeClass.C3_MONEY_AFFECTING,
            ChangeClass.C4_REGULATORY,
            ChangeClass.E_EMERGENCY,
        }


class Tag(StrEnum):
    """What a key affects. Tags decide the change class."""

    MONEY = "money"
    REGULATORY = "regulatory"
    CUSTOMER_VISIBLE = "customer_visible"
    OUTCOME = "outcome"
    OPERATIONAL = "operational"


def class_for(tags: set[Tag]) -> ChangeClass:
    """Derive the change class from tags. Never lowered manually."""
    if Tag.REGULATORY in tags:
        return ChangeClass.C4_REGULATORY
    if Tag.MONEY in tags:
        return ChangeClass.C3_MONEY_AFFECTING
    if Tag.OUTCOME in tags:
        return ChangeClass.C2_OUTCOME_AFFECTING
    if Tag.CUSTOMER_VISIBLE in tags:
        return ChangeClass.C1_CUSTOMER_VISIBLE
    return ChangeClass.C0_COSMETIC


#: Scope dimensions, most specific first. A value on an earlier dimension wins.
SCOPE_PRECEDENCE: tuple[str, ...] = (
    "subscriber",
    "campaign",
    "rule",
    "merchant",
    "segment",
    "channel",
    "region",
)


class Scope(ClarityModel):
    """Where a value applies. An empty scope is global."""

    subscriber: str | None = None
    campaign: str | None = None
    rule: str | None = None
    merchant: str | None = None
    segment: str | None = None
    channel: str | None = None
    region: str | None = None

    @property
    def is_global(self) -> bool:
        return self.specificity == 0

    @property
    def specificity(self) -> int:
        """How many dimensions are pinned. More specific values win."""
        return sum(1 for name in SCOPE_PRECEDENCE if getattr(self, name) is not None)

    @property
    def rank(self) -> int:
        """Precedence rank: lower is more specific.

        A scope on ``subscriber`` outranks one on ``channel`` even though both
        pin a single dimension, which is what "most specific wins" means here.
        """
        for index, name in enumerate(SCOPE_PRECEDENCE):
            if getattr(self, name) is not None:
                return index
        return len(SCOPE_PRECEDENCE)

    def matches(self, context: dict[str, str | None]) -> bool:
        """True when every pinned dimension equals the one in context."""
        return all(
            context.get(name) == getattr(self, name)
            for name in SCOPE_PRECEDENCE
            if getattr(self, name) is not None
        )

    def label(self) -> str:
        pinned = [
            f"{name}={getattr(self, name)}"
            for name in SCOPE_PRECEDENCE
            if getattr(self, name) is not None
        ]
        return ", ".join(pinned) if pinned else "global"


class Guardrail(ClarityModel):
    """A ceiling no override may exceed, approved separately and more strictly."""

    min: Decimal | None = None
    max: Decimal | None = None

    def permits(self, value: Any) -> bool:
        if not isinstance(value, Decimal | int):
            return True
        number = Decimal(str(value))
        if self.min is not None and number < self.min:
            return False
        return not (self.max is not None and number > self.max)


class PolicyValue(ClarityModel):
    """One value, for one scope, over one window of real-world time."""

    value: Any
    scope: Scope = Field(default_factory=Scope)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    version: int = 1
    note: str | None = None

    @field_validator("effective_from", "effective_to")
    @classmethod
    def _as_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)

    @model_validator(mode="after")
    def _window_is_ordered(self) -> Self:
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to <= self.effective_from
        ):
            raise ValueError("effective_to must be after effective_from")
        return self

    def applies_at(self, moment: datetime) -> bool:
        if self.effective_from is not None and moment < self.effective_from:
            return False
        return not (self.effective_to is not None and moment >= self.effective_to)

    def overlaps(self, other: PolicyValue) -> bool:
        """Do two windows for the same scope collide?"""
        start_a = self.effective_from or datetime.min.replace(tzinfo=UTC)
        end_a = self.effective_to or datetime.max.replace(tzinfo=UTC)
        start_b = other.effective_from or datetime.min.replace(tzinfo=UTC)
        end_b = other.effective_to or datetime.max.replace(tzinfo=UTC)
        return start_a < end_b and start_b < end_a


class PolicyKey(ClarityModel):
    """A typed, owned, tagged setting with its values and its ceiling."""

    key: str
    kind: str = Field(default="money", description="money | number | duration | bool | string")
    owner_role: str = "cx_engineer"
    tags: set[Tag] = Field(default_factory=set)
    description: str = ""
    guardrail: Guardrail | None = None
    values: list[PolicyValue] = Field(default_factory=list)
    legal_basis: str | None = None

    @property
    def change_class(self) -> ChangeClass:
        return class_for(self.tags)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        # A value outside its own ceiling can never be published.
        if self.guardrail is not None:
            for value in self.values:
                if not self.guardrail.permits(value.value):
                    raise ValueError(
                        f"{self.key}: value {value.value} for scope "
                        f"{value.scope.label()} is outside its guardrail"
                    )

        # Two values for the same scope with overlapping windows are ambiguous,
        # so they are rejected at load rather than resolved arbitrarily.
        for index, left in enumerate(self.values):
            for right in self.values[index + 1 :]:
                if left.scope == right.scope and left.overlaps(right):
                    raise ValueError(
                        f"{self.key}: overlapping effective windows for scope {left.scope.label()}"
                    )
        return self

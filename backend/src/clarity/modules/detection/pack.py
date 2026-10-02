"""Rule packs: the data that decides causes (plan §13.1).

Rules are **data, not code**. A pack is a YAML file, versioned, hashed and
(in production) signed and published through four-eyes approval - no code
deploy. This module defines their schema and loads them.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator, model_validator

from clarity.contracts.decision import ActionType
from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import ClarityModel, EventSource, Language
from clarity.modules.detection.predicates import RuleSyntaxError, validate_condition


class RuleStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    ACTIVE = "active"
    RETIRED = "retired"


class ConfidenceAdjustment(ClarityModel):
    """A boost or penalty applied when a stated situation holds."""

    amount: float = Field(
        ge=-1,
        le=1,
        description="Positive boosts confidence, negative penalises it. Never zero.",
    )
    reason: str
    when_source_partial: EventSource | None = Field(
        default=None,
        description="Applies when this source answered partially or not at all.",
    )
    when_condition: dict[str, Any] | None = Field(
        default=None, description="Applies when this condition tree is satisfied."
    )

    @model_validator(mode="after")
    def _exactly_one_trigger(self) -> ConfidenceAdjustment:
        if self.amount == 0:
            raise ValueError("a confidence adjustment of 0 has no effect; remove it")
        triggers = [self.when_source_partial is not None, self.when_condition is not None]
        if sum(triggers) != 1:
            raise ValueError(
                "a confidence adjustment needs exactly one of when_source_partial / when_condition"
            )
        if self.when_condition is not None:
            validate_condition(self.when_condition, path="confidence.when_condition")
        return self


class MoneyEffect(ClarityModel):
    """How much money the cause accounts for.

    Either a single bound value (``value: "$c.amount"``) or the sum over a set
    of matching events. The amount always comes from evidence, never from a
    model or from customer text.
    """

    value: str | None = None
    sum: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> MoneyEffect:
        if (self.value is None) == (self.sum is None):
            raise ValueError("money_effect needs exactly one of 'value' or 'sum'")
        return self


class RulePack(ClarityModel):
    """One versioned cause rule."""

    rule_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    version: int = Field(ge=1)
    status: RuleStatus = RuleStatus.DRAFT
    owner: str
    legal_basis: str | None = None
    description: str = ""
    required_evidence: list[EventSource] = Field(
        default_factory=list,
        description="Sources that must answer completely, or the rule is indeterminate.",
    )
    conditions: dict[str, Any]
    confidence_base: float | None = Field(default=None, ge=0, le=1)
    """A literal confidence. Use ``confidence_param`` instead to make it policy.

    One of the two is required. A literal is fine for a rule whose confidence is
    a property of its logic; a parameter is for one that Risk tunes, because a
    literal here means a code release and a rule bundle to change a number
    (D5, ADR-0001).
    """
    confidence_param: str | None = Field(
        default=None,
        description="Policy key holding this rule's base confidence, resolved as_of the event.",
    )
    confidence_adjustments: list[ConfidenceAdjustment] = Field(default_factory=list)
    rules_out: list[str] = Field(
        default_factory=list,
        description="Causes this rule explicitly excludes, reported as 'ruled out'.",
    )
    category: str
    money_effect: MoneyEffect | None = None
    allowed_actions: list[ActionType] = Field(default_factory=list)
    safeguard: ActionType | None = None
    recurrence_check: str | None = None

    @model_validator(mode="after")
    def _confidence_has_exactly_one_source(self) -> RulePack:
        """A pack states its confidence once, as a literal or as a parameter.

        Refused at load rather than defaulted, because a pack with neither has
        no confidence to report and one with both has two answers that can
        disagree. A rule bundle that cannot be read is better than a rule that
        reports a number nobody chose.
        """
        has_literal = self.confidence_base is not None
        has_param = self.confidence_param is not None
        if has_literal == has_param:
            raise ValueError(
                f"{self.rule_id}@{self.version}: set exactly one of confidence_base "
                "(a literal) or confidence_param (a policy key)"
            )
        return self

    disclosed_to_customer: bool = Field(
        default=False,
        description="True when the cause is a rule the customer saw at purchase; "
        "the decision policy turns these into EXPLAIN_ONLY (deck S7).",
    )
    auto_fix_whitelisted: bool = Field(
        default=False,
        description="Only whitelisted rules may ever reach AUTO_FIX (plan §14.2).",
    )
    explanation_templates: dict[Language, str] = Field(default_factory=dict)

    @field_validator("conditions")
    @classmethod
    def _valid_conditions(cls, value: dict[str, Any]) -> dict[str, Any]:
        validate_condition(value)
        return value

    @model_validator(mode="after")
    def _safeguard_is_allowed(self) -> RulePack:
        if self.safeguard is not None and self.safeguard not in self.allowed_actions:
            raise ValueError(
                f"{self.rule_id}: safeguard {self.safeguard.value} must also be in allowed_actions"
            )
        return self

    @property
    def ref(self) -> str:
        return f"{self.rule_id}@{self.version}"

    @property
    def pack_hash(self) -> str:
        """Hash recorded on every decision, so a verdict names exact logic."""
        return hash_payload(self.model_dump(mode="json"))


class RulePackLoadError(RuleSyntaxError):
    """A rule pack file could not be loaded."""


def load_pack(path: Path) -> RulePack:
    """Load and validate one YAML rule pack."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise RulePackLoadError(f"{path.name}: invalid YAML: {error}") from error
    if not isinstance(raw, dict):
        raise RulePackLoadError(f"{path.name}: expected a mapping at the top level")
    try:
        return RulePack.model_validate(raw)
    except Exception as error:
        raise RulePackLoadError(f"{path.name}: {error}") from error


def load_packs(directory: Path, *, active_only: bool = True) -> list[RulePack]:
    """Load every pack in a directory, newest version per rule.

    Loading is deliberately strict: one malformed pack fails the whole load
    rather than silently shrinking the rule set, because a missing rule means
    a customer gets "we don't know" for a cause we can actually detect.
    """
    packs = [load_pack(path) for path in sorted(directory.glob("*.yaml"))]
    if active_only:
        packs = [p for p in packs if p.status is RuleStatus.ACTIVE]

    newest: dict[str, RulePack] = {}
    for pack in packs:
        existing = newest.get(pack.rule_id)
        if existing is None or pack.version > existing.version:
            newest[pack.rule_id] = pack
    return [newest[key] for key in sorted(newest)]

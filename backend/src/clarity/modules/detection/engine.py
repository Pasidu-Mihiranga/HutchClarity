"""Rule engine: evidence in, ranked causes out (deck S7 step 03).

Every active rule is evaluated against the snapshot - not just until one
matches - because the customer is told both what happened *and* what was ruled
out ("Ruled out: pack expiry · loan recovery", deck S7).

A rule whose required evidence is unavailable is **indeterminate**, never
"did not match". That distinction is what sends a case to a human instead of
producing a confident wrong answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from clarity.contracts.decision import CauseAssessment
from clarity.contracts.timeline import EvidenceSnapshot
from clarity.kernel.common import Completeness, EventSource, money
from clarity.modules.detection.pack import RulePack
from clarity.modules.detection.predicates import (
    Bindings,
    RuleSyntaxError,
    first_solution,
    matches_selector,
    resolve,
    solve,
)

#: Confidence floor/ceiling after adjustments.
_MIN_CONFIDENCE = Decimal("0.00")
_MAX_CONFIDENCE = Decimal("1.00")


@dataclass(frozen=True)
class RuleOutcome:
    """A rule's verdict plus the bindings that produced it (for explanations)."""

    assessment: CauseAssessment
    bindings: Bindings
    pack: RulePack

    @property
    def matched(self) -> bool:
        return self.assessment.matched


@dataclass(frozen=True)
class RuleEvaluation:
    """Everything the decision policy needs from the rule engine."""

    snapshot_hash: str
    matched: list[RuleOutcome]
    ruled_out: list[CauseAssessment]
    indeterminate: list[CauseAssessment]
    pack_refs: list[str]

    @property
    def top(self) -> RuleOutcome | None:
        return self.matched[0] if self.matched else None

    @property
    def margin(self) -> Decimal:
        """Confidence gap between the top two causes.

        A small margin means two causes are close, which the decision policy
        treats as a conflict and routes to staff (deck S7).
        """
        if len(self.matched) < 2:
            return _MAX_CONFIDENCE
        return self.matched[0].assessment.confidence - self.matched[1].assessment.confidence

    @property
    def evidence_complete(self) -> bool:
        """True when no rule was blocked by a source we could not read."""
        return not self.indeterminate


class RuleParameters(Protocol):
    """Resolves a rule's tunable values as of a moment (D5, ADR-0001).

    A protocol rather than the policy resolver itself, so the detection module
    does not depend on how policy is stored and a test can supply two values
    with different effective dates in three lines.
    """

    def confidence(self, key: str) -> Decimal:
        """The base confidence this key holds, as of the event being judged."""
        ...

    def duration(self, key: str) -> str:
        """An ISO-8601 match window this key holds, as of the event."""
        ...


class MissingRuleParameter(RuleSyntaxError):
    """A pack asked for a parameter nobody provided.

    Raised rather than defaulted. A rule that scored itself with an invented
    confidence would be reporting a number no human chose, on a path that
    decides whether money moves automatically.
    """


def _base_confidence(pack: RulePack, parameters: RuleParameters | None) -> Decimal:
    if pack.confidence_param is None:
        # The validator guarantees one of the two is set.
        return Decimal(str(pack.confidence_base))
    if parameters is None:
        raise MissingRuleParameter(
            f"{pack.rule_id}@{pack.version} takes its confidence from "
            f"{pack.confidence_param!r}, but no parameter resolver was given"
        )
    return parameters.confidence(pack.confidence_param)


def _condition_parameters(
    node: dict[str, Any], parameters: RuleParameters | None
) -> dict[str, Any]:
    """Replace policy references in a condition tree with resolved values."""

    def materialise(value: Any) -> Any:
        if isinstance(value, list):
            return [materialise(item) for item in value]
        if not isinstance(value, dict):
            return value
        resolved = {key: materialise(item) for key, item in value.items()}
        if "within_param" not in resolved:
            return resolved
        key = str(resolved.pop("within_param"))
        if parameters is None:
            raise MissingRuleParameter(
                f"condition takes its match window from {key!r}, "
                "but no parameter resolver was given"
            )
        resolved["within"] = parameters.duration(key)
        return resolved

    materialised = materialise(node)
    assert isinstance(materialised, dict)
    return materialised


class RuleEngine:
    """Evaluates a set of rule packs. Stateless and deterministic."""

    def __init__(self, packs: list[RulePack], *, parameters: RuleParameters | None = None) -> None:
        self._packs = list(packs)
        self._parameters = parameters

    @property
    def packs(self) -> list[RulePack]:
        return list(self._packs)

    def evaluate(
        self,
        snapshot: EvidenceSnapshot,
        *,
        parameters: RuleParameters | None = None,
    ) -> RuleEvaluation:
        """Find the causes in this snapshot.

        ``parameters`` resolves any ``confidence_param`` a pack declares, as of
        the moment the disputed event happened rather than now (D5). A case
        about yesterday's charge is judged by yesterday's confidence, because a
        value changed today was not the value anyone relied on then.

        Without it, a pack using ``confidence_param`` cannot be scored and says
        so, rather than quietly falling back to a number nobody chose.
        """
        parameters = parameters or self._parameters
        matched: list[RuleOutcome] = []
        ruled_out: list[CauseAssessment] = []
        indeterminate: list[CauseAssessment] = []

        for pack in self._packs:
            missing = self._missing_evidence(pack, snapshot)
            if missing:
                indeterminate.append(
                    CauseAssessment(
                        rule_id=pack.rule_id,
                        rule_version=pack.version,
                        matched=False,
                        confidence=Decimal("0"),
                        evidence_complete=False,
                        reason=(
                            "required evidence unavailable: "
                            + ", ".join(sorted(source.value for source in missing))
                        ),
                    )
                )
                continue

            conditions = _condition_parameters(pack.conditions, parameters)
            bindings = first_solution(conditions, snapshot)
            if bindings is None:
                ruled_out.append(
                    CauseAssessment(
                        rule_id=pack.rule_id,
                        rule_version=pack.version,
                        matched=False,
                        confidence=Decimal("0"),
                        category=pack.category,
                        reason=pack.description or "conditions not met",
                    )
                )
                continue

            matched.append(self._to_outcome(pack, snapshot, bindings, parameters))

        # Highest confidence first; ties broken by rule_id so ordering is stable.
        matched.sort(key=lambda o: (-o.assessment.confidence, o.assessment.rule_id))

        excluded = {rule_id for outcome in matched for rule_id in outcome.pack.rules_out}
        ruled_out = [
            assessment.model_copy(
                update={"reason": assessment.reason or "excluded by the detected cause"}
            )
            if assessment.rule_id in excluded
            else assessment
            for assessment in ruled_out
        ]

        return RuleEvaluation(
            snapshot_hash=snapshot.snapshot_hash,
            matched=matched,
            ruled_out=ruled_out,
            indeterminate=indeterminate,
            pack_refs=[pack.ref for pack in self._packs],
        )

    # -- internals --------------------------------------------------------- #

    @staticmethod
    def _missing_evidence(pack: RulePack, snapshot: EvidenceSnapshot) -> set[EventSource]:
        return {
            source
            for source in pack.required_evidence
            if snapshot.status_of(source) is not Completeness.COMPLETE
        }

    def _to_outcome(
        self,
        pack: RulePack,
        snapshot: EvidenceSnapshot,
        bindings: Bindings,
        parameters: RuleParameters | None = None,
    ) -> RuleOutcome:
        confidence = self._confidence(pack, snapshot, bindings, parameters)
        assessment = CauseAssessment(
            rule_id=pack.rule_id,
            rule_version=pack.version,
            matched=True,
            confidence=confidence,
            category=pack.category,
            money_effect_lkr=self._money_effect(pack, snapshot, bindings, parameters),
            evidence_refs=sorted(event.event_id for event in bindings.values()),
            allowed_actions=list(pack.allowed_actions),
            safeguard=pack.safeguard,
            recurrence_check=pack.recurrence_check,
        )
        return RuleOutcome(assessment=assessment, bindings=bindings, pack=pack)

    @staticmethod
    def _confidence(
        pack: RulePack,
        snapshot: EvidenceSnapshot,
        bindings: Bindings,
        parameters: RuleParameters | None = None,
    ) -> Decimal:
        value = _base_confidence(pack, parameters)
        for adjustment in pack.confidence_adjustments:
            applies = False
            if adjustment.when_source_partial is not None:
                applies = (
                    snapshot.status_of(adjustment.when_source_partial) is not Completeness.COMPLETE
                )
            elif adjustment.when_condition is not None:
                applies = (
                    next(
                        solve(
                            _condition_parameters(adjustment.when_condition, parameters),
                            snapshot,
                            bindings,
                        ),
                        None,
                    )
                    is not None
                )
            if applies:
                value += Decimal(str(adjustment.amount))
        return max(_MIN_CONFIDENCE, min(_MAX_CONFIDENCE, value))

    @staticmethod
    def _money_effect(
        pack: RulePack,
        snapshot: EvidenceSnapshot,
        bindings: Bindings,
        parameters: RuleParameters | None = None,
    ) -> Decimal | None:
        effect = pack.money_effect
        if effect is None:
            return None
        if effect.value is not None:
            resolved = resolve(effect.value, bindings)
            return None if resolved is None else money(resolved)

        assert effect.sum is not None
        total = Decimal("0")
        selector = _condition_parameters({"selector": effect.sum}, parameters)["selector"]
        for event in snapshot.events:
            if matches_selector(event, selector, bindings) and event.amount_lkr is not None:
                total += event.amount_lkr
        return money(total)

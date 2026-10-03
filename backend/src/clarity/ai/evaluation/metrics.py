"""Metric computation for the evaluation gates (A05, plan 22 section 10).

Everything here is pure: it takes gold labels beside predicted ones and returns
numbers. Nothing in this module runs the system under test, which is what keeps
the metric definition reviewable on its own and lets the same definition be
applied to a recorded run and a live one.

Two choices are worth stating.

**F1 is macro, not micro.** Micro-F1 over an intent set this skewed is close to
plain accuracy, and plain accuracy is carried by whichever intent happens to be
most common in the dataset: a classifier that answers BALANCE_DEDUCTION_QUERY to
everything would score respectably while being useless on the other eighteen
intents. Macro-F1 averages per intent, so a whole intent that never fires costs
the score the same as any other.

**A metric over nothing has no value, not a value of 1.0.** Every observation
carries the sample it was computed on, and an empty sample yields ``None``
rather than a number. Returning 1.0 for "no examples failed" is how an empty
suite comes to report perfection, so the type makes it impossible here and the
gate layer turns that ``None`` into a blocked release.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Observation:
    """One number, and the number of examples behind it.

    ``value is None`` means "not measured", which is different from zero. The
    sample size travels with the value so a reader never has to go and find out
    whether 1.00 came from four examples or four hundred.
    """

    value: float | None
    sample_size: int

    @property
    def measured(self) -> bool:
        return self.value is not None and self.sample_size > 0

    def __str__(self) -> str:
        if not self.measured:
            return f"not measured (n={self.sample_size})"
        return f"{self.value:.3f} (n={self.sample_size})"


#: An observation that was never measured, for a dataset that does not exist.
UNMEASURED = Observation(value=None, sample_size=0)


@dataclass(frozen=True)
class Measurement:
    """A named metric, overall and broken down by language."""

    metric: str
    overall: Observation
    per_language: dict[str, Observation] = field(default_factory=dict)


@dataclass(frozen=True)
class Labelled:
    """One prediction beside its gold label, tagged with its language."""

    language: str
    gold: str
    predicted: str


def macro_f1(rows: Sequence[Labelled]) -> Observation:
    """Unweighted mean F1 across every label present in gold or prediction.

    A label that appears only in the predictions still counts: inventing an
    intent that is never correct is a real failure, and averaging only over gold
    labels would hide it.
    """
    if not rows:
        return UNMEASURED

    labels = {row.gold for row in rows} | {row.predicted for row in rows}
    scores: list[float] = []
    for label in labels:
        true_positive = sum(1 for r in rows if r.gold == label and r.predicted == label)
        false_positive = sum(1 for r in rows if r.gold != label and r.predicted == label)
        false_negative = sum(1 for r in rows if r.gold == label and r.predicted != label)
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(0.0 if denominator == 0 else (2 * true_positive) / denominator)
    return Observation(value=sum(scores) / len(scores), sample_size=len(rows))


def accuracy(rows: Sequence[Labelled]) -> Observation:
    """Fraction of rows whose prediction equals its gold label."""
    if not rows:
        return UNMEASURED
    correct = sum(1 for row in rows if row.gold == row.predicted)
    return Observation(value=correct / len(rows), sample_size=len(rows))


def by_language(
    metric: str,
    rows: Sequence[Labelled],
    *,
    statistic: str = "macro_f1",
) -> Measurement:
    """Compute one statistic overall and again within each language.

    Per-language is not a presentation detail: plan 22 section 10 sets the gate
    per language, because an average across four languages passes comfortably
    while one language is unusable.
    """
    compute = macro_f1 if statistic == "macro_f1" else accuracy
    languages = sorted({row.language for row in rows})
    return Measurement(
        metric=metric,
        overall=compute(rows),
        per_language={
            language: compute([row for row in rows if row.language == language])
            for language in languages
        },
    )


def ratio(metric: str, *, held: int, total: int) -> Measurement:
    """A pass-rate metric: how many of ``total`` attempts held the property.

    Used for the safety gate, where the question is not how well something
    scored but whether anything got through: ``held`` is the number of attempts
    that executed nothing.
    """
    if total <= 0:
        return Measurement(metric=metric, overall=UNMEASURED)
    return Measurement(metric=metric, overall=Observation(value=held / total, sample_size=total))


def slot_signature(slots: dict[str, str], *, keys: Sequence[str]) -> str:
    """A canonical string for the declared slot keys, for exact comparison.

    Only the keys the example declares are compared. The extractor is free to
    return extra slots, because a spurious slot is not a wrong answer to the
    question "did it find the amount".
    """
    return "|".join(f"{key}={slots.get(key, '')}" for key in sorted(keys))


__all__ = [
    "UNMEASURED",
    "Labelled",
    "Measurement",
    "Observation",
    "accuracy",
    "by_language",
    "macro_f1",
    "ratio",
    "slot_signature",
]

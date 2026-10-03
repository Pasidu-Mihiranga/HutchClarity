"""Evaluation datasets: the labelled inputs a gate is measured on (A05).

A dataset here is a JSONL file, one example per line, because that is the format
a reviewer can read in a diff and a person can add a line to without tooling.

Two things in this module matter more than the parsing:

**A dataset knows its own size per language.** Plan 22 section 10 states a
minimum per language, and the gate needs that count to decide whether its metric
means anything. Counting happens here so no caller has to remember to.

**A missing dataset is an absence, not an empty set.** ``load_intake`` on a path
that does not exist raises. An empty dataset would give every metric a vacuous
1.00, and the whole point of the gate layer is that a suite which measured
nothing must not report a pass. The one place that tolerates absence is
``MissingDataset``, which is a declared gap carrying the reason.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class DatasetInvalid(ValueError):
    """A dataset file is missing, malformed, or an example lacks a field."""


@dataclass(frozen=True)
class IntakeExample:
    """One labelled utterance: what the customer said, and what it means.

    ``language`` is the language the example is *written in*, as declared by
    whoever wrote the line. It is not the output of a detector, which is the
    point: the detector is one of the things being measured, so it cannot also
    be the source of truth.
    """

    example_id: str
    language: str
    text: str
    intent: str
    slots: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_document(cls, document: dict[str, Any], *, source: str, line: int) -> IntakeExample:
        where = f"{source}:{line}"
        raw_slots = document.get("slots") or {}
        if not isinstance(raw_slots, dict):
            raise DatasetInvalid(f"{where}: 'slots' must be an object")

        return cls(
            example_id=_required(document, "id", where=where),
            language=_required(document, "language", where=where),
            text=_required(document, "text", where=where),
            intent=_required(document, "intent", where=where),
            slots={str(key): str(value) for key, value in raw_slots.items()},
        )


@dataclass(frozen=True)
class IntakeDataset:
    """A labelled intake set, with the per-language counts a gate needs."""

    name: str
    source: str
    examples: tuple[IntakeExample, ...]

    @property
    def languages(self) -> tuple[str, ...]:
        return tuple(sorted({example.language for example in self.examples}))

    @property
    def counts_per_language(self) -> dict[str, int]:
        return dict(Counter(example.language for example in self.examples))

    def for_language(self, language: str) -> tuple[IntakeExample, ...]:
        return tuple(example for example in self.examples if example.language == language)

    def __len__(self) -> int:
        return len(self.examples)


@dataclass(frozen=True)
class MissingDataset:
    """A dataset a gate expects, which does not exist yet, and why.

    This is the honest representation of "we have not built the thing this
    measures". It carries the issue that will bring it, so the report names the
    work rather than only reporting a gap.
    """

    name: str
    reason: str

    @property
    def counts_per_language(self) -> dict[str, int]:
        return {}

    def __len__(self) -> int:
        return 0


@dataclass(frozen=True)
class SafetyExample:
    """One safety probe: a text, and whether the guard is meant to hold it.

    The set deliberately contains both directions. A guard measured only on
    injections scores perfectly by refusing everything, which would block every
    real complaint, so the genuine half is part of the dataset rather than a
    separate courtesy check.
    """

    example_id: str
    text: str
    expect: str
    kind: str = ""

    @property
    def must_be_held(self) -> bool:
        return self.expect == "held"


@dataclass(frozen=True)
class SafetyDataset:
    """The injection set and the genuine complaints that must still get through."""

    name: str
    source: str
    examples: tuple[SafetyExample, ...]

    @property
    def held(self) -> tuple[SafetyExample, ...]:
        return tuple(example for example in self.examples if example.must_be_held)

    @property
    def allowed(self) -> tuple[SafetyExample, ...]:
        return tuple(example for example in self.examples if not example.must_be_held)

    @property
    def counts_per_language(self) -> dict[str, int]:
        return {"all": len(self.examples)}

    def __len__(self) -> int:
        return len(self.examples)


def load_intake(path: Path, *, name: str = "intake") -> IntakeDataset:
    """Read a JSONL intake set, refusing anything it cannot read exactly.

    Raises rather than skipping a bad line. A dataset that quietly drops the
    examples it could not parse reports a metric over a smaller set than the one
    on disk, and the number it reports is then not the number anyone reviewed.
    """
    examples: list[IntakeExample] = []
    seen: set[str] = set()
    for number, document in _jsonl(path):
        example = IntakeExample.from_document(document, source=str(path), line=number)
        if example.example_id in seen:
            raise DatasetInvalid(f"{path}:{number}: duplicate id {example.example_id!r}")
        seen.add(example.example_id)
        examples.append(example)

    if not examples:
        raise DatasetInvalid(f"{path}: holds no examples")
    return IntakeDataset(name=name, source=str(path), examples=tuple(examples))


def load_safety(path: Path, *, name: str = "safety") -> SafetyDataset:
    """Read the safety set: injections to hold, genuine complaints to let through."""
    examples: list[SafetyExample] = []
    seen: set[str] = set()
    for number, document in _jsonl(path):
        where = f"{path}:{number}"
        expect = _required(document, "expect", where=where)
        if expect not in {"held", "allowed"}:
            raise DatasetInvalid(f"{where}: 'expect' must be 'held' or 'allowed', not {expect!r}")
        example = SafetyExample(
            example_id=_required(document, "id", where=where),
            text=_required(document, "text", where=where),
            expect=expect,
            kind=str(document.get("kind") or ""),
        )
        if example.must_be_held and not example.kind:
            raise DatasetInvalid(
                f"{path}:{number}: an injection needs a 'kind'; the audit record carries it"
            )
        if example.example_id in seen:
            raise DatasetInvalid(f"{path}:{number}: duplicate id {example.example_id!r}")
        seen.add(example.example_id)
        examples.append(example)

    if not examples:
        raise DatasetInvalid(f"{path}: holds no examples")
    dataset = SafetyDataset(name=name, source=str(path), examples=tuple(examples))
    if not dataset.held or not dataset.allowed:
        raise DatasetInvalid(
            f"{path}: the safety set needs both injections and genuine complaints; "
            "a one-sided set is passed by a guard that refuses everything"
        )
    return dataset


def _required(document: dict[str, Any], key: str, *, where: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DatasetInvalid(f"{where}: {key!r} is required and must be a string")
    return value


def _jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    """Parse a JSONL file, refusing any line it cannot read exactly.

    Blank lines and ``//`` comments are skipped so a dataset can carry its own
    provenance header. Everything else must parse: a loader that drops the lines
    it could not read reports a metric over a set nobody reviewed.
    """
    if not path.is_file():
        raise DatasetInvalid(f"{path} does not exist")

    rows: list[tuple[int, dict[str, Any]]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        try:
            document = json.loads(line)
        except json.JSONDecodeError as error:
            raise DatasetInvalid(f"{path}:{number}: {error}") from error
        if not isinstance(document, dict):
            raise DatasetInvalid(f"{path}:{number}: each line must be a JSON object")
        rows.append((number, document))
    return rows


__all__ = [
    "DatasetInvalid",
    "IntakeDataset",
    "IntakeExample",
    "MissingDataset",
    "SafetyDataset",
    "SafetyExample",
    "load_intake",
    "load_safety",
]

"""Resolving a policy key to the value that applied at a moment in time.

Two properties matter more than anything else here:

**Point-in-time.** Resolution takes ``as_of``. A dispute about a charge from
April is judged by April's caps, even if they changed in May. Without this, a
replay silently uses today's thresholds and "what applied when it happened"
cannot be answered - which is the question a regulator asks.

**Reproducibility.** Every resolution is recorded in a
:class:`ConfigSnapshot` whose hash is stored on the decision. Re-running the
decision with that snapshot gives the same answer forever, even after the
policy has moved on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from clarity.kernel.canonical import hash_payload
from clarity.platform.config.artefacts import PolicyKey, PolicyValue


def _coerce(value: Any, kind: str) -> Any:
    """Return a value in its declared type.

    Money and fractions are written as quoted strings in YAML so they load as
    exact decimals rather than binary floats; this turns them back into the
    type the caller expects.
    """
    if kind in {"money", "number"} and isinstance(value, str | int):
        return Decimal(str(value))
    if kind == "bool" and isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "on", "1"}
    return value


class UnknownPolicyKey(KeyError):
    """A key was requested that no artefact declares.

    Deliberately an error rather than a default: a silently defaulted cap is
    how money leaks.
    """


@dataclass(frozen=True)
class Resolution:
    """One resolved value, with the evidence of how it was chosen."""

    key: str
    value: Any
    matched_scope: str
    version: int

    def as_record(self) -> dict[str, Any]:
        return {"value": self.value, "scope": self.matched_scope, "version": self.version}


@dataclass
class ConfigSnapshot:
    """Every value a decision used, frozen and hashable.

    Stored by hash on the decision, so a replay can be exact.
    """

    as_of: datetime
    resolved: dict[str, Resolution] = field(default_factory=dict)

    def record(self, resolution: Resolution) -> None:
        self.resolved[resolution.key] = resolution

    def get(self, key: str) -> Any:
        return self.resolved[key].value

    @property
    def hash(self) -> str:
        return hash_payload(
            {
                "as_of": self.as_of,
                "resolved": {k: r.as_record() for k, r in sorted(self.resolved.items())},
            }
        )

    def explain(self) -> list[str]:
        """Human-readable lines for the Desk and for audit."""
        return [
            f"{key} = {r.value} (scope: {r.matched_scope}, version {r.version})"
            for key, r in sorted(self.resolved.items())
        ]


class PolicyResolver:
    """Holds the policy keys and answers "what applied, for whom, when"."""

    def __init__(self, keys: dict[str, PolicyKey] | None = None) -> None:
        self._keys: dict[str, PolicyKey] = dict(keys or {})

    # -- loading ---------------------------------------------------------- #

    @classmethod
    def from_directory(cls, directory: Path) -> PolicyResolver:
        """Load every ``*.yaml`` policy file. A bad file fails the load."""
        keys: dict[str, PolicyKey] = {}
        for path in sorted(directory.glob("*.yaml")):
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for entry in raw.get("keys", []):
                key = PolicyKey.model_validate(entry)
                if key.key in keys:
                    raise ValueError(f"{path.name}: duplicate policy key {key.key}")
                keys[key.key] = key
        return cls(keys)

    def add(self, key: PolicyKey) -> None:
        self._keys[key.key] = key

    def keys(self) -> list[PolicyKey]:
        return [self._keys[name] for name in sorted(self._keys)]

    def key(self, name: str) -> PolicyKey:
        try:
            return self._keys[name]
        except KeyError as error:
            raise UnknownPolicyKey(name) from error

    # -- resolving -------------------------------------------------------- #

    def resolve(
        self,
        name: str,
        *,
        as_of: datetime,
        context: dict[str, str | None] | None = None,
        snapshot: ConfigSnapshot | None = None,
    ) -> Any:
        """The value that applied to this context at this moment."""
        key = self.key(name)
        where = context or {}

        candidates = [
            value for value in key.values if value.applies_at(as_of) and value.scope.matches(where)
        ]
        if not candidates:
            raise UnknownPolicyKey(f"{name}: no value applies at {as_of.isoformat()} for {where}")

        # Most specific wins; among equals, the later-starting window wins,
        # which is how a campaign override beats a standing value.
        chosen = min(
            candidates,
            key=lambda v: (
                v.scope.rank,
                -v.scope.specificity,
                -(v.effective_from.timestamp() if v.effective_from else 0),
            ),
        )

        resolution = Resolution(
            key=name,
            value=_coerce(chosen.value, key.kind),
            matched_scope=chosen.scope.label(),
            version=chosen.version,
        )
        if snapshot is not None:
            snapshot.record(resolution)
        return resolution.value

    def snapshot_for(
        self,
        names: list[str],
        *,
        as_of: datetime,
        context: dict[str, str | None] | None = None,
    ) -> ConfigSnapshot:
        """Resolve a set of keys together, for one decision."""
        snapshot = ConfigSnapshot(as_of=as_of)
        for name in names:
            self.resolve(name, as_of=as_of, context=context, snapshot=snapshot)
        return snapshot

    # -- change preview --------------------------------------------------- #

    def with_override(self, name: str, value: PolicyValue) -> PolicyResolver:
        """A copy in which ``value`` supersedes the value for its scope.

        Supersession, not addition: a new version closes the window of the one
        it replaces, exactly as publishing does (§19 principle 2, "nothing is
        edited in place"). Simply appending would leave two values covering the
        same scope and instant, which validation rightly rejects as ambiguous.

        The candidate policy never touches the live resolver, so a preview
        cannot change what production decides.
        """
        key = self.key(name)

        superseded: list[PolicyValue] = []
        for existing in key.values:
            if existing.scope != value.scope:
                superseded.append(existing)
                continue
            if value.effective_from is None:
                continue  # replaced outright
            if existing.applies_at(value.effective_from):
                superseded.append(
                    existing.model_copy(update={"effective_to": value.effective_from})
                )
            else:
                superseded.append(existing)

        candidate = key.model_copy(update={"values": [*superseded, value]})
        # Re-validate, so a candidate that breaks a guardrail or overlaps is
        # rejected here rather than after someone approves it.
        return PolicyResolver(
            {**self._keys, name: PolicyKey.model_validate(candidate.model_dump())}
        )

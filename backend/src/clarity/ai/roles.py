"""Model roles and the provider chain behind each one (A01, I12, ADR-0009).

Code asks for a **role**, never a model. `extract` means "pull fields out of
this text"; which model does that, and what happens when it is rate limited, is
a deployment decision recorded in `config/ai/models.yaml`.

The reason is not tidiness. A model ID in code means changing provider is a
release, and it means the thing that decides how a customer's complaint is read
is spread across the codebase instead of sitting in one reviewable file. I12
makes that a rule and `tests/architecture/test_no_model_ids.py` enforces it.

A chain is ordered and ends, where it can, in something that needs no provider
at all: a template or a rule. That is what makes "no model configured" a
supported state rather than an outage (ADR-0009).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml


class ModelRole(StrEnum):
    """The jobs Clarity asks a model to do. One role, one contract."""

    FAST_TEXT = "fast-text"
    """Short customer-facing wording from facts already decided."""

    EXTRACT = "extract"
    """Pull named fields out of free text. Never decides anything (I1)."""

    REASON = "reason"
    """Longer explanation over evidence, still never supplying an amount."""

    JUDGE = "judge"
    """Score another model's output in the evaluation harness."""

    GUARD = "guard"
    """Classify text as safe or not before it is used."""

    EMBED = "embed"
    """Vectors for retrieval."""

    STT = "stt"
    """Speech to text."""

    TTS = "tts"
    """Text to speech."""


#: Providers that answer without a network call or a token spend. A chain that
#: ends in one of these can always answer, which is what ADR-0009 requires.
#:
#: Two of them answer by saying they cannot. ``local-unscored`` and
#: ``local-unavailable`` return an explicit non-answer, because there is no
#: honest local way to judge an output's quality or to transcribe speech, and a
#: fabricated score or transcript is worse than an admitted gap: a release gate
#: would trust the score, and a guessed transcript is invented customer input
#: (I2). A non-answer is still an answer the caller can act on, which is what
#: lets every role terminate locally.
LOCAL_PROVIDERS = frozenset(
    {
        "template",
        "local-template",
        "local-bge",
        "local-rules",
        "local-unscored",
        "local-unavailable",
    }
)

#: Local providers whose answer is "I cannot do this", not a result.
NON_ANSWERING_PROVIDERS = frozenset({"local-unscored", "local-unavailable"})


class ModelConfigInvalid(ValueError):
    """``models.yaml`` is missing, malformed, or names an unknown role."""


@dataclass(frozen=True)
class ProviderChoice:
    """One step in a role's chain: who to ask, and with which model."""

    provider: str
    model: str

    @property
    def is_local(self) -> bool:
        return self.provider in LOCAL_PROVIDERS


@dataclass(frozen=True)
class RoleRouting:
    """The ordered chain for one role: primary first, then each fallback."""

    role: ModelRole
    chain: tuple[ProviderChoice, ...]

    @property
    def primary(self) -> ProviderChoice:
        return self.chain[0]

    @property
    def ends_locally(self) -> bool:
        """Whether this chain can answer with no provider configured."""
        return bool(self.chain) and self.chain[-1].is_local

    @property
    def local_answer_is_a_refusal(self) -> bool:
        """Whether this role's local end admits it cannot do the job."""
        return bool(self.chain) and self.chain[-1].provider in NON_ANSWERING_PROVIDERS


@dataclass(frozen=True)
class ModelCatalogue:
    """Every role's routing, plus the defaults, as read from config."""

    roles: dict[ModelRole, RoleRouting]
    prefer_templates: bool = True
    mask_pii_before_send: bool = True
    cassette_dir: str = "cassettes"

    def routing(self, role: ModelRole) -> RoleRouting:
        found = self.roles.get(role)
        if found is None:
            raise ModelConfigInvalid(
                f"no routing for the {role.value!r} role; add it to config/ai/models.yaml"
            )
        return found

    @classmethod
    def from_file(cls, path: Path) -> ModelCatalogue:
        if not path.is_file():
            raise ModelConfigInvalid(f"{path} does not exist")
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as error:
            raise ModelConfigInvalid(f"{path}: {error}") from error
        return cls.from_document(document, source=str(path))

    @classmethod
    def from_document(cls, document: dict[str, Any], *, source: str = "<memory>") -> ModelCatalogue:
        raw_roles = document.get("roles")
        if not isinstance(raw_roles, dict) or not raw_roles:
            raise ModelConfigInvalid(f"{source}: no roles declared")

        routings: dict[ModelRole, RoleRouting] = {}
        for name, spec in raw_roles.items():
            try:
                role = ModelRole(name)
            except ValueError as error:
                raise ModelConfigInvalid(
                    f"{source}: {name!r} is not a model role; "
                    f"known roles are {', '.join(r.value for r in ModelRole)}"
                ) from error
            routings[role] = RoleRouting(role=role, chain=_chain_of(spec, role, source))

        defaults = document.get("defaults") or {}
        return cls(
            roles=routings,
            prefer_templates=bool(defaults.get("prefer_templates", True)),
            mask_pii_before_send=bool(defaults.get("mask_pii_before_send", True)),
            cassette_dir=str(defaults.get("record_replay_cassette_dir", "cassettes")),
        )


def _chain_of(spec: Any, role: ModelRole, source: str) -> tuple[ProviderChoice, ...]:
    if not isinstance(spec, dict) or "primary" not in spec:
        raise ModelConfigInvalid(f"{source}: the {role.value!r} role needs a primary provider")
    steps = [_choice_of(spec["primary"], role, source)]
    for fallback in spec.get("fallback") or []:
        steps.append(_choice_of(fallback, role, source))
    return tuple(steps)


def _choice_of(spec: Any, role: ModelRole, source: str) -> ProviderChoice:
    if not isinstance(spec, dict) or "provider" not in spec or "model" not in spec:
        raise ModelConfigInvalid(
            f"{source}: every step of the {role.value!r} chain needs a provider and a model"
        )
    return ProviderChoice(provider=str(spec["provider"]), model=str(spec["model"]))


__all__ = [
    "LOCAL_PROVIDERS",
    "NON_ANSWERING_PROVIDERS",
    "ModelCatalogue",
    "ModelConfigInvalid",
    "ModelRole",
    "ProviderChoice",
    "RoleRouting",
]

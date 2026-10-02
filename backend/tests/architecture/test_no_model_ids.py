"""No model ID appears outside config (issue #2, A01; I12).

A model ID in code means two things, both bad. Changing provider becomes a
release rather than a configuration change, and the decision about which model
reads a customer's complaint ends up spread across the codebase instead of in
one reviewable file that Risk can look at.

So the IDs live in ``config/ai/models.yaml`` and code asks for a role. This test
reads the real config, takes every model ID it finds, and looks for them in the
source. It cannot be fooled by a new provider being added, because the list of
things to search for comes from the config itself.
"""

from __future__ import annotations

from pathlib import Path

import clarity
from clarity.ai.roles import ModelCatalogue, ModelRole

SRC = Path(clarity.__file__).parent
CONFIG = SRC.parents[2] / "config" / "ai" / "models.yaml"

#: Files allowed to name a model, because naming them is their job.
ALLOWED = {
    # The loader's docstrings quote config examples.
    "ai/roles.py",
}

#: Local provider names are not model IDs; they are the names of code in this
#: repository, which has to refer to itself.
LOCAL_MODEL_NAMES = frozenset(
    {
        "local-template",
        "keyword-intake",
        "no-judgement",
        "no-transcription",
        "local-guard-rules",
        "local-tts-stub",
    }
)


def _configured_model_ids() -> set[str]:
    catalogue = ModelCatalogue.from_file(CONFIG)
    found: set[str] = set()
    for role in ModelRole:
        for step in catalogue.routing(role).chain:
            if step.model not in LOCAL_MODEL_NAMES:
                found.add(step.model)
    return found


def test_the_config_actually_names_some_models() -> None:
    """Guard against the test passing because it found nothing to look for."""
    ids = _configured_model_ids()
    assert len(ids) >= 5, f"only {len(ids)} model IDs in the config; is it being read?"


def test_no_model_id_appears_in_the_source() -> None:
    ids = _configured_model_ids()
    offenders: dict[str, list[str]] = {}

    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = str(path.relative_to(SRC))
        if relative in ALLOWED:
            continue
        text = path.read_text(encoding="utf-8")
        named = sorted(model for model in ids if model in text)
        if named:
            offenders[relative] = named

    assert offenders == {}, (
        "these files name a model ID; ask for a role instead and let "
        "config/ai/models.yaml decide which model serves it (I12)"
    )


def test_every_role_can_answer_without_a_provider() -> None:
    """A01 acceptance 3's companion: the chains are what make tier 1 possible.

    Every role ends in a local provider, so "no model configured" is a supported
    state rather than an outage (ADR-0009). Two of those local ends report that
    they cannot do the job rather than inventing a result, which is still an
    answer the caller can act on.
    """
    catalogue = ModelCatalogue.from_file(CONFIG)
    cannot_answer = [role.value for role in ModelRole if not catalogue.routing(role).ends_locally]
    assert cannot_answer == [], (
        f"these roles have no answer with no provider configured: {cannot_answer}. "
        "Give each chain a local last step."
    )


def test_the_roles_that_refuse_locally_are_the_expected_two() -> None:
    """Pinned, so a third role cannot quietly start returning a non-answer.

    There is no honest local way to judge an output or transcribe speech. Any
    other role acquiring a refusing local end would mean a real capability was
    swapped for an admitted gap, which should be a deliberate decision.
    """
    catalogue = ModelCatalogue.from_file(CONFIG)
    refusing = sorted(
        role.value for role in ModelRole if catalogue.routing(role).local_answer_is_a_refusal
    )
    assert refusing == ["judge", "stt"]

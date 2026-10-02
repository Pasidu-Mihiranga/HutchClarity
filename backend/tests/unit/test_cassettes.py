"""Recorded responses, and no live model calls (issue #3, A02).

The acceptance case is a test that uses the ``fast-text`` role reading its
answer from a cassette and touching no network. The second half matters as much:
the suite has to be *unable* to make a live call, or a missing recording quietly
becomes one and the build starts depending on somebody's free-tier quota.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import httpx
import pytest

from clarity.ai.cassettes import (
    Cassette,
    CassetteLibrary,
    CassetteMissing,
    RecordedProvider,
    cassette_key,
)
from clarity.ai.gateway import Prompt, Usage
from clarity.ai.roles import ModelCatalogue, ModelRole
from clarity.ai.routing import RoleRouter
from clarity.kernel.common import Language
from tests.support.no_network import LiveCallAttempted

FAST_TEXT = ModelRole.FAST_TEXT.value


def a_prompt(text: str = "why was I charged 49") -> Prompt:
    return Prompt(
        system="explain the charge",
        facts={"outcome": "ONE_TAP_FIX", "amount_lkr": "49.00"},
        user_masked=text,
        language=Language.EN,
    )


class _Live:
    """Stands in for a real provider: records that it was called."""

    name = "live"

    def __init__(self, text: str = "a model wrote this") -> None:
        self.text = text
        self.calls = 0

    def complete(self, prompt: Prompt) -> tuple[str, Usage]:
        self.calls += 1
        return self.text, Usage(input_tokens=11, output_tokens=7)


@pytest.fixture
def library(tmp_path: Path) -> CassetteLibrary:
    return CassetteLibrary(tmp_path / "cassettes")


# -- acceptance 1: the fast-text role replays and makes no network call ----- #


def test_a_fast_text_test_reads_the_cassette_and_calls_nothing(
    library: CassetteLibrary,
) -> None:
    prompt = a_prompt()
    key = cassette_key(role=FAST_TEXT, provider="groq", model="llama-3.3-70b", prompt=prompt)
    library.put(
        Cassette(
            key=key,
            role=FAST_TEXT,
            provider="groq",
            model="llama-3.3-70b",
            prompt={"user_masked": prompt.user_masked},
            response="LKR 49.00 was returned to your balance.",
            usage={"input_tokens": 11, "output_tokens": 7},
            recorded_at="2026-10-02T00:00:00+00:00",
        )
    )
    live = _Live()
    replaying = RecordedProvider(
        live, library=library, role=FAST_TEXT, provider="groq", model="llama-3.3-70b"
    )

    text, usage = replaying.complete(prompt)

    assert text == "LKR 49.00 was returned to your balance."
    assert usage.total == 18, "the recorded cost is replayed too"
    assert live.calls == 0, "the wrapped provider must not be touched in replay"


def test_the_fast_text_role_replays_through_the_router(library: CassetteLibrary) -> None:
    """The same thing through the real routing path, as a caller would see it."""
    catalogue = ModelCatalogue.from_document(
        {
            "roles": {
                FAST_TEXT: {
                    "primary": {"provider": "groq", "model": "llama-3.3-70b"},
                    "fallback": [{"provider": "template", "model": "local-template"}],
                }
            }
        }
    )
    prompt = a_prompt()
    key = cassette_key(role=FAST_TEXT, provider="groq", model="llama-3.3-70b", prompt=prompt)
    library.put(
        Cassette(
            key=key,
            role=FAST_TEXT,
            provider="groq",
            model="llama-3.3-70b",
            prompt={"user_masked": prompt.user_masked},
            response="recorded answer",
            usage={"input_tokens": 1, "output_tokens": 1},
            recorded_at="2026-10-02T00:00:00+00:00",
        )
    )
    live = _Live()
    router = RoleRouter(
        catalogue,
        providers={
            "groq": RecordedProvider(
                live, library=library, role=FAST_TEXT, provider="groq", model="llama-3.3-70b"
            )
        },
    )

    answer = router.invoke(ModelRole.FAST_TEXT, prompt)

    assert answer.text == "recorded answer"
    assert live.calls == 0


# -- a missing cassette is an error, never a live call --------------------- #


def test_a_missing_cassette_refuses_rather_than_calling_the_provider(
    library: CassetteLibrary,
) -> None:
    """The whole point. Falling through to the network is what A02 prevents."""
    live = _Live()
    replaying = RecordedProvider(live, library=library, role=FAST_TEXT, provider="groq", model="m")

    with pytest.raises(CassetteMissing, match="CLARITY_RECORD_CASSETTES"):
        replaying.complete(a_prompt())

    assert live.calls == 0


def test_recording_writes_a_reviewable_file(tmp_path: Path) -> None:
    """A cassette is read in a diff, so it holds the prompt as well as the answer."""
    library = CassetteLibrary(tmp_path / "cassettes", recording=True)
    live = _Live("recorded once")
    recorder = RecordedProvider(live, library=library, role=FAST_TEXT, provider="groq", model="m")
    prompt = a_prompt()

    text, _ = recorder.complete(prompt)
    assert text == "recorded once"
    assert live.calls == 1

    key = cassette_key(role=FAST_TEXT, provider="groq", model="m", prompt=prompt)
    written = library.path_for(FAST_TEXT, key)
    document = json.loads(written.read_text(encoding="utf-8"))

    assert document["response"] == "recorded once"
    assert document["prompt"]["user_masked"] == prompt.user_masked, "the ask is reviewable"
    assert document["role"] == FAST_TEXT
    assert document["usage"] == {"input_tokens": 11, "output_tokens": 7}
    assert written.read_text(encoding="utf-8").endswith("\n"), "diffs cleanly"

    # Replaying afterwards does not call the provider again.
    replaying = RecordedProvider(
        live,
        library=CassetteLibrary(tmp_path / "cassettes"),
        role=FAST_TEXT,
        provider="groq",
        model="m",
    )
    replaying.complete(prompt)
    assert live.calls == 1


def test_a_reworded_prompt_misses_its_old_cassette(library: CassetteLibrary) -> None:
    """The worst passing test would be an answer replayed for a different question."""
    first = cassette_key(role=FAST_TEXT, provider="g", model="m", prompt=a_prompt("why 49"))
    second = cassette_key(role=FAST_TEXT, provider="g", model="m", prompt=a_prompt("why 99"))
    assert first != second


def test_the_key_changes_with_the_model(library: CassetteLibrary) -> None:
    """A different model can answer differently, so it gets its own recording."""
    prompt = a_prompt()
    assert cassette_key(role=FAST_TEXT, provider="g", model="a", prompt=prompt) != cassette_key(
        role=FAST_TEXT, provider="g", model="b", prompt=prompt
    )


# -- the suite cannot reach a provider ------------------------------------- #


def test_an_outbound_connection_is_refused() -> None:
    """The guard is autouse, so this is already in force for every test."""
    with pytest.raises(LiveCallAttempted, match=r"api\.groq\.com"):
        httpx.Client(timeout=1).get("https://api.groq.com/openai/v1/models")


def test_a_raw_socket_to_the_internet_is_refused() -> None:
    """Checked at the socket layer, so it holds for any client library."""
    with pytest.raises(LiveCallAttempted):
        socket.create_connection(("example.com", 443), timeout=1)


def test_loopback_is_still_allowed() -> None:
    """The suite drives the app and the full lane's containers over localhost."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        socket.create_connection(listener.getsockname(), timeout=2).close()
    finally:
        listener.close()


# -- the committed cassettes are clean ------------------------------------- #


def test_no_committed_cassette_contains_a_raw_number() -> None:
    """I13: a cassette holds the masked prompt, so it cannot be where PII leaks.

    Masking happens in the gateway before a cassette is written, which means a
    number appearing here would mean the masking was bypassed.
    """
    import clarity

    directory = Path(clarity.__file__).parents[3] / "cassettes"
    offenders: list[str] = []
    for cassette in CassetteLibrary(directory).all_cassettes():
        rendered = json.dumps(cassette.as_document())
        if "+947" in rendered or "07" in rendered.replace("2026-10-07", ""):
            offenders.append(cassette.key)
    assert offenders == [], f"these cassettes may contain a raw number: {offenders}"

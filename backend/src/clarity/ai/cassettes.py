"""Recorded model responses, replayed in tests (A02, plan 19 section 4.3).

A test that calls a live model is three problems at once: it costs quota that a
customer's request needs, it fails when a free tier is rate limited, and it is
not a test, because the thing it asserts can change without the code changing.

So a response is recorded once and replayed afterwards. A cassette is a plain
JSON file holding the prompt that produced it and the answer that came back, so
it reads in a diff and is reviewed like code: a changed cassette is a changed
expectation about what a model says, and that deserves a human looking at it.

**What is in a cassette.** The prompt stored is the masked one, which is the
only text that ever reaches a provider (I13). Masking happens in the gateway
before this sees anything, so a cassette cannot be the place a phone number
leaks, and ``tests/unit/test_cassettes.py`` checks the recorded files for that.

**Recording is explicit.** Replay is the default and a missing cassette is an
error, not a silent live call. Recording happens only when someone sets
``CLARITY_RECORD_CASSETTES``, which is the one moment a real provider is wanted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from clarity.ai.gateway import Prompt, Usage
from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import utc_now


class CassetteMissing(RuntimeError):
    """No recording for this prompt, and recording is off.

    Deliberately an error. The alternative is falling through to a live call,
    which is the thing A02 exists to prevent: a test suite that quietly reaches
    the network is one rate limit away from a red build nobody caused.
    """

    def __init__(self, key: str, path: Path) -> None:
        super().__init__(
            f"no cassette for {key} at {path}. Record it once with "
            "CLARITY_RECORD_CASSETTES=1 and a provider configured, then commit "
            "the file so the suite needs no network."
        )
        self.key = key
        self.path = path


@dataclass(frozen=True)
class Cassette:
    """One recorded exchange."""

    key: str
    role: str
    provider: str
    model: str
    prompt: dict[str, Any]
    response: str
    usage: dict[str, int]
    recorded_at: str

    def as_document(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "role": self.role,
            "provider": self.provider,
            "model": self.model,
            # Kept so a reviewer can see what was asked, not only what came
            # back. A cassette whose answer no longer fits its prompt is the
            # interesting case, and that is invisible without this.
            "prompt": self.prompt,
            "response": self.response,
            "usage": self.usage,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> Cassette:
        return cls(
            key=str(document["key"]),
            role=str(document.get("role", "")),
            provider=str(document.get("provider", "")),
            model=str(document.get("model", "")),
            prompt=dict(document.get("prompt") or {}),
            response=str(document["response"]),
            usage={k: int(v) for k, v in (document.get("usage") or {}).items()},
            recorded_at=str(document.get("recorded_at", "")),
        )


def cassette_key(*, role: str, provider: str, model: str, prompt: Prompt) -> str:
    """A stable name for one exchange.

    Everything that could change the answer is in the key: the role, the
    provider, the model and the whole prompt. So a reworded prompt misses its
    old cassette rather than quietly replaying an answer to a different
    question, which would be the worst kind of passing test.
    """
    return hash_payload(
        {
            "role": role,
            "provider": provider,
            "model": model,
            "system": prompt.system,
            "facts": {str(k): str(v) for k, v in sorted(prompt.facts.items())},
            "user_masked": prompt.user_masked,
            "language": prompt.language.value,
        }
    )[:32]


class CassetteLibrary:
    """Reads and writes the recorded responses under one directory."""

    def __init__(self, directory: Path, *, recording: bool = False) -> None:
        self._directory = directory
        self._recording = recording

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def directory(self) -> Path:
        return self._directory

    def path_for(self, role: str, key: str) -> Path:
        """One directory per role, so a reviewer can see what each role asks."""
        return self._directory / role / f"{key}.json"

    def get(self, role: str, key: str) -> Cassette | None:
        path = self.path_for(role, key)
        if not path.is_file():
            return None
        return Cassette.from_document(json.loads(path.read_text(encoding="utf-8")))

    def put(self, cassette: Cassette) -> Path:
        path = self.path_for(cassette.role, cassette.key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Indented and newline-terminated: a cassette is reviewed in a diff.
        path.write_text(
            json.dumps(cassette.as_document(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    def all_cassettes(self) -> list[Cassette]:
        if not self._directory.is_dir():
            return []
        return [
            Cassette.from_document(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self._directory.rglob("*.json"))
        ]


class RecordedProvider:
    """Wraps a provider so tests replay instead of calling it.

    In replay mode the wrapped provider is never touched, so a test cannot reach
    the network even if one is configured. In recording mode the call goes
    through once and the answer is written down.
    """

    def __init__(
        self,
        inner: Any,
        *,
        library: CassetteLibrary,
        role: str,
        provider: str,
        model: str,
        now: Any = utc_now,
    ) -> None:
        self._inner = inner
        self._library = library
        self._role = role
        self._provider = provider
        self._model = model
        self._now = now
        # A plain attribute, not a property: the ModelProvider protocol wants
        # `name` settable, and a read-only property does not satisfy it.
        self.name = f"cassette:{provider}"

    def complete(self, prompt: Prompt) -> tuple[str, Usage]:
        key = cassette_key(
            role=self._role, provider=self._provider, model=self._model, prompt=prompt
        )
        found = self._library.get(self._role, key)
        if found is not None:
            usage = found.usage
            return found.response, Usage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
            )

        if not self._library.recording:
            raise CassetteMissing(key, self._library.path_for(self._role, key))

        if self._inner is None:
            raise CassetteMissing(key, self._library.path_for(self._role, key))

        text, usage_out = self._inner.complete(prompt)
        moment: datetime = self._now()
        self._library.put(
            Cassette(
                key=key,
                role=self._role,
                provider=self._provider,
                model=self._model,
                prompt={
                    "system": prompt.system,
                    "facts": {str(k): str(v) for k, v in sorted(prompt.facts.items())},
                    "user_masked": prompt.user_masked,
                    "language": prompt.language.value,
                },
                response=text,
                usage={
                    "input_tokens": usage_out.input_tokens,
                    "output_tokens": usage_out.output_tokens,
                },
                recorded_at=moment.isoformat(),
            )
        )
        return text, usage_out


__all__ = [
    "Cassette",
    "CassetteLibrary",
    "CassetteMissing",
    "RecordedProvider",
    "cassette_key",
]

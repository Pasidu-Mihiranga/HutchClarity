"""Vertex answers text. No live call: the HTTP client and the credential are fakes."""

from __future__ import annotations

from typing import Any

import httpx

from clarity.ai.gateway import Prompt
from clarity.ai.providers import ProviderRateLimited, VertexAIProvider
from clarity.kernel.common import Language


class _Creds:
    valid = True
    token: str | None = "ya29-test"

    def refresh(self, _request: object) -> None:
        raise AssertionError("a valid credential must not refresh")


def _response(status: int, body: dict[str, Any]) -> httpx.Response:
    response = httpx.Response(status, json=body)
    response.request = httpx.Request("POST", "https://aiplatform.googleapis.com/v1")
    return response


class _Client:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.url = ""
        self.headers: dict[str, str] = {}
        self.body: dict[str, Any] = {}

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any]) -> httpx.Response:
        self.url = url
        self.headers = headers
        self.body = json
        return self.response


def _prompt() -> Prompt:
    return Prompt(
        system="Restate the facts.",
        facts={"amount_lkr": "100.00"},
        user_masked="why was I charged",
        language=Language.EN,
    )


def test_complete_posts_the_masked_prompt_and_reads_usage() -> None:
    client = _Client(
        _response(
            200,
            {
                "candidates": [{"content": {"parts": [{"text": "The charge was LKR 100.00."}]}}],
                "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 6},
            },
        )
    )
    provider = VertexAIProvider(
        project="agentrix-500015",
        location="global",
        model="gemini-2.5-flash",
        credentials=_Creds(),  # type: ignore[arg-type]
        client=client,  # type: ignore[arg-type]
    )
    text, usage = provider.complete(_prompt())
    assert text == "The charge was LKR 100.00."
    assert usage.input_tokens == 4
    assert usage.output_tokens == 6
    assert client.url.endswith(
        "/projects/agentrix-500015/locations/global/publishers/google/models/"
        "gemini-2.5-flash:generateContent"
    )
    assert client.headers["Authorization"] == "Bearer ya29-test"
    assert "100.00" in client.body["contents"][0]["parts"][0]["text"]


def test_a_rate_limit_is_its_own_error() -> None:
    provider = VertexAIProvider(
        project="p",
        location="global",
        model="gemini-2.5-flash",
        credentials=_Creds(),  # type: ignore[arg-type]
        client=_Client(_response(429, {})),  # type: ignore[arg-type]
    )
    try:
        provider.complete(_prompt())
    except ProviderRateLimited:
        return
    raise AssertionError("expected ProviderRateLimited")

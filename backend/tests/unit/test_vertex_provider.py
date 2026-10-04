"""Vertex AI provider contract tests use no network or live credentials."""

from __future__ import annotations

import httpx

from clarity.ai.gateway import Prompt
from clarity.ai.providers import VertexAIProvider
from clarity.kernel.common import Language


class _Credentials:
    valid = True
    token = "test-access-token"

    def refresh(self, request: object) -> None:
        raise AssertionError("valid test credentials must not refresh")


def test_vertex_sends_masked_context_and_reports_usage() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-access-token"
        assert "/projects/synthetic-project/locations/global/" in str(request.url)
        body = request.read().decode()
        assert "SUB-***" in body
        assert "0771234567" not in body
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "Approved explanation"}]}}],
                "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 4},
            },
        )

    provider = VertexAIProvider(
        project="synthetic-project",
        location="global",
        model="gemini-test",
        credentials=_Credentials(),  # type: ignore[arg-type]
        client=httpx.Client(transport=httpx.MockTransport(answer)),
    )
    text, usage = provider.complete(
        Prompt(
            system="Restate verified facts only.",
            facts={"subscriber_ref": "SUB-***"},
            user_masked="Please explain for SUB-***",
            language=Language.EN,
        )
    )

    assert text == "Approved explanation"
    assert usage.input_tokens == 12
    assert usage.output_tokens == 4

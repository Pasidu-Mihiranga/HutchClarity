"""Stateless receipt-rendering job entry point.

The request and response are JSON-safe, so this handler can run in a worker,
Knative service or function runtime. The renderer itself blocks all network
requests and consumes only the signed receipt document in the request.
"""

from __future__ import annotations

import base64

from clarity.contracts.receipt import TrustReceipt
from clarity.kernel.common import ClarityModel, Language
from clarity.modules.receipts.render import RenderFormat, render


class RenderJobRequest(ClarityModel):
    receipt: TrustReceipt
    language: Language = Language.EN
    format: RenderFormat = RenderFormat.PNG


class RenderJobResult(ClarityModel):
    content_base64: str
    content_type: str
    language: Language


def handle_render_job(document: dict[str, object]) -> dict[str, object]:
    """Render one JSON request and return a JSON-safe response."""
    request = RenderJobRequest.model_validate(document)
    rendered = render(
        request.receipt,
        language=request.language,
        format=request.format,
    )
    result = RenderJobResult(
        content_base64=base64.b64encode(rendered.content).decode("ascii"),
        content_type=("image/png" if rendered.format is RenderFormat.PNG else "application/pdf"),
        language=rendered.language,
    )
    return result.model_dump(mode="json")


__all__ = ["RenderJobRequest", "RenderJobResult", "handle_render_job"]

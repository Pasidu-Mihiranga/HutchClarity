"""The `clarity-mcp` entry point: ``uvicorn clarity.entrypoints.mcp_asgi:app``.

A second deployable beside `clarity-api` (ADR-0018). It serves MCP over
Streamable HTTP at ``/mcp`` and has no database of its own.

This module asks the container for what it needs and makes no profile
decision of its own, so the composition root stays the only place that reads
the runtime profile (I20).
"""

from __future__ import annotations

from clarity.app.container import Clarity
from clarity.interfaces.mcp.app import build_mcp_app
from clarity.interfaces.mcp.server import ClarityMCPServer


def create_app() -> object:
    """Build the MCP ASGI app from configuration."""
    clarity = Clarity()
    settings = clarity.settings
    hosts = [host.strip() for host in settings.mcp_allowed_hosts.split(",") if host.strip()]
    issuer = settings.keycloak_issuer or settings.mcp_resource_url
    return build_mcp_app(
        ClarityMCPServer(clarity.mcp_view),
        clarity.token_verifier,
        issuer_url=issuer,
        resource_url=settings.mcp_resource_url,
        allowed_hosts=hosts or None,
    )


app = create_app()

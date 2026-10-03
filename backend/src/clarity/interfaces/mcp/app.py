"""The `clarity-mcp` deployable: MCP over Streamable HTTP (A04, ADR-0018).

This module is the transport and nothing more. Every authorization decision
still belongs to :class:`~clarity.interfaces.mcp.server.ClarityMCPServer`, which
was already tested as the chokepoint, so putting a network in front of it adds
a way in and no new way to be allowed.

Three properties are worth stating because they are easy to lose:

**The principal is derived per call, from the token.** Nothing about the caller
is remembered between calls and nothing about it comes from the arguments. The
transport is stateless (ADR-0018), which is not only a scaling choice: there is
no session for a later request to inherit a wider profile from.

**Every tool has an explicit signature.** The JSON schema a model is shown is
generated from these wrappers, so the tool surface is readable in one place and
reviewable in a diff. In particular ``propose_action`` takes an action type and
no amount, which is the shape of invariant I1 in the published contract rather
than only in the handler.

**Denials cross the boundary as codes.** A refusal becomes a typed MCP error
with a stable code and a safe message. No stack trace and no internal detail
reaches the model.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from clarity.interfaces.mcp.auth import TokenRejected, principal_from_claims
from clarity.interfaces.mcp.resource_server import ClarityResourceServer
from clarity.interfaces.mcp.server import ClarityMCPServer, Principal, ToolDenied
from clarity.modules.iam.public import TokenVerifier as ClarityTokenVerifier

#: MCP Apps UI cards (plan 07 section 10.7). Rendered sandboxed by the host.
WHY_CARD_URI = "ui://clarity/why-card"
RECEIPT_URI = "ui://clarity/receipt"


def _caller() -> Principal:
    """The principal for the call in flight, from its bearer token.

    Raises rather than returning a default. A tool that cannot tell who is
    calling must not run (I9).
    """
    access = get_access_token()
    if access is None:
        raise _denied("NOT_AUTHENTICATED", "this call carried no verified token")
    try:
        return principal_from_claims(access.claims or {})
    except TokenRejected as rejected:
        raise _denied(rejected.code, str(rejected)) from rejected


def _denied(code: str, detail: str) -> ToolError:
    """A refusal the model can read, with nothing internal in it.

    ``ToolError`` is the SDK's "failure you anticipated": the call comes back
    with ``is_error`` set and this message in the content, and the server logs
    it at INFO with no traceback. That is what a denial should be. Any other
    exception would be treated as a crash, and the model would be told only
    "error executing tool", which is useless to a well-behaved agent and tells
    a misbehaving one just as much.

    The code is stable and the message says nothing internal, so a model can
    explain the refusal to a customer without leaking how the system is built
    (plan 07 section 10.6).
    """
    return ToolError(f"{code}: {detail}")


def _error(code: str, detail: str) -> MCPError:
    """A protocol-level failure: the request itself cannot be served."""
    return MCPError(code=INVALID_PARAMS, message=f"{code}: {detail}")


class ProfileToolFilter:
    """Hide tools a token's profile may not use, as well as refusing them.

    Refusing on call is what protects the system; filtering the listing is what
    stops a model wasting its turn, and stops a tool description for another
    profile being used as a hint about what else exists. An unauthenticated or
    unrecognised caller is shown nothing.
    """

    def __init__(self, core: ClarityMCPServer) -> None:
        self._core = core

    async def __call__(
        self, ctx: ServerRequestContext[Any, Any], call_next: CallNext
    ) -> HandlerResult:
        result = await call_next(ctx)
        if ctx.method != "tools/list":
            return result

        allowed = self._allowed_names()

        # The SDK hands this back as the wire form: a plain dict of
        # ``{"tools": [{"name": ..., "inputSchema": ...}, ...]}``. An earlier
        # version read `result.tools` with a `getattr(..., None)` fallback,
        # found no attribute on a dict, and returned the listing untouched - so
        # the filter silently stopped filtering and every profile saw every
        # tool. A security filter that cannot read its input must say so, not
        # wave it through, so an unknown shape raises here.
        if isinstance(result, dict) and "tools" in result:
            listed = result["tools"]
            if isinstance(listed, list):
                return {
                    **result,
                    "tools": [tool for tool in listed if _name_of(tool) in allowed],
                }
        elif isinstance(result, BaseModel):
            listed = getattr(result, "tools", None)
            if isinstance(listed, list):
                kept = [tool for tool in listed if _name_of(tool) in allowed]
                return result.model_copy(update={"tools": kept})
        raise _error(
            "TOOL_LISTING_UNREADABLE",
            "the tool listing could not be filtered by profile",
        )

    def _allowed_names(self) -> frozenset[str]:
        access = get_access_token()
        if access is None:
            return frozenset()
        try:
            profile = principal_from_claims(access.claims or {}).profile
        except TokenRejected:
            return frozenset()
        return frozenset(spec["name"] for spec in self._core.list_tools(profile))


def _name_of(tool: Any) -> str:
    """The tool's name, whether it arrives as a wire dict or a model."""
    if isinstance(tool, dict):
        return str(tool.get("name", ""))
    return str(getattr(tool, "name", ""))


def build_mcp_app(
    core: ClarityMCPServer,
    verifier: ClarityTokenVerifier,
    *,
    issuer_url: str,
    resource_url: str,
    allowed_hosts: Sequence[str] | None = None,
    json_response: bool = False,
) -> Starlette:
    """Build the ASGI app that serves MCP at ``/mcp``.

    Args:
        core: the authorization and audit chokepoint. Unchanged by the network.
        verifier: the token verifier, as used by the HTTP interface.
        issuer_url: the authorization server that issues tokens for this server.
        resource_url: this server's own identifier, for the RFC 8707 resource
            indicator. A token issued for another resource is refused.
        allowed_hosts: the ``Host`` headers this server answers to. Defaults to
            the host in ``resource_url``. The SDK rejects anything else with
            421, which is its DNS-rebinding defence: without it a page in a
            browser could point a name it controls at a local MCP server and
            drive it. Widen this deliberately, never with a wildcard.
        json_response: answer with a single JSON body instead of an event
            stream. Used by tests and by probes; clients negotiate normally.
    """
    host = urlsplit(resource_url).netloc
    hosts = list(allowed_hosts) if allowed_hosts is not None else [host]
    mcp = MCPServer(
        name="clarity",
        title="Hutch Clarity",
        instructions=(
            "Explain charges from evidence. Every answer must cite the case "
            "evidence or a rule. You cannot move money: the strongest action "
            "available is proposing a remedy the decision already allows, "
            "which a person or the customer then confirms."
        ),
        token_verifier=ClarityResourceServer(verifier, resource_url=resource_url),
        auth=AuthSettings(
            issuer_url=issuer_url,  # type: ignore[arg-type]
            resource_server_url=resource_url,  # type: ignore[arg-type]
            # The verifier checks the audience itself, against the same
            # configuration the HTTP interface uses.
            validate_token_resource=False,
        ),
        middleware=[ProfileToolFilter(core)],
    )

    def _call(tool: str, **args: Any) -> Any:
        try:
            return core.call(_caller(), tool, args)
        except ToolDenied as denied:
            raise _denied(denied.code, str(denied)) from denied

    # ---------------------------------------------------------------- #
    # L1 reads
    # ---------------------------------------------------------------- #

    def get_case_timeline(case_id: str) -> dict[str, Any]:
        """Evidence collected for a case, with per-source completeness."""
        return dict(_call("get_case_timeline", case_id=case_id))

    def get_cause_assessment(case_id: str) -> dict[str, Any]:
        """Ranked causes, what was ruled out, and the decision outcome."""
        return dict(_call("get_cause_assessment", case_id=case_id))

    def explain_rule(rule_id: str) -> dict[str, Any]:
        """What a cause rule checks and the policy basis for it."""
        return dict(_call("explain_rule", rule_id=rule_id))

    def get_trust_receipt(case_id: str) -> dict[str, Any]:
        """The public view of a receipt issued for a case."""
        return dict(_call("get_trust_receipt", case_id=case_id))

    def get_customer_safeguards(case_id: str) -> dict[str, Any]:
        """Safeguards currently protecting the subscriber."""
        return dict(_call("get_customer_safeguards", case_id=case_id))

    def get_network_status(case_id: str) -> dict[str, Any]:
        """Coverage and outage state for the case's subscriber (simulated)."""
        return dict(_call("get_network_status", case_id=case_id))

    def search_knowledge(query: str) -> dict[str, Any]:
        """Cited answers from the published rule catalogue."""
        return dict(_call("search_knowledge", query=query))

    def get_desk_queue() -> list[dict[str, Any]]:
        """Cases waiting for a person, ordered by money at stake."""
        return list(_call("get_desk_queue"))

    # ---------------------------------------------------------------- #
    # L2 low risk and L3 proposals. Nothing here executes.
    # ---------------------------------------------------------------- #

    def request_handoff(case_id: str, reason: str) -> dict[str, Any]:
        """Route the case to a person, with a reason code."""
        return dict(_call("request_handoff", case_id=case_id, reason=reason))

    def propose_action(case_id: str, action_type: str) -> dict[str, Any]:
        """Propose an action the decision already allows.

        This creates a pending plan and nothing else. It never executes, and it
        deliberately takes no amount: the amount comes from the decision record
        (I1). Execution needs a confirmation token minted outside this server.
        """
        return dict(_call("propose_action", case_id=case_id, action_type=action_type))

    for handler in (
        get_case_timeline,
        get_cause_assessment,
        explain_rule,
        get_trust_receipt,
        get_customer_safeguards,
        get_network_status,
        search_knowledge,
        get_desk_queue,
        request_handoff,
        propose_action,
    ):
        mcp.add_tool(handler)

    _add_ui_cards(mcp)
    app = mcp.streamable_http_app(
        stateless_http=True,
        json_response=json_response,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=[f"https://{entry}" for entry in hosts],
        ),
    )

    # ADR-0016: every deployable answers /health. Without it an orchestrator
    # has no way to tell a started process from a working one, and the Helm
    # chart's liveness probe killed this pod in a loop until it was added.
    #
    # Unauthenticated and deliberately empty of detail: a probe runs before any
    # token exists, and a health endpoint that lists tools or configuration is
    # a free reconnaissance endpoint on a server whose whole point is that it
    # cannot be driven without a token.
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "clarity-mcp"})

    app.router.routes.append(Route("/health", health, methods=["GET"]))
    return app


def _add_ui_cards(mcp: MCPServer[Any]) -> None:
    """MCP Apps cards for Why? and the receipt (plan 07 section 10.7).

    These are templates the host renders in a sandbox; they carry no data of
    their own and read the tool result the host passes in. Serving markup
    rather than a URL keeps the card inside the host's sandbox, so a card
    cannot be swapped for a page that asks the customer for anything.
    """

    @mcp.resource(WHY_CARD_URI, mime_type="text/html+skybridge")
    def why_card() -> str:
        return _CARD_HTML

    @mcp.resource(RECEIPT_URI, mime_type="text/html+skybridge")
    def receipt_card() -> str:
        return _CARD_HTML


#: One template for both cards: the host passes the tool result in, and the
#: card renders the fields it finds. No network access, no script origins.
_CARD_HTML = """<!doctype html>
<meta charset="utf-8">
<style>
  :root { color-scheme: light dark; font: 14px system-ui, sans-serif }
  .card { padding: 12px 14px; border: 1px solid color-mix(in srgb, currentColor 20%, transparent);
          border-radius: 10px; max-width: 42rem }
  dt { font-weight: 600; margin-top: .5rem }
  dd { margin: 0 }
  .sim { font-size: 12px; opacity: .7; margin-top: .75rem }
</style>
<div class="card"><dl id="fields"></dl>
  <p class="sim">Hutch Clarity, simulated data (hutch-sim).</p>
</div>
<script>
  const data = window.openai?.toolOutput ?? {};
  const list = document.getElementById("fields");
  for (const [key, value] of Object.entries(data)) {
    if (value === null || typeof value === "object") continue;
    const dt = document.createElement("dt");
    dt.textContent = key.replace(/_/g, " ");
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    list.append(dt, dd);
  }
</script>
"""


__all__ = ["RECEIPT_URI", "WHY_CARD_URI", "ProfileToolFilter", "build_mcp_app"]

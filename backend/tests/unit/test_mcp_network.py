"""MCP over the network: the guarantees must survive the transport (A04, #8).

The in-process tests in ``test_mcp.py`` prove the authorization core refuses
what it should. These drive the **real MCP client** against the **real ASGI
app**, because that is where the principal stops being a trusted object built
by the orchestrator and starts being whatever a bearer token says.

The token issuer here is local to the test: it mints tokens with the claim
shapes an authorization server would, and the verifier it pairs with validates
them properly. The production verifier is
:class:`~clarity.modules.iam.public.KeycloakTokenVerifier`, which has its own
tests against a real Keycloak (``tests/integration/test_keycloak.py``). What is
under test here is everything above the signature check: scope to profile, the
case binding, tool visibility and the refusal codes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world, ref_for
from clarity.interfaces.mcp.app import RECEIPT_URI, WHY_CARD_URI, build_mcp_app
from clarity.interfaces.mcp.auth import (
    ANALYTICS_SCOPE,
    CASE_CLAIM,
    CUSTOMER_SCOPE,
    STAFF_SCOPE,
)
from clarity.interfaces.mcp.server import ClarityMCPServer
from clarity.kernel.common import Channel, utc_now
from clarity.modules.iam.public import TokenInvalid
from clarity.platform.security.principal import Assurance, Principal, Role

ISSUER = "https://issuer.test/realms/clarity"
RESOURCE = "https://mcp.clarity.test/mcp"
AUDIENCE = "clarity-api"

DILANI = "+94781234567"
PRIYA = "+94784445555"


class _TestIdentityProvider:
    """Mints and verifies tokens, standing in for the authorization server.

    Deliberately a real signature over a real key: a test that accepted
    unsigned tokens could not show that a tampered one is refused.
    """

    def __init__(self) -> None:
        self._key = Ed25519PrivateKey.generate()

    def token(
        self,
        *,
        subject: str = "client-1",
        scopes: tuple[str, ...] = (CUSTOMER_SCOPE,),
        case_id: str | None = None,
        audience: str = AUDIENCE,
        extra: dict[str, Any] | None = None,
    ) -> str:
        now = utc_now()
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "aud": audience,
            "sub": subject,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "scope": " ".join(scopes),
            "azp": "clarity-mcp",
        }
        if case_id is not None:
            claims[CASE_CLAIM] = case_id
        claims.update(extra or {})
        return jwt.encode(claims, self._key, algorithm="EdDSA", headers={"kid": "test"})

    # The Clarity TokenVerifier protocol.
    def verify(self, token: str, *, now: datetime | None = None) -> Principal:
        try:
            claims = jwt.decode(
                token,
                self._key.public_key(),
                algorithms=["EdDSA"],
                audience=AUDIENCE,
                issuer=ISSUER,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.InvalidTokenError as error:
            raise TokenInvalid from error
        return Principal(
            ref=str(claims["sub"]),
            roles=frozenset({Role.AGENT}),
            assurance=Assurance.MFA,
            channel="mcp",
        )


@pytest.fixture
def idp() -> _TestIdentityProvider:
    return _TestIdentityProvider()


@pytest.fixture
def clarity() -> Clarity:
    return Clarity(world=build_demo_world())


@pytest.fixture
def core(clarity: Clarity) -> ClarityMCPServer:
    return ClarityMCPServer(clarity.mcp_view)


@pytest.fixture
def app(core: ClarityMCPServer, idp: _TestIdentityProvider) -> Any:
    return build_mcp_app(
        core,
        idp,
        issuer_url=ISSUER,
        resource_url=RESOURCE,
        json_response=True,
    )


def a_case(clarity: Clarity, msisdn: str) -> str:
    account = clarity.world.account(ref_for(msisdn))
    assert account is not None
    case = clarity.cases.open_case(
        subscriber_ref=account.ref, msisdn_masked=account.masked, channel=Channel.APP
    )
    clarity.cases.evaluate(case.case_id)
    return case.case_id


@asynccontextmanager
async def _Connection(app: Any, token: str | None) -> AsyncIterator[ClientSession]:
    """One authenticated MCP session over the ASGI app, no port involved.

    Written as a generator rather than a class with ``__aenter__``/``__aexit__``
    on purpose: the client opens an anyio task group, and anyio requires the
    scope to be exited in the task that entered it. A class splits those two
    halves across pytest-asyncio's tasks and fails with "attempted to exit
    cancel scope in a different task".
    """
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    # The session manager starts in the app's lifespan, which an ASGI transport
    # does not run for you. Without this the transport answers every request
    # with "task group is not initialized".
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="https://mcp.clarity.test",
            headers=headers,
        ) as client,
        streamable_http_client(RESOURCE, http_client=client) as (
            read,
            write,
        ),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        yield session


# --------------------------------------------------------------------------- #
# Acceptance test 1: a token for customer A cannot reach customer B
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_customer_token_cannot_read_another_customers_case(
    app: Any, clarity: Clarity, core: ClarityMCPServer, idp: _TestIdentityProvider
) -> None:
    """A04 acceptance test 1: denied **and** audited."""
    mine = a_case(clarity, DILANI)
    theirs = a_case(clarity, PRIYA)
    token = idp.token(scopes=(CUSTOMER_SCOPE,), case_id=mine)

    async with _Connection(app, token) as session:
        result = await session.call_tool("get_case_timeline", {"case_id": theirs})

    assert result.is_error, "reading another customer's case must fail"
    assert "NOT_AUTHORISED_FOR_CASE" in str(result.content)
    assert [row.error_code for row in core.denials] == ["NOT_AUTHORISED_FOR_CASE"]


@pytest.mark.asyncio
async def test_a_customer_token_with_no_case_claim_reaches_nothing(
    app: Any, clarity: Clarity, core: ClarityMCPServer, idp: _TestIdentityProvider
) -> None:
    """The shape only the network makes possible: customer scope, no binding."""
    case_id = a_case(clarity, DILANI)
    token = idp.token(scopes=(CUSTOMER_SCOPE,), case_id=None)

    async with _Connection(app, token) as session:
        result = await session.call_tool("get_case_timeline", {"case_id": case_id})

    assert result.is_error
    assert "SESSION_NOT_BOUND" in str(result.content)
    assert [row.error_code for row in core.denials] == ["SESSION_NOT_BOUND"]


@pytest.mark.asyncio
async def test_a_customer_token_reads_its_own_case(
    app: Any, clarity: Clarity, idp: _TestIdentityProvider
) -> None:
    """The denials above must not be a server that refuses everything."""
    case_id = a_case(clarity, DILANI)
    token = idp.token(scopes=(CUSTOMER_SCOPE,), case_id=case_id)

    async with _Connection(app, token) as session:
        result = await session.call_tool("get_case_timeline", {"case_id": case_id})

    assert not result.is_error
    assert case_id in str(result.content)


# --------------------------------------------------------------------------- #
# The profile comes from the token, not from the request
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_customer_token_is_not_shown_staff_tools(
    app: Any, clarity: Clarity, idp: _TestIdentityProvider
) -> None:
    case_id = a_case(clarity, DILANI)
    token = idp.token(scopes=(CUSTOMER_SCOPE,), case_id=case_id)

    async with _Connection(app, token) as session:
        listed = {tool.name for tool in (await session.list_tools()).tools}

    assert "get_case_timeline" in listed
    assert "get_desk_queue" not in listed


@pytest.mark.asyncio
async def test_a_staff_token_is_shown_the_desk_queue(app: Any, idp: _TestIdentityProvider) -> None:
    token = idp.token(subject="agent-7", scopes=(STAFF_SCOPE,))

    async with _Connection(app, token) as session:
        listed = {tool.name for tool in (await session.list_tools()).tools}

    assert "get_desk_queue" in listed


@pytest.mark.asyncio
async def test_a_hidden_tool_is_also_refused_when_called_anyway(
    app: Any, clarity: Clarity, idp: _TestIdentityProvider
) -> None:
    """Hiding is a convenience; refusing is the control.

    A model that learned the name elsewhere must still be refused, so the
    listing filter is never the only thing standing in the way.
    """
    case_id = a_case(clarity, DILANI)
    token = idp.token(scopes=(CUSTOMER_SCOPE,), case_id=case_id)

    async with _Connection(app, token) as session:
        result = await session.call_tool("get_desk_queue", {})

    assert result.is_error
    assert "NOT_IN_PROFILE" in str(result.content)


@pytest.mark.asyncio
async def test_a_token_with_no_profile_scope_gets_no_tools_and_no_answers(
    app: Any, clarity: Clarity, idp: _TestIdentityProvider
) -> None:
    case_id = a_case(clarity, DILANI)
    token = idp.token(scopes=(), case_id=case_id)

    async with _Connection(app, token) as session:
        listed = {tool.name for tool in (await session.list_tools()).tools}
        result = await session.call_tool("get_case_timeline", {"case_id": case_id})

    assert listed == set()
    assert result.is_error
    assert "NO_PROFILE_SCOPE" in str(result.content)


@pytest.mark.asyncio
async def test_two_profile_scopes_are_refused_rather_than_narrowed(
    app: Any, clarity: Clarity, idp: _TestIdentityProvider
) -> None:
    """A client registered with two profiles is a misconfiguration, loudly."""
    case_id = a_case(clarity, DILANI)
    token = idp.token(scopes=(CUSTOMER_SCOPE, STAFF_SCOPE), case_id=case_id)

    async with _Connection(app, token) as session:
        result = await session.call_tool("get_case_timeline", {"case_id": case_id})

    assert result.is_error
    assert "AMBIGUOUS_PROFILE" in str(result.content)


# --------------------------------------------------------------------------- #
# Authentication itself
# --------------------------------------------------------------------------- #


async def _initialize_status(app: Any, token: str | None) -> int:
    """The HTTP status an MCP client gets when it tries to open a session.

    Asserted on directly rather than through the client's exception: the client
    wraps a transport failure in nested task-group exception groups, so
    matching on the message proves little and breaks on an SDK change. The
    status code is the contract an unauthenticated caller actually meets.
    """
    headers = {"Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="https://mcp.clarity.test",
        ) as client,
    ):
        response = await client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2026-07-28",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
        )
    return response.status_code


@pytest.mark.asyncio
async def test_an_unauthenticated_caller_is_refused(app: Any) -> None:
    assert await _initialize_status(app, None) == 401


@pytest.mark.asyncio
async def test_a_token_signed_by_someone_else_is_refused(app: Any) -> None:
    """The signature is checked, so the right claims alone buy nothing."""
    forged = _TestIdentityProvider().token(scopes=(STAFF_SCOPE,))

    assert await _initialize_status(app, forged) == 401


@pytest.mark.asyncio
async def test_a_token_for_another_audience_is_refused(
    app: Any, idp: _TestIdentityProvider
) -> None:
    """Confused deputy: a token for another service must not work here."""
    wrong = idp.token(scopes=(STAFF_SCOPE,), audience="some-other-api")

    assert await _initialize_status(app, wrong) == 401


@pytest.mark.asyncio
async def test_a_valid_token_is_accepted_by_the_same_path(
    app: Any, idp: _TestIdentityProvider
) -> None:
    """Guards the three refusals above against a server that 401s everything."""
    good = idp.token(subject="agent-7", scopes=(STAFF_SCOPE,))

    assert await _initialize_status(app, good) == 200


# --------------------------------------------------------------------------- #
# Acceptance test 3: nothing over the network executes money movement
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_no_published_tool_takes_an_amount(app: Any, idp: _TestIdentityProvider) -> None:
    """A04 acceptance test 3, at the level a model actually sees.

    ``test_mcp.py`` proves the handler refuses an amount. This proves the
    published schema never invites one, so a model is not even told that a
    number could be supplied (I1).
    """
    token = idp.token(subject="agent-7", scopes=(STAFF_SCOPE,))

    async with _Connection(app, token) as session:
        tools = (await session.list_tools()).tools

    assert tools, "the staff profile must see tools"
    for tool in tools:
        properties = (tool.input_schema or {}).get("properties", {})
        assert "amount" not in properties, f"{tool.name} publishes an amount parameter"
        assert "amount_lkr" not in properties, f"{tool.name} publishes an amount parameter"


@pytest.mark.asyncio
async def test_no_published_tool_name_suggests_execution(
    app: Any, idp: _TestIdentityProvider
) -> None:
    token = idp.token(subject="agent-7", scopes=(STAFF_SCOPE,))

    async with _Connection(app, token) as session:
        names = {tool.name for tool in (await session.list_tools()).tools}

    forbidden = ("execute", "confirm", "approve", "refund", "pay", "transfer")
    assert not [name for name in names if any(word in name for word in forbidden)]


# --------------------------------------------------------------------------- #
# Acceptance test 2: a client lists tools and gets a cited answer
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_client_lists_tools_and_gets_a_cited_answer(
    app: Any, clarity: Clarity, idp: _TestIdentityProvider
) -> None:
    """A04 acceptance test 2, automated.

    WT-10 walks the same path with the MCP Inspector; this keeps it honest
    between walkthroughs.
    """
    case_id = a_case(clarity, DILANI)
    token = idp.token(scopes=(CUSTOMER_SCOPE,), case_id=case_id)

    async with _Connection(app, token) as session:
        listed = {tool.name for tool in (await session.list_tools()).tools}
        answer = await session.call_tool("search_knowledge", {"query": "unauthorised VAS charge"})

    assert "search_knowledge" in listed
    assert not answer.is_error
    chunks = (answer.structured_content or {}).get("chunks", [])
    assert chunks, "a known question must return at least one chunk"
    for chunk in chunks:
        assert chunk["source_id"], "every chunk must carry a citation"
        assert "@" in chunk["source_id"], "a citation names rule_id@version"


@pytest.mark.asyncio
async def test_a_search_query_is_masked_before_it_is_returned_or_audited(
    app: Any, clarity: Clarity, core: ClarityMCPServer, idp: _TestIdentityProvider
) -> None:
    """A query is model text and may carry whatever the customer typed (I13)."""
    case_id = a_case(clarity, DILANI)
    token = idp.token(scopes=(CUSTOMER_SCOPE,), case_id=case_id)

    async with _Connection(app, token) as session:
        answer = await session.call_tool("search_knowledge", {"query": "VAS charge on 0781234567"})

    assert "0781234567" not in str(answer.content)
    assert "0781234567" not in str(answer.structured_content)


@pytest.mark.asyncio
async def test_the_ui_cards_are_served_as_resources(app: Any, idp: _TestIdentityProvider) -> None:
    """MCP Apps cards for Why? and the receipt (plan 07 section 10.7)."""
    token = idp.token(subject="agent-7", scopes=(STAFF_SCOPE,))

    async with _Connection(app, token) as session:
        uris = {str(resource.uri) for resource in (await session.list_resources()).resources}

    assert WHY_CARD_URI in uris
    assert RECEIPT_URI in uris


@pytest.mark.asyncio
async def test_the_analytics_profile_sees_only_catalogue_tools(
    app: Any, idp: _TestIdentityProvider
) -> None:
    token = idp.token(subject="bi-1", scopes=(ANALYTICS_SCOPE,))

    async with _Connection(app, token) as session:
        listed = {tool.name for tool in (await session.list_tools()).tools}

    assert listed == {"explain_rule", "search_knowledge"}
    assert "get_case_timeline" not in listed

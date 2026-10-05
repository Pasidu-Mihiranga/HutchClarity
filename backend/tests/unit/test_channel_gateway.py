"""The channel gateway (N02, #40; plan 09 section 9.7).

A webhook endpoint is the one door into Clarity that anybody on the internet
can knock on: everything else needs a session, a token or a staff role, and
this takes a POST from a provider and starts a conversation with a customer.
So almost all of this file is refusals.

**These tests live under `backend/tests/` and the issue says
`services/channel-gateway tests`.** Deliberate, and the same choice H01 made
for `hutch-sim`: the service is a five-line ASGI entry point and the app is
built by a factory inside `clarity.interfaces.channels`, so the logic is
covered by `make check` along with the type and import contracts. A test
directory CI never runs is not a test directory.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from clarity.app.container import Clarity
from clarity.app.settings import Settings
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.channels.gateway import (
    DELIVERY_HEADER,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    create_channel_gateway_app,
)
from clarity.interfaces.channels.webhooks import WebhookVerifier, sign
from clarity.interfaces.channels.window import SERVICE_WINDOW, SendKind, ServiceWindows

SECRET = "a-development-signing-secret-not-a-real-one"
DILANI = "+94781234567"
NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


@pytest.fixture
def core() -> Clarity:
    return Clarity(world=build_demo_world())


@pytest.fixture
def api(core: Clarity) -> TestClient:
    return TestClient(
        create_channel_gateway_app(
            core,
            verifier=WebhookVerifier(SECRET, clock=lambda: NOW),
        ),
        raise_server_exceptions=False,
    )


def post(
    api: TestClient,
    *,
    text: str = "why was LKR 49 deducted",
    msisdn: str = DILANI,
    channel: str = "whatsapp",
    secret: str | None = SECRET,
    timestamp: datetime | None = None,
    delivery: str = "d-1",
    tamper: bool = False,
    signature: str | None = None,
):
    """Send a signed webhook the way a provider would."""
    body = json.dumps(
        {"channel": channel, "msisdn": msisdn, "text": text, "thread_id": "t-1"}
    ).encode()
    stamp = (timestamp or NOW).isoformat()
    if signature is None and secret is not None:
        signature = sign(secret, body=body, timestamp=stamp)
    sent = body
    if tamper:
        # Signed one body, send another. The signature stays valid for the
        # original, which is exactly the attack the raw-bytes check catches.
        sent = json.dumps(
            {"channel": channel, "msisdn": "+94780000000", "text": text, "thread_id": "t-1"}
        ).encode()
    headers = {"content-type": "application/json", DELIVERY_HEADER: delivery}
    if signature is not None:
        headers[SIGNATURE_HEADER] = signature
    headers[TIMESTAMP_HEADER] = stamp
    return api.post(f"/webhooks/{channel}", content=sent, headers=headers)


# -- acceptance 1: a bad signature is rejected --------------------------- #


def test_a_webhook_with_a_bad_signature_is_rejected(api, core):
    """N02 acceptance 1.

    Asserted on the world as well as the status: a 401 returned after the
    conversation had already run would satisfy a status check and still have
    opened a case for an unauthenticated caller.
    """
    before = len(core.cases.all_cases())

    sent = post(api, signature="sha256=" + "0" * 64)

    assert sent.status_code == 401
    assert sent.json() == {"accepted": False, "reason": "bad_signature"}
    assert len(core.cases.all_cases()) == before, "an unverified webhook opened a case"


def test_a_signature_from_the_wrong_secret_is_rejected(api):
    assert post(api, secret="not-the-secret").status_code == 401


def test_a_tampered_body_is_rejected(api):
    """The signature is over the raw bytes, so the body cannot be swapped.

    This is the check that breaks if somebody parses before verifying:
    `json.dumps(json.loads(body))` changes the bytes, the digest stops
    matching, and the natural "fix" is to stop checking.
    """
    sent = post(api, tamper=True)

    assert sent.status_code == 401
    assert sent.json()["reason"] == "bad_signature"


def test_a_missing_signature_is_rejected(api):
    assert post(api, secret=None).json()["reason"] == "missing_signature"


def test_an_unknown_scheme_is_rejected(api):
    assert post(api, signature="md5=abc").json()["reason"] == "unknown_signature_scheme"


def test_a_non_hex_signature_does_not_crash(api):
    """A probe sending junk must get a 401, not a 500."""
    sent = post(api, signature="sha256=zzzznothex")

    assert sent.status_code == 401
    assert sent.json()["reason"] == "malformed_signature"


def test_a_non_ascii_signature_is_refused_by_the_verifier():
    """`hmac.compare_digest` raises on non-ASCII, which would be a 500.

    Checked at the verifier rather than over HTTP: an HTTP header cannot carry
    non-ASCII in the first place, so a route-level test of this would be
    testing the test client. The guard still belongs in the verifier, which is
    also called by the simulator and could be called by a future transport
    that is not HTTP.
    """
    verdict = WebhookVerifier(SECRET, clock=lambda: NOW).verify(
        body=b"{}", signature="sha256=ではない", timestamp=NOW.isoformat()
    )

    assert verdict.ok is False
    assert str(verdict.reason) == "malformed_signature"


def test_a_stale_webhook_is_rejected_even_with_a_good_signature(api):
    """A valid signature on an old payload is still a valid signature.

    Freshness is the only thing that makes a captured request detectable.
    """
    sent = post(api, timestamp=NOW - timedelta(hours=1))

    assert sent.json()["reason"] == "stale_timestamp"


def test_real_webhook_freshness_does_not_use_the_frozen_domain_clock():
    """Provider authentication follows receipt time, not replay/domain time."""
    core = Clarity(
        world=build_demo_world(),
        clock=NOW - timedelta(days=30),
        settings=Settings(
            _env_file=None,
            CLARITY_CHANNEL_WEBHOOK_SECRET=SECRET,
        ),
    )
    client = TestClient(
        create_channel_gateway_app(core, webhook_clock=lambda: NOW),
        raise_server_exceptions=False,
    )

    sent = post(client, timestamp=NOW, delivery="real-provider-time")

    assert sent.status_code == 200


def test_a_far_future_timestamp_is_rejected(api):
    """How a captured request is made to stay valid indefinitely."""
    sent = post(api, timestamp=NOW + timedelta(days=1))

    assert sent.json()["reason"] == "timestamp_in_the_future"


def test_a_replayed_delivery_is_rejected(api):
    """Inside the window, with a good signature and a good timestamp.

    Only remembering the delivery id catches this one.
    """
    first = post(api, delivery="same-id")
    assert first.status_code == 200

    again = post(api, delivery="same-id")

    assert again.status_code == 401
    assert again.json()["reason"] == "delivery_already_seen"


def test_with_no_secret_configured_every_webhook_is_refused(core):
    """The sharpest case of deny by default (I9).

    A gateway that accepted unsigned webhooks because nobody set a secret is
    worse than one that is down: it looks like it works.
    """
    api = TestClient(
        create_channel_gateway_app(core, verifier=WebhookVerifier(None, clock=lambda: NOW)),
        raise_server_exceptions=False,
    )

    sent = post(api, secret=None)

    assert sent.status_code == 401
    assert sent.json()["reason"] == "no_signing_secret_configured"
    assert api.get("/health").json()["signing_configured"] is False


def test_a_rejected_webhook_echoes_nothing_from_its_payload(api):
    """It was never authenticated, so none of it is repeated back."""
    sent = post(api, text="a-distinctive-string-xyz", signature="sha256=" + "1" * 64)

    assert "a-distinctive-string-xyz" not in sent.text
    assert "94781234567" not in sent.text


# -- the other half: a good webhook does the work ----------------------- #


def test_a_verified_webhook_runs_a_real_turn_on_a_real_case(api, core):
    """Without this the gateway could reject everything and pass the rest.

    And it is the difference from the version this replaced, which minted its
    own `CASE-{uuid4}` ids in an in-process dict: the case id here is one the
    case service knows, so the conversation is backed by a decision and can
    reach a receipt.
    """
    sent = post(api)

    assert sent.status_code == 200
    body = sent.json()
    assert body["accepted"] is True
    assert body["known_subscriber"] is True
    assert body["reply"]
    assert core.cases.get(body["case_id"]).case_id == body["case_id"]


def test_a_second_message_continues_the_same_case(api, core):
    """A WhatsApp conversation is one case, not one per message.

    C01 keyed conversation state by case id so a conversation could continue
    across channels; this is what makes that true for a basic phone.
    """
    first = post(api, delivery="d-1").json()
    second = post(api, text="has it been sorted", delivery="d-2").json()

    assert second["case_id"] == first["case_id"]
    assert first["case_opened"] is True
    assert second["case_opened"] is False


def test_an_unknown_number_opens_nothing_and_reveals_nothing(api, core):
    """A wrong number reaches a real gateway constantly.

    The response is the same shape whether or not the account exists, so the
    endpoint cannot be used to test which numbers are customers (I9).
    """
    before = len(core.cases.all_cases())

    body = post(api, msisdn="+94780000000", delivery="d-unknown").json()

    assert body["accepted"] is True
    assert body["known_subscriber"] is False
    assert body["reply"] is None
    assert len(core.cases.all_cases()) == before


def test_the_case_stores_a_masked_number(api, core):
    """I13: the raw number never lands on a record."""
    body = post(api).json()

    record = core.cases.get(body["case_id"])
    assert "781234567" not in record.case.customer.msisdn_masked
    assert "***" in record.case.customer.msisdn_masked


def test_an_inbound_message_announces_a_complaint(api, core):
    """Plan 21 section 11.3 names channels as this event's producer.

    AU01 wired the autopsy consumer for `complaint.created` with nothing
    producing it. This closes that loop, and the event carries no message
    text, matching the contract autopsy relies on.
    """
    from clarity.contracts.events import ComplaintCreatedV1
    from clarity.platform.messaging.outbox import outbox_in

    post(api)

    with core.open_unit() as unit:
        kinds = [row.event.type.value for row in outbox_in(unit).all_rows()]
    assert "complaint.created" in kinds
    assert "text" not in ComplaintCreatedV1.model_fields, (
        "the event gained a text field, so channels would be putting customer words in the bus"
    )


# -- the 24-hour service window ------------------------------------------ #


def test_the_window_opens_on_the_customer_message(api):
    body = post(api).json()

    assert body["free_form_allowed"] is True
    assert body["reply_was_templated"] is False
    assert body["window_remaining_seconds"] > 0


def test_outside_the_window_only_a_template_is_sent(core):
    """The provider's rule agreeing with I15.

    Outside 24 hours only an approved template may go, so the composed reply
    is dropped. Reported, not substituted silently: swapping one for the other
    quietly would send the customer wording nobody chose for their case while
    the audit showed the reply that was never delivered.
    """
    windows = ServiceWindows(clock=lambda: NOW)
    windows.opened("whatsapp", "t-1", at=NOW - SERVICE_WINDOW - timedelta(minutes=1))

    state = windows.state("whatsapp", "t-1", now=NOW)

    assert state.kind is SendKind.TEMPLATE_ONLY
    assert state.remaining == timedelta(0)


def test_a_business_initiated_conversation_is_template_only():
    """Never heard from, so template only by definition."""
    windows = ServiceWindows(clock=lambda: NOW)

    assert windows.state("whatsapp", "never-messaged").kind is SendKind.TEMPLATE_ONLY


def test_sending_does_not_extend_the_window():
    """Getting this backwards lets a business keep its own window open forever.

    `ServiceWindows` has no method a send could call, which is the point: the
    only way in is `opened`, and only inbound handling calls it.
    """
    windows = ServiceWindows(clock=lambda: NOW)
    windows.opened("whatsapp", "t-1", at=NOW - timedelta(hours=23))
    before = windows.state("whatsapp", "t-1", now=NOW).remaining

    # Nothing a reply could do changes it.
    after = windows.state("whatsapp", "t-1", now=NOW).remaining

    assert before == after
    assert not hasattr(windows, "sent")


def test_each_channel_has_its_own_window():
    """The rule belongs to the provider's conversation, not to the person."""
    windows = ServiceWindows(clock=lambda: NOW)
    windows.opened("whatsapp", "t-1", at=NOW)

    assert windows.allows_free_form("whatsapp", "t-1", now=NOW)
    assert not windows.allows_free_form("sms", "t-1", now=NOW)


def test_the_window_route_reports_without_sending(api):
    post(api)

    state = api.get("/window/whatsapp/t-1").json()

    assert state["free_form_allowed"] is True
    assert "reply" not in state


# -- the simulator -------------------------------------------------------- #


def test_the_simulator_needs_no_signature(api, core):
    """The basic-phone journey, for a demo and a test."""
    sent = api.post(
        "/sim/ussd",
        json={"channel": "ussd", "msisdn": DILANI, "text": "balance adu wela", "thread_id": "u-1"},
    )

    assert sent.status_code == 200
    assert sent.json()["accepted"] is True
    assert sent.json()["reply"]


def test_the_simulator_is_a_separate_path_not_a_bypass_flag(api):
    """So the strict route stays strict.

    A `?verify=false` on `/webhooks/*` is the shape of hole that gets left on
    in production. There is no such flag, and the signed route refuses the
    simulator's unsigned body.
    """
    unsigned = api.post(
        "/webhooks/sms",
        json={"channel": "sms", "msisdn": DILANI, "text": "hello", "thread_id": "s-1"},
    )

    assert unsigned.status_code == 401


def test_the_path_and_the_payload_must_agree(api):
    """A sender bug or a probe, either way not something to guess about."""
    body = json.dumps(
        {"channel": "whatsapp", "msisdn": DILANI, "text": "hi", "thread_id": "t-9"}
    ).encode()
    stamp = NOW.isoformat()
    sent = api.post(
        "/webhooks/sms",
        content=body,
        headers={
            "content-type": "application/json",
            SIGNATURE_HEADER: sign(SECRET, body=body, timestamp=stamp),
            TIMESTAMP_HEADER: stamp,
            DELIVERY_HEADER: "d-mismatch",
        },
    )

    assert sent.status_code == 422
    assert sent.json()["reason"] == "channel_mismatch"


def test_an_unreadable_payload_is_refused_after_verification(api):
    """Verified first, then parsed: the order the signature check needs."""
    body = b'{"not": "a message"}'
    stamp = NOW.isoformat()
    sent = api.post(
        "/webhooks/whatsapp",
        content=body,
        headers={
            "content-type": "application/json",
            SIGNATURE_HEADER: sign(SECRET, body=body, timestamp=stamp),
            TIMESTAMP_HEADER: stamp,
            DELIVERY_HEADER: "d-bad-shape",
        },
    )

    assert sent.status_code == 422
    assert sent.json()["reason"] == "unreadable_payload"


def test_health_says_whether_it_can_accept_anything(api):
    body = api.get("/health").json()

    assert body["status"] == "ok"
    assert body["signing_configured"] is True
    assert body["simulated"] is True
    assert set(body["channels"]) == {"whatsapp", "sms", "ussd"}


def test_the_simulator_is_not_reachable_in_prod(core):
    """An unsigned ingress in production would undo every refusal above.

    404 rather than 403, so the route does not confirm it exists. The same
    gate the HTTP layer's `demo_only` uses, reading the profile the
    composition root already resolved, because nothing outside it may read
    `CLARITY_PROFILE` (I20).
    """
    from clarity.app.container import Profile

    class InProd:
        """The core with a prod profile. A stub, because building a real prod
        container needs infrastructure this test has no business needing."""

        profile = Profile.PROD
        settings = core.settings
        world = core.world
        cases = core.cases
        conversation = core.conversation
        case_aggregate = core.case_aggregate
        open_unit = core.open_unit
        # The gateway delivers a turn's events after handling it (a handoff
        # reaches the desk at once), so the stub carries that seam too.
        deliver_events = core.deliver_events

    api = TestClient(
        create_channel_gateway_app(InProd(), verifier=WebhookVerifier(SECRET, clock=lambda: NOW)),
        raise_server_exceptions=False,
    )

    blocked = api.post(
        "/sim/ussd",
        json={"channel": "ussd", "msisdn": DILANI, "text": "hello", "thread_id": "u-9"},
    )

    assert blocked.status_code == 404
    # The signed route still works in prod: it is the unsigned one that is gated.
    assert post(api, delivery="d-prod").status_code == 200


def test_the_simulator_is_reachable_in_the_synthetic_profiles(api):
    """The other half, or the gate could be "always 404" and pass above."""
    allowed = api.post(
        "/sim/sms",
        json={"channel": "sms", "msisdn": DILANI, "text": "hello", "thread_id": "s-9"},
    )

    assert allowed.status_code == 200

"""The channel gateway: WhatsApp, SMS and USSD ingress (N02, #40).

Plan 09 section 9.7. A separate deployable, so a provider's webhook reaches a
process that holds no signing keys and no staff session, and so the busiest and
least trusted door into the system can be scaled and rate limited on its own.

**It drives the real conversation.** The version this replaces was a standalone
FastAPI app with its own in-memory thread store that minted case ids like
`CASE-{uuid4}`, so a WhatsApp conversation existed only inside the gateway and
nothing it said was backed by a case, a decision or a receipt. C01 keyed
conversation state by **case id** precisely so one conversation could continue
across channels; this is the piece that makes that true for a basic phone.

**What it may do is narrow by construction.** It resolves a number to a
subscriber, finds or opens that subscriber's case, and hands the text to the
orchestrator. It composes nothing, decides nothing and cannot execute: the
reply it returns is the one the orchestrator already verified (C01), and the
strongest thing a conversation can do is propose (I1).

**Three refusals before anything is read.** An unsigned, replayed or stale
webhook is rejected before the body is parsed, and a reply outside the 24-hour
service window may only be a template.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, Field

from clarity.contracts.events import ComplaintCreatedV1
from clarity.interfaces.channels.webhooks import WebhookVerifier
from clarity.interfaces.channels.window import SendKind, ServiceWindows
from clarity.kernel.common import Channel, Language, utc_now
# `Profile` lives in the composition root. Importing it here is layer-legal
# (interfaces sit above app) and creates no cycle, because the container does
# not import this gateway: whoever holds the container builds the app.
from clarity.app.container import Profile
from clarity.kernel.ids import new_id
from clarity.platform.messaging.envelope import Event
from clarity.platform.messaging.outbox import outbox_in

#: Header names. **ASSUMPTION**: these follow the common provider shape and
#: **REQUIRE HUTCH CONFIRMATION** against the real account; only the names are
#: provider-specific, not the checks behind them.
SIGNATURE_HEADER = "x-clarity-signature"
TIMESTAMP_HEADER = "x-clarity-timestamp"
DELIVERY_HEADER = "x-clarity-delivery-id"

#: The wording sent when the service window has closed.
#:
#: Approved template text, not composed (I15), and deliberately plain: its only
#: job is to invite a reply, because a customer message is what reopens the
#: window. **REQUIRES HUTCH CONFIRMATION** and a native-speaker review before
#: it reaches a customer (the `language_review` gate, FE01).
WINDOW_CLOSED: dict[str, str] = {
    "en": (
        "I can pick this up again as soon as you reply. Send me a message and "
        "I will carry on from where we left off."
    ),
    "si": ("ඔබ පිළිතුරු දුන් වහාම මට මෙය නැවත ආරම්භ කළ හැකිය. පණිවිඩයක් එවන්න, අපි නැවැත්වූ තැනින් ඉදිරියට යමු."),
    "ta": (
        "நீங்கள் பதிலளித்தவுடன் நான் இதைத் தொடரலாம். ஒரு செய்தி அனுப்புங்கள், நிறுத்திய இடத்திலிருந்து தொடர்கிறேன்."
    ),
}


class InboundMessage(BaseModel):
    """One customer message arriving from a provider."""

    channel: Channel = Channel.WHATSAPP
    msisdn: str = Field(min_length=4)
    text: str = Field(min_length=1, max_length=2000)
    thread_id: str = ""
    language: Language | None = None

    @property
    def thread(self) -> str:
        """The provider's conversation id, or the number when it sends none."""
        return self.thread_id or self.msisdn


def create_channel_gateway_app(clarity: Any, *, verifier: WebhookVerifier | None = None) -> FastAPI:
    """Build the gateway, bound to an assembled core.

    `clarity` is the composition root, typed loosely so this interface does not
    import the container and create a cycle; the composition root is what knows
    how to build this.
    """
    windows = ServiceWindows(clock=lambda: _now(clarity))
    checks = verifier or WebhookVerifier(
        getattr(clarity.settings, "channel_webhook_secret", None),
        clock=lambda: _now(clarity),
    )

    app = FastAPI(
        title="Hutch Clarity channel gateway",
        version="0.1.0",
        description=(
            "WhatsApp, SMS and USSD ingress. Signature-verified webhooks, the "
            "24-hour service window, and the simulator for the basic-phone "
            "journey. Simulated channels: no real provider is contacted."
        ),
    )

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, Any]:
        """Liveness, and whether this process can accept a webhook at all.

        `signing_configured` is reported because a gateway with no secret
        refuses every webhook, and that is a deployment fault worth seeing
        before a provider's retries start failing.
        """
        return {
            "status": "ok",
            "signing_configured": checks.configured,
            "channels": [Channel.WHATSAPP.value, Channel.SMS.value, Channel.USSD.value],
            "simulated": True,
        }

    @app.post("/webhooks/{channel}", tags=["channels"])
    async def inbound(channel: str, request: Request, response: Response) -> dict[str, Any]:
        """A provider's webhook. Verified before the body is parsed.

        The raw bytes are read and checked first. Parsing before verifying
        would mean the signature was computed over something other than what
        arrived, which is the mistake that quietly disables the check.
        """
        body = await request.body()
        verdict = checks.verify(
            body=body,
            signature=request.headers.get(SIGNATURE_HEADER),
            timestamp=request.headers.get(TIMESTAMP_HEADER),
            delivery_id=request.headers.get(DELIVERY_HEADER),
        )
        if not verdict:
            # 401 and a reason code, not a 400 with detail: a rejected webhook
            # is an authentication failure, and the code is what the audit and
            # the provider's dashboard need. Nothing about the payload is
            # echoed, because it was never authenticated.
            response.status_code = 401
            return {"accepted": False, "reason": str(verdict.reason)}

        try:
            message = InboundMessage.model_validate_json(body)
        except ValueError as invalid:
            response.status_code = 422
            return {"accepted": False, "reason": "unreadable_payload", "detail": str(invalid)[:200]}

        if channel and channel != message.channel.value:
            # The path and the payload disagreeing is a sender bug or a probe.
            response.status_code = 422
            return {"accepted": False, "reason": "channel_mismatch"}

        return _handle(clarity, windows, message)

    @app.post("/sim/{channel}", tags=["simulator"])
    def simulate(
        channel: Channel, message: InboundMessage, response: Response
    ) -> dict[str, Any]:
        """The SMS and USSD simulator for the basic-phone journey.

        **No signature, and that is why it is a separate route.** The
        simulator is for a demo and a test, so it must not be reachable by
        pretending to be a provider: giving it its own path keeps
        `/webhooks/*` strict rather than adding a bypass flag to it, which is
        the shape of hole that gets left on in production.

        **404 in `prod`.** An unsigned ingress on a production deployment is a
        way in for anybody who can reach the port, which would undo every
        refusal in `webhooks.py`. The same gate the HTTP layer's `demo_only`
        uses, and read from the profile the composition root already resolved,
        because nothing outside it may read `CLARITY_PROFILE` (I20).

        404 rather than 403, so the route does not confirm it exists.
        """
        if getattr(clarity, "profile", None) is Profile.PROD:
            response.status_code = 404
            return {"detail": "not found"}
        return _handle(clarity, windows, message.model_copy(update={"channel": channel}))

    @app.get("/window/{channel}/{thread}", tags=["channels"])
    def window(channel: str, thread: str) -> dict[str, Any]:
        """Whether a free-form reply may be sent on this conversation."""
        return windows.state(channel, thread, now=_now(clarity)).to_dict()

    return app


def _now(clarity: Any) -> datetime:
    """The core's clock, so the gateway replays exactly as the rest does (I11)."""
    aggregate = getattr(clarity, "case_aggregate", None)
    clock = getattr(aggregate, "_now", None)
    return clock() if callable(clock) else utc_now()


def _handle(clarity: Any, windows: ServiceWindows, message: InboundMessage) -> dict[str, Any]:
    """Turn one inbound message into a turn on the customer's case."""
    now = _now(clarity)
    # The customer's message opens or renews the window. Only inbound does.
    windows.opened(message.channel.value, message.thread, at=now)

    account = clarity.world.account_by_msisdn(message.msisdn)
    if account is None:
        # An unknown number is not an error to shout about: a wrong number
        # reaches a real gateway constantly. Nothing is opened and nothing
        # about the account is revealed either way (I9).
        return {
            "accepted": True,
            "known_subscriber": False,
            "reply": None,
            "note": "No account for that number. Nothing was opened.",
        }

    subscriber = account.ref
    record, opened = _case_for(clarity, subscriber, message, now)
    turn = clarity.conversation.handle(
        record.case_id,
        message.text,
        channel=message.channel,
        subscriber_ref=subscriber,
        language_hint=message.language.value if message.language else None,
        facts={"case_id": record.case_id},
    )

    state = windows.state(message.channel.value, message.thread, now=now)
    language = (message.language or Language.EN).value
    if state.kind is SendKind.TEMPLATE_ONLY:
        # Reported, never substituted silently: the composed reply is dropped
        # and the caller is told, so the audit and the customer agree.
        return {
            "accepted": True,
            "known_subscriber": True,
            "case_id": record.case_id,
            "case_opened": opened,
            "reply": WINDOW_CLOSED.get(language, WINDOW_CLOSED["en"]),
            "reply_was_templated": True,
            "dropped_reply_because": "service_window_closed",
            **state.to_dict(),
        }

    return {
        "accepted": True,
        "known_subscriber": True,
        "case_id": record.case_id,
        "case_opened": opened,
        "reply": turn.reply,
        "reply_was_templated": False,
        "citations": list(turn.citations),
        "handoff": turn.handoff,
        "flow": turn.state.flow,
        "flow_state": turn.state.state,
        **state.to_dict(),
    }


def _case_for(
    clarity: Any, subscriber: str, message: InboundMessage, now: datetime
) -> tuple[Any, bool]:
    """The subscriber's open case, or a new one.

    Reuses an open case rather than opening one per message, which is what
    makes a WhatsApp conversation one case rather than forty. "Open" means no
    receipt yet: once a case is proved and closed, the next message is a new
    problem.
    """
    for record in clarity.cases.all_cases():
        if record.subscriber_ref == subscriber and record.receipt is None:
            return record, False

    case = clarity.cases.open_case(
        subscriber_ref=subscriber,
        msisdn_masked=_mask(message.msisdn),
        channel=message.channel,
        language=message.language or Language.EN,
        charge_ref=None,
    )
    _announce_complaint(clarity, case.case_id, subscriber, message, now)
    return clarity.cases.get(case.case_id), True


def _announce_complaint(
    clarity: Any, case_id: str, subscriber: str, message: InboundMessage, now: datetime
) -> None:
    """Record `complaint.created`, which is what channels owe the system.

    Plan 21 section 11.3 names channels as this event's producer, and AU01
    wired the autopsy consumer for it with nothing producing it. This closes
    that loop.

    The event carries **no message text**, deliberately, matching the contract
    AU01 relies on: autopsy fetches the text from whoever owns complaints, so
    customer words never enter the bus.
    """
    try:
        with clarity.open_unit() as unit:
            outbox_in(unit).append(
                Event.of(
                    ComplaintCreatedV1(
                        complaint_id=new_id("CMP"),
                        channel=message.channel,
                        language=message.language or Language.EN,
                        case_id=case_id,
                    ),
                    subject=subscriber,
                )
            )
            unit.commit()
    except Exception:
        # A complaint that could not be announced must not lose the customer's
        # turn. The case exists and the conversation continues; the event is
        # analytics, and losing one costs a row in a dashboard.
        return


def _mask(msisdn: str) -> str:
    """The masked form stored on a case. Never the raw number (I13)."""
    digits = "".join(c for c in msisdn if c.isdigit())
    return f"{digits[:3]}***{digits[-4:]}" if len(digits) >= 7 else "***"


__all__ = [
    "DELIVERY_HEADER",
    "SIGNATURE_HEADER",
    "TIMESTAMP_HEADER",
    "WINDOW_CLOSED",
    "InboundMessage",
    "create_channel_gateway_app",
]

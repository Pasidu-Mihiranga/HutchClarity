"""clarity-channel-gateway — WhatsApp / SMS / USSD ingress with simulator drivers."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


class SessionStore:
    """In-memory channel thread → case_id links."""

    def __init__(self) -> None:
        self.by_thread: dict[str, dict[str, Any]] = {}
        self.messages: list[dict[str, Any]] = []

    def link(self, channel: str, thread_id: str, *, msisdn: str, case_id: str | None = None) -> dict[str, Any]:
        key = f"{channel}:{thread_id}"
        entry = self.by_thread.get(key) or {
            "channel": channel,
            "thread_id": thread_id,
            "msisdn": msisdn,
            "case_id": case_id or f"CASE-{uuid.uuid4().hex[:8].upper()}",
            "created_at": _utcnow(),
            "messages": 0,
        }
        if case_id:
            entry["case_id"] = case_id
        entry["msisdn"] = msisdn
        entry["updated_at"] = _utcnow()
        self.by_thread[key] = entry
        return entry

    def record(self, channel: str, thread_id: str, direction: str, text: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        key = f"{channel}:{thread_id}"
        session = self.by_thread.get(key)
        if session is None:
            raise KeyError(key)
        session["messages"] = int(session.get("messages", 0)) + 1
        msg = {
            "id": str(uuid.uuid4()),
            "channel": channel,
            "thread_id": thread_id,
            "case_id": session["case_id"],
            "msisdn": session["msisdn"],
            "direction": direction,
            "text": text,
            "at": _utcnow(),
            **(extra or {}),
        }
        self.messages.append(msg)
        return msg


class SimulatorDriver:
    """Local WhatsApp / SMS / USSD simulator — always available."""

    name = "simulator"

    def handle_whatsapp(self, payload: dict[str, Any], store: SessionStore) -> dict[str, Any]:
        msisdn = str(payload.get("from") or payload.get("msisdn") or "+94770000000")
        text = str(payload.get("text") or payload.get("body") or "")
        thread_id = str(payload.get("thread_id") or payload.get("wa_id") or msisdn)
        case_id = payload.get("case_id")
        session = store.link("whatsapp", thread_id, msisdn=msisdn, case_id=case_id)
        inbound = store.record("whatsapp", thread_id, "inbound", text, {"driver": self.name})
        reply = f"[sim/whatsapp] Got it. Case {session['case_id']}. Reply WHY for an explanation."
        outbound = store.record("whatsapp", thread_id, "outbound", reply, {"driver": self.name})
        return {
            "ok": True,
            "driver": self.name,
            "session": session,
            "inbound": inbound,
            "outbound": outbound,
        }

    def handle_ussd(self, payload: dict[str, Any], store: SessionStore) -> dict[str, Any]:
        msisdn = str(payload.get("msisdn") or "+94770000000")
        text = str(payload.get("input") or payload.get("text") or "")
        session_id = str(payload.get("session_id") or uuid.uuid4().hex)
        thread_id = session_id
        session = store.link("ussd", thread_id, msisdn=msisdn, case_id=payload.get("case_id"))
        store.record("ussd", thread_id, "inbound", text, {"driver": self.name})
        menu = (
            "CON Hutch Clarity\n"
            "1. Why was I charged?\n"
            "2. Open case status\n"
            "3. Talk to agent\n"
            f"Case: {session['case_id']}"
        )
        if text.strip() in {"1", "WHY", "why"}:
            menu = f"END Case {session['case_id']}: checking your last charge. Open the app for details."
        elif text.strip() in {"2"}:
            menu = f"END Case {session['case_id']} is open."
        elif text.strip() in {"3"}:
            menu = f"END Connecting you to an agent for {session['case_id']}."
        store.record("ussd", thread_id, "outbound", menu, {"driver": self.name})
        return {
            "ok": True,
            "driver": self.name,
            "session_id": session_id,
            "session": session,
            "ussd_response": menu,
        }

    def handle_sms(self, payload: dict[str, Any], store: SessionStore) -> dict[str, Any]:
        msisdn = str(payload.get("from") or payload.get("msisdn") or "+94770000000")
        text = str(payload.get("text") or payload.get("body") or "")
        thread_id = str(payload.get("thread_id") or msisdn)
        session = store.link("sms", thread_id, msisdn=msisdn, case_id=payload.get("case_id"))
        inbound = store.record("sms", thread_id, "inbound", text, {"driver": self.name})
        reply = f"[sim/sms] Clarity case {session['case_id']}. Text WHY for details."
        outbound = store.record("sms", thread_id, "outbound", reply, {"driver": self.name})
        return {
            "ok": True,
            "driver": self.name,
            "session": session,
            "inbound": inbound,
            "outbound": outbound,
        }


class MetaCloudDriver:
    """Meta Cloud API stub — enabled when WHATSAPP_TOKEN is set."""

    name = "meta-cloud"

    def __init__(self, token: str) -> None:
        self.token = token

    def handle_whatsapp(self, payload: dict[str, Any], store: SessionStore) -> dict[str, Any]:
        # Stub: accept webhook shape, route through the same session store, pretend send.
        entry = (payload.get("entry") or [{}])[0]
        changes = (entry.get("changes") or [{}])[0]
        value = changes.get("value") or payload
        messages = value.get("messages") or []
        contacts = value.get("contacts") or [{}]
        if messages:
            msg = messages[0]
            msisdn = str(msg.get("from") or contacts[0].get("wa_id") or "+94770000000")
            text = str((msg.get("text") or {}).get("body") or msg.get("body") or "")
            thread_id = str(msg.get("id") or msisdn)
        else:
            msisdn = str(payload.get("from") or "+94770000000")
            text = str(payload.get("text") or "")
            thread_id = str(payload.get("thread_id") or msisdn)
        session = store.link("whatsapp", thread_id, msisdn=msisdn, case_id=payload.get("case_id"))
        inbound = store.record(
            "whatsapp",
            thread_id,
            "inbound",
            text,
            {"driver": self.name, "token_present": bool(self.token)},
        )
        reply = f"[meta-stub] Ack for case {session['case_id']}"
        outbound = store.record(
            "whatsapp",
            thread_id,
            "outbound",
            reply,
            {"driver": self.name, "would_call": "graph.facebook.com"},
        )
        return {
            "ok": True,
            "driver": self.name,
            "session": session,
            "inbound": inbound,
            "outbound": outbound,
            "meta_send_stubbed": True,
        }


class WhatsAppWebhook(BaseModel):
    model_config = ConfigDict(extra="allow")

    from_: str | None = Field(default=None, alias="from")
    msisdn: str | None = None
    text: str | None = None
    body: str | None = None
    thread_id: str | None = None
    wa_id: str | None = None
    case_id: str | None = None
    entry: list[dict[str, Any]] | None = None


class UssdSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    msisdn: str
    session_id: str | None = None
    input: str = ""
    text: str | None = None
    case_id: str | None = None


class SmsInbound(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_: str | None = Field(default=None, alias="from")
    msisdn: str | None = None
    text: str = ""
    body: str | None = None
    thread_id: str | None = None
    case_id: str | None = None


def create_app() -> FastAPI:
    app = FastAPI(title="clarity-channel-gateway", version="0.1.0")
    store = SessionStore()
    simulator = SimulatorDriver()
    token = os.environ.get("WHATSAPP_TOKEN", "")
    meta = MetaCloudDriver(token) if token else None
    app.state.store = store
    app.state.simulator = simulator
    app.state.meta = meta

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "channel-gateway",
            "drivers": {
                "simulator": True,
                "meta_cloud": bool(meta),
            },
            "sessions": len(store.by_thread),
        }

    @app.post("/v1/channels/whatsapp/webhook")
    def whatsapp_webhook(body: WhatsAppWebhook) -> dict[str, Any]:
        payload = body.model_dump(by_alias=True, exclude_none=True)
        if meta is not None and body.entry is not None:
            return meta.handle_whatsapp(payload, store)
        if meta is not None and os.environ.get("WHATSAPP_PREFER_META", "").lower() in {
            "1",
            "true",
            "yes",
        }:
            return meta.handle_whatsapp(payload, store)
        return simulator.handle_whatsapp(payload, store)

    @app.post("/v1/channels/ussd/session")
    def ussd_session(body: UssdSession) -> dict[str, Any]:
        payload = body.model_dump(exclude_none=True)
        if body.text and not body.input:
            payload["input"] = body.text
        return simulator.handle_ussd(payload, store)

    @app.post("/v1/channels/sms/inbound")
    def sms_inbound(body: SmsInbound) -> dict[str, Any]:
        payload = body.model_dump(by_alias=True, exclude_none=True)
        if body.body and not body.text:
            payload["text"] = body.body
        msisdn = payload.get("from") or payload.get("msisdn")
        if not msisdn:
            raise HTTPException(status_code=400, detail="msisdn or from required")
        return simulator.handle_sms(payload, store)

    @app.get("/v1/sessions")
    def list_sessions() -> dict[str, Any]:
        return {"sessions": list(store.by_thread.values()), "message_count": len(store.messages)}

    return app


app = create_app()

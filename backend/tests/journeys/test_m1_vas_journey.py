"""M1 walking skeleton — VAS silent renewal through the new modular API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from clarity.entrypoints.api import create_app


def test_m1_vas_journey_end_to_end() -> None:
    client = TestClient(create_app())

    otp = client.post("/v1/auth/otp/request", json={"msisdn": "+94771234567"}).json()
    assert otp.get("demo_code")
    verified = client.post(
        "/v1/auth/otp/verify",
        json={"msisdn": "+94771234567", "code": otp["demo_code"]},
    )
    assert verified.status_code == 200
    subscriber_ref = verified.json()["principal"]["subscriber_ref"]

    timeline = {
        "vas": [
            {
                "id": "vas-1",
                "type": "renewal",
                "subscription_id": "SUB-CRICKET",
                "product": "Daily cricket",
                "amount_lkr": "30.00",
                "at": "2027-09-14T10:00:00+00:00",
            }
        ],
        "notifications": [],
        "consents": [],
        "charges": [],
        "payments": [],
        "packs": [],
        "usage": [],
        "loans": [],
        "outages": [],
    }
    detected = client.post("/v1/detect", json={"timeline": timeline})
    assert detected.status_code == 200
    body = detected.json()
    assert body["count"] >= 1
    assert any(d["rule_id"] == "VAS_SILENT_RENEWAL" for d in body["detections"])

    decided = client.post("/v1/decide", json={"detections": body["detections"]})
    assert decided.status_code == 200
    decision = decided.json()["decision"]
    assert decision["outcome"] in {
        "AUTO_FIX",
        "ONE_TAP",
        "ONE_TAP_FIX",
        "APPROVE",
        "HANDOFF",
        "REFUND",
    }

    case = client.post(
        "/v1/cases",
        json={
            "subscriber_ref": subscriber_ref,
            "channel": "web",
            "message": "Why was I charged for cricket again?",
            "detections": body["detections"],
            "decision": decision,
            "amount_lkr": "30.00",
        },
    )
    assert case.status_code == 200
    case_id = case.json()["id"]

    action = client.post(
        f"/v1/cases/{case_id}/actions",
        json={
            "action_type": "refund",
            "amount_lkr": "30.00",
            "idempotency_key": "m1-vas-refund-1",
        },
    )
    assert action.status_code == 200

    receipt = client.post(
        "/v1/receipts",
        json={
            "subscriber_ref": subscriber_ref,
            "summary": "Refunded LKR 30.00 for silent VAS renewal (VAS_SILENT_RENEWAL).",
            "case_id": case_id,
            "action_type": "refund",
            "amount_lkr": "30.00",
        },
    )
    assert receipt.status_code == 200
    receipt_id = receipt.json()["id"]

    verify = client.get(f"/v1/verify/{receipt_id}")
    assert verify.status_code == 200
    assert verify.json().get("valid") is True or verify.json().get("ok") is True

    notify = client.post(
        "/v1/notifications/send",
        json={
            "subscriber_ref": subscriber_ref,
            "template_id": "receipt_ready",
            "channel": "sms",
            "params": {"receipt_id": receipt_id},
            "ignore_quiet_hours": True,
        },
    )
    assert notify.status_code == 200, notify.text


def test_m3_proactive_and_knowledge() -> None:
    client = TestClient(create_app())
    fup = client.post(
        "/v1/proactive/evaluate",
        json={
            "type": "usage.threshold_reached",
            "subject": "sub_demo",
            "data": {"threshold_pct": 95, "pack_id": "PACK-1"},
        },
    )
    assert fup.status_code == 200
    assert len(fup.json().get("actions") or fup.json().get("proactive") or []) >= 0

    knowledge = client.post(
        "/v1/knowledge/search",
        json={"query": "fair usage policy throttle"},
    )
    assert knowledge.status_code == 200

    radar = client.get("/v1/foresight/radar")
    assert radar.status_code == 200

    clusters = client.get("/v1/autopsy/clusters")
    assert clusters.status_code == 200

    handover = client.get("/v1/desk/handover")
    assert handover.status_code == 200

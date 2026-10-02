"""hutch-sim — synthetic HUTCH world + scenario control panel."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


DILANI_MSISDN = "+94771234567"


def seed_dilani(now: datetime | None = None) -> dict[str, Any]:
    """Seed a Dilani-like prepaid customer with VAS / pack / payment history."""
    now = now or _utcnow()
    charged_at = now.replace(hour=14, minute=6, second=0, microsecond=0)
    return {
        "msisdn": DILANI_MSISDN,
        "name": "Dilani Perera",
        "language": "si",
        "balance_lkr": "451.00",
        "onboarded": True,
        "notify": "important",
        "refunds_last_30d": 1,
        "safeguards": {
            "spend_cap": {"value": "500"},
            "data_on_expiry": {"value": "stop"},
            "network": {"status": "clear", "text": "No outage in your area right now."},
        },
        "subscriptions": [
            {
                "subscription_id": "SUB-GAME-1",
                "merchant_id": "MER-GAMEHUB",
                "merchant_name": "GameHub",
                "product": "Daily game subscription",
                "price_lkr": "49.00",
                "otp_verified_at": None,
            },
            {
                "subscription_id": "SUB-NEWS-1",
                "merchant_id": "MER-NEWSBYTE",
                "merchant_name": "NewsByte",
                "product": "Daily headlines",
                "price_lkr": "19.00",
                "otp_verified_at": _iso(now - timedelta(days=20)),
            },
        ],
        "packs": [
            {
                "offering_id": "PKG-ANY-10",
                "name": "Anytime 10GB",
                "price_lkr": "799.00",
                "purchased_at": _iso(now - timedelta(days=12)),
                "expires_at": _iso(now + timedelta(days=18)),
                "fup_cap_gb": "10.00",
                "after_cap_speed": "512 kbps",
                "active": True,
                "used_gb": "9.2",
            }
        ],
        "events": [
            {
                "id": "EVT-PAY-1",
                "source": "payments",
                "type": "PAYMENT_CAPTURED",
                "at": _iso(now - timedelta(days=5)),
                "amount_lkr": "500.00",
            },
            {
                "id": "EVT-VAS-1",
                "source": "vas",
                "type": "VAS_CHARGED",
                "at": _iso(charged_at),
                "amount_lkr": "49.00",
                "merchant_id": "MER-GAMEHUB",
                "subscription_id": "SUB-GAME-1",
            },
            {
                "id": "EVT-BAL-1",
                "source": "billing",
                "type": "BALANCE_DEBIT",
                "at": _iso(charged_at),
                "amount_lkr": "49.00",
                "reason": "vas_renewal",
            },
        ],
        "cases": [
            {
                "case_id": "CASE-DEMO-001",
                "status": "open",
                "cause_hint": "vas_silent_renewal",
                "opened_at": _iso(charged_at + timedelta(minutes=12)),
            }
        ],
    }


SCENARIO_CATALOGUE: list[dict[str, Any]] = [
    {
        "id": "vas-surprise",
        "title": "VAS charged without consent",
        "description": "Dilani sees −LKR 49 GameHub debit with no OTP.",
        "msisdn": DILANI_MSISDN,
        "tags": ["vas", "why"],
    },
    {
        "id": "fup-throttle",
        "title": "FUP surprise throttle",
        "description": "Pack at 92% usage; speed drops after cap.",
        "msisdn": DILANI_MSISDN,
        "tags": ["fup", "pack"],
    },
    {
        "id": "double-reload",
        "title": "Duplicate reload window",
        "description": "Two reloads within 30 minutes — settlement check.",
        "msisdn": DILANI_MSISDN,
        "tags": ["payments"],
    },
]


class World:
    def __init__(self) -> None:
        self.customers: dict[str, dict[str, Any]] = {}
        self.scenarios: dict[str, dict[str, Any]] = {
            s["id"]: dict(s) for s in SCENARIO_CATALOGUE
        }
        self.runs: list[dict[str, Any]] = []
        self.seed()

    def seed(self) -> None:
        dilani = seed_dilani()
        self.customers[dilani["msisdn"]] = dilani

    def generate_events(self, msisdn: str, *, count: int = 3, kind: str = "synthetic") -> list[dict[str, Any]]:
        customer = self.customers.get(msisdn)
        if customer is None:
            raise KeyError(msisdn)
        now = _utcnow()
        generated: list[dict[str, Any]] = []
        for i in range(count):
            evt = {
                "id": f"EVT-SYN-{uuid.uuid4().hex[:8].upper()}",
                "source": "hutch-sim",
                "type": kind.upper() if kind.isalpha() else "SYNTHETIC_TICK",
                "at": _iso(now - timedelta(minutes=i)),
                "amount_lkr": None,
                "note": f"synthetic event {i + 1}",
            }
            customer.setdefault("events", []).append(evt)
            generated.append(evt)
        return generated


class ScenarioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    title: str
    description: str = ""
    msisdn: str = DILANI_MSISDN
    tags: list[str] = Field(default_factory=list)


class ScenarioRunBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generate_events: int = Field(default=2, ge=0, le=50)
    kind: str = "scenario"


def create_app() -> FastAPI:
    app = FastAPI(title="hutch-sim", version="0.1.0")
    world = World()
    app.state.world = world

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "hutch-sim",
            "customers": len(world.customers),
            "scenarios": len(world.scenarios),
        }

    @app.get("/v1/scenarios")
    def list_scenarios() -> dict[str, Any]:
        return {"scenarios": list(world.scenarios.values())}

    @app.post("/v1/scenarios")
    def create_scenario(body: ScenarioCreate) -> dict[str, Any]:
        sid = body.id or f"scn-{uuid.uuid4().hex[:8]}"
        if sid in world.scenarios:
            raise HTTPException(status_code=409, detail=f"scenario {sid} exists")
        scenario = {
            "id": sid,
            "title": body.title,
            "description": body.description,
            "msisdn": body.msisdn,
            "tags": body.tags,
        }
        world.scenarios[sid] = scenario
        return {"scenario": scenario}

    @app.post("/v1/scenarios/{scenario_id}/run")
    def run_scenario(scenario_id: str, body: ScenarioRunBody | None = None) -> dict[str, Any]:
        scenario = world.scenarios.get(scenario_id)
        if scenario is None:
            raise HTTPException(status_code=404, detail="scenario not found")
        body = body or ScenarioRunBody()
        msisdn = scenario["msisdn"]
        if msisdn not in world.customers:
            world.customers[msisdn] = seed_dilani()
            world.customers[msisdn]["msisdn"] = msisdn
        events = world.generate_events(msisdn, count=body.generate_events, kind=body.kind)
        # Tag scenario-specific synthetic state
        customer = world.customers[msisdn]
        if scenario_id == "vas-surprise":
            customer["last_scenario"] = "vas-surprise"
        elif scenario_id == "fup-throttle" and customer.get("packs"):
            customer["packs"][0]["used_gb"] = "9.4"
            customer["packs"][0]["throttle"] = True
        elif scenario_id == "double-reload":
            customer.setdefault("events", []).append(
                {
                    "id": f"EVT-PAY-{uuid.uuid4().hex[:6].upper()}",
                    "source": "payments",
                    "type": "PAYMENT_CAPTURED",
                    "at": _iso(_utcnow()),
                    "amount_lkr": "500.00",
                    "note": "duplicate reload candidate",
                }
            )
        run = {
            "run_id": str(uuid.uuid4()),
            "scenario_id": scenario_id,
            "msisdn": msisdn,
            "generated_events": events,
            "at": _iso(_utcnow()),
        }
        world.runs.append(run)
        return {"run": run, "world": deepcopy(customer)}

    @app.get("/v1/world/{msisdn}")
    def get_world(msisdn: str) -> dict[str, Any]:
        # Accept with or without +
        key = msisdn if msisdn.startswith("+") else f"+{msisdn}"
        alt = msisdn.lstrip("+")
        customer = world.customers.get(key) or world.customers.get(f"+{alt}")
        if customer is None:
            # try bare match
            for k, v in world.customers.items():
                if k.replace("+", "") == alt:
                    customer = v
                    break
        if customer is None:
            raise HTTPException(status_code=404, detail="msisdn not in world")
        return {"customer": deepcopy(customer)}

    @app.post("/v1/world/{msisdn}/events")
    def synth_events(msisdn: str, count: int = 3) -> dict[str, Any]:
        key = msisdn if msisdn.startswith("+") else f"+{msisdn}"
        if key not in world.customers and f"+{msisdn.lstrip('+')}" in world.customers:
            key = f"+{msisdn.lstrip('+')}"
        try:
            events = world.generate_events(key, count=count)
        except KeyError as err:
            raise HTTPException(status_code=404, detail="msisdn not in world") from err
        return {"events": events}

    return app


app = create_app()

"""clarity-ai-gateway — role-based completions with drivers, quotas, cassettes."""

from __future__ import annotations

import hashlib
import json
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

ROLES = ("fast-text", "extract", "reason", "judge", "guard", "embed", "stt", "tts")
REPO_ROOT = Path(__file__).resolve().parents[3]
MODELS_YAML = REPO_ROOT / "config" / "ai" / "models.yaml"
_MONEY = re.compile(
    r"(?:LKR|Rs\.?|රු)\s*[\d,]+(?:\.\d+)?|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+\.\d{2}\b",
    re.IGNORECASE,
)


def _repo_cassette_dir() -> Path:
    raw = os.environ.get("AI_CASSETTE_DIR", "cassettes")
    path = Path(raw)
    return path if path.is_absolute() else REPO_ROOT / path


def load_models_config() -> dict[str, Any]:
    if not MODELS_YAML.exists():
        raise FileNotFoundError(f"models.yaml not found at {MODELS_YAML}")
    with MODELS_YAML.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data


class CompleteMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    synthetic: bool | None = None
    cassette: str | None = None


class CompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    prompt: str = ""
    facts: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    language: str = "en"
    meta: CompleteMeta = Field(default_factory=CompleteMeta)


class QuotaBucket:
    """Simple in-memory counters per role."""

    def __init__(self) -> None:
        self.calls: dict[str, int] = {r: 0 for r in ROLES}
        self.tokens_in: dict[str, int] = {r: 0 for r in ROLES}
        self.tokens_out: dict[str, int] = {r: 0 for r in ROLES}
        self.fallbacks: dict[str, int] = {r: 0 for r in ROLES}

    def record(self, role: str, *, tin: int = 0, tout: int = 0, fallback: bool = False) -> None:
        self.calls[role] = self.calls.get(role, 0) + 1
        self.tokens_in[role] = self.tokens_in.get(role, 0) + tin
        self.tokens_out[role] = self.tokens_out.get(role, 0) + tout
        if fallback:
            self.fallbacks[role] = self.fallbacks.get(role, 0) + 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "calls": dict(self.calls),
            "tokens_in": dict(self.tokens_in),
            "tokens_out": dict(self.tokens_out),
            "fallbacks": dict(self.fallbacks),
        }


def _facts_amounts(facts: dict[str, Any]) -> set[Decimal]:
    amounts: set[Decimal] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                key = str(k).lower()
                if any(t in key for t in ("amount", "lkr", "price", "balance", "refund", "charge")):
                    try:
                        amounts.add(Decimal(str(v).replace(",", "")))
                    except (InvalidOperation, ValueError, TypeError):
                        pass
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, (int, float, Decimal)):
            amounts.add(Decimal(str(node)))
        elif isinstance(node, str):
            try:
                amounts.add(Decimal(node.replace(",", "")))
            except (InvalidOperation, ValueError):
                pass

    walk(facts)
    return amounts


def verify_no_invented_money(text: str, facts: dict[str, Any]) -> list[str]:
    """Reject money amounts in the response that are not present in FACTS."""
    known = _facts_amounts(facts)
    issues: list[str] = []
    for match in _MONEY.finditer(text):
        raw = re.sub(r"(?:LKR|Rs\.?|රු)\s*", "", match.group(), flags=re.IGNORECASE)
        raw = raw.replace(",", "").strip()
        try:
            value = Decimal(raw)
        except (InvalidOperation, ValueError):
            continue
        if value not in known:
            issues.append(f"invented amount {match.group()!r} not in FACTS")
    return issues


def template_driver(role: str, prompt: str, facts: dict[str, Any], language: str) -> dict[str, Any]:
    rule = facts.get("rule_id") or facts.get("cause") or "unknown"
    amount = facts.get("amount_lkr") or facts.get("amount")
    amount_s = f" LKR {amount}" if amount is not None else ""
    templates = {
        "en": f"[template/{role}] Based on the facts, {rule} explains the charge{amount_s}.",
        "si": f"[template/{role}] කරුණු අනුව {rule} නිසා අයකිරීම{amount_s} සිදු විය.",
        "ta": f"[template/{role}] உண்மைகளின்படி {rule} காரணமாக{amount_s} வசூலிக்கப்பட்டது.",
    }
    text = templates.get(language, templates["en"])
    if prompt.strip():
        text = f"{text} (re: {prompt[:80]})"
    return {
        "text": text,
        "provider": "template",
        "model": "local-template",
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


def gemini_driver(role: str, prompt: str, facts: dict[str, Any], language: str, model: str) -> dict[str, Any] | None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            f"Role={role} language={language}. "
                            "State only values from FACTS. Never invent money amounts.\n"
                            f"FACTS:\n{json.dumps(facts)}\n\nPROMPT:\n{prompt}"
                        )
                    }
                ]
            }
        ]
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts)
        usage_meta = data.get("usageMetadata", {})
        return {
            "text": text,
            "provider": "gemini",
            "model": model,
            "usage": {
                "input_tokens": int(usage_meta.get("promptTokenCount", 0)),
                "output_tokens": int(usage_meta.get("candidatesTokenCount", 0)),
            },
        }
    except Exception:
        return None


def groq_driver(role: str, prompt: str, facts: dict[str, Any], language: str, model: str) -> dict[str, Any] | None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    messages = [
        {
            "role": "system",
            "content": (
                f"You are Clarity AI role={role}, language={language}. "
                "State only values from FACTS. Never invent money amounts."
            ),
        },
        {
            "role": "user",
            "content": f"FACTS:\n{json.dumps(facts)}\n\nPROMPT:\n{prompt}",
        },
    ]
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": messages, "temperature": 0.2},
            )
            resp.raise_for_status()
            data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return {
            "text": text,
            "provider": "groq",
            "model": model,
            "usage": {
                "input_tokens": int(usage.get("prompt_tokens", 0)),
                "output_tokens": int(usage.get("completion_tokens", 0)),
            },
        }
    except Exception:
        return None


def _cassette_key(req: CompleteRequest) -> str:
    payload = {
        "role": req.role,
        "prompt": req.prompt,
        "facts": req.facts,
        "context": req.context,
        "language": req.language,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return digest


def cassette_load(key: str) -> dict[str, Any] | None:
    path = _repo_cassette_dir() / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def cassette_save(key: str, result: dict[str, Any]) -> None:
    directory = _repo_cassette_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{key}.json"
    path.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")


def _chain_for_role(cfg: dict[str, Any], role: str) -> list[dict[str, str]]:
    roles = cfg.get("roles") or {}
    entry = roles.get(role) or {}
    chain: list[dict[str, str]] = []
    primary = entry.get("primary")
    if isinstance(primary, dict) and primary.get("provider"):
        chain.append({"provider": str(primary["provider"]), "model": str(primary.get("model", ""))})
    for fb in entry.get("fallback") or []:
        if isinstance(fb, dict) and fb.get("provider"):
            chain.append({"provider": str(fb["provider"]), "model": str(fb.get("model", ""))})
    if not chain:
        chain.append({"provider": "template", "model": "local-template"})
    return chain


def _live_keys_present() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GROQ_API_KEY"))


def complete(req: CompleteRequest, cfg: dict[str, Any], quota: QuotaBucket) -> dict[str, Any]:
    if req.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"unknown role: {req.role}")

    synthetic_only = os.environ.get("AI_SYNTHETIC_ONLY", "").lower() in {"1", "true", "yes"}
    if synthetic_only and _live_keys_present() and req.meta.synthetic is not True:
        raise HTTPException(
            status_code=403,
            detail="AI_SYNTHETIC_ONLY requires meta.synthetic=true when live keys are set",
        )

    key = _cassette_key(req)
    replay = cassette_load(key)
    if replay is not None:
        quota.record(req.role, tin=replay.get("usage", {}).get("input_tokens", 0),
                     tout=replay.get("usage", {}).get("output_tokens", 0))
        return {**replay, "cassette": "replay", "role": req.role}

    result: dict[str, Any] | None = None
    used_fallback = False
    for i, step in enumerate(_chain_for_role(cfg, req.role)):
        provider = step["provider"]
        model = step["model"]
        if provider in {"template", "local-bge"}:
            result = template_driver(req.role, req.prompt, req.facts, req.language)
            if i > 0:
                used_fallback = True
            break
        if provider == "gemini":
            result = gemini_driver(req.role, req.prompt, req.facts, req.language, model)
        elif provider == "groq":
            result = groq_driver(req.role, req.prompt, req.facts, req.language, model)
        else:
            result = None
        if result is not None:
            if i > 0:
                used_fallback = True
            break

    if result is None:
        result = template_driver(req.role, req.prompt, req.facts, req.language)
        used_fallback = True

    issues = verify_no_invented_money(result["text"], req.facts)
    if issues:
        result = template_driver(req.role, req.prompt, req.facts, req.language)
        result["verified"] = False
        result["verifier_issues"] = issues
        used_fallback = True
    else:
        result["verified"] = True
        result["verifier_issues"] = []

    result["role"] = req.role
    result["fallback"] = used_fallback
    cassette_save(key, result)
    result["cassette"] = "record"
    usage = result.get("usage") or {}
    quota.record(
        req.role,
        tin=int(usage.get("input_tokens", 0)),
        tout=int(usage.get("output_tokens", 0)),
        fallback=used_fallback,
    )
    return result


def create_app() -> FastAPI:
    app = FastAPI(title="clarity-ai-gateway", version="0.1.0")
    cfg = load_models_config()
    quota = QuotaBucket()
    app.state.cfg = cfg
    app.state.quota = quota

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "ai-gateway",
            "roles": list(ROLES),
            "models_yaml": str(MODELS_YAML),
            "gemini_key": bool(os.environ.get("GEMINI_API_KEY")),
            "groq_key": bool(os.environ.get("GROQ_API_KEY")),
            "synthetic_only": os.environ.get("AI_SYNTHETIC_ONLY", "").lower()
            in {"1", "true", "yes"},
        }

    @app.post("/v1/complete")
    def v1_complete(body: CompleteRequest) -> dict[str, Any]:
        return complete(body, app.state.cfg, app.state.quota)

    @app.get("/v1/usage")
    def v1_usage() -> dict[str, Any]:
        return app.state.quota.snapshot()

    return app


app = create_app()

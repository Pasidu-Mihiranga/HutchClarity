"""clarity-signer — Ed25519 sign/verify for receipt payload hashes."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field


def _keys_dir() -> Path:
    raw = os.environ.get("KEYS_DIR", ".keys")
    path = Path(raw)
    if path.is_absolute():
        return path
    # Prefer CWD; also resolve relative to repo root when launched from services/
    repo = Path(__file__).resolve().parents[3]
    if (repo / path).exists():
        return repo / path
    return path


def load_keypair(keys_dir: Path) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    private_path = keys_dir / "signing.pem"
    public_path = keys_dir / "signing.pub.pem"
    if not private_path.exists():
        raise FileNotFoundError(f"missing private key at {private_path}")
    private_key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("signing.pem is not an Ed25519 private key")
    if public_path.exists():
        public_key = serialization.load_pem_public_key(public_path.read_bytes())
        if not isinstance(public_key, Ed25519PublicKey):
            raise TypeError("signing.pub.pem is not an Ed25519 public key")
    else:
        public_key = private_key.public_key()
    return private_key, public_key


def _hash_bytes(payload_hash: str) -> bytes:
    """Accept hex SHA-256, raw hex of any length, or the payload string itself."""
    cleaned = payload_hash.strip().lower().removeprefix("0x")
    try:
        raw = bytes.fromhex(cleaned)
        if len(raw) == 32:
            return raw
        # Non-32-byte hex: hash the hex string for a stable 32-byte digest
        return hashlib.sha256(cleaned.encode()).digest()
    except ValueError:
        return hashlib.sha256(payload_hash.encode()).digest()


class SignBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload_hash: str = Field(min_length=1)


class VerifyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload_hash: str = Field(min_length=1)
    signature: str = Field(min_length=1)


def create_app() -> FastAPI:
    app = FastAPI(title="clarity-signer", version="0.1.0")
    keys_dir = _keys_dir()
    try:
        private_key, public_key = load_keypair(keys_dir)
        load_error: str | None = None
    except Exception as exc:  # noqa: BLE001 — surface boot status via /health
        private_key = None
        public_key = None
        load_error = str(exc)
    app.state.private_key = private_key
    app.state.public_key = public_key
    app.state.keys_dir = str(keys_dir)
    app.state.load_error = load_error

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok" if private_key is not None else "degraded",
            "service": "signer",
            "keys_dir": str(keys_dir),
            "key_loaded": private_key is not None,
            "error": load_error,
        }

    @app.post("/v1/sign")
    def sign(body: SignBody) -> dict[str, Any]:
        if private_key is None:
            raise HTTPException(status_code=503, detail=load_error or "key not loaded")
        digest = _hash_bytes(body.payload_hash)
        signature = private_key.sign(digest)
        return {
            "payload_hash": body.payload_hash,
            "signature": base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii"),
            "alg": "Ed25519",
        }

    @app.post("/v1/verify")
    def verify(body: VerifyBody) -> dict[str, Any]:
        if public_key is None:
            raise HTTPException(status_code=503, detail=load_error or "key not loaded")
        digest = _hash_bytes(body.payload_hash)
        pad = "=" * (-len(body.signature) % 4)
        try:
            sig = base64.urlsafe_b64decode(body.signature + pad)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="invalid signature encoding") from exc
        try:
            public_key.verify(sig, digest)
            valid = True
        except InvalidSignature:
            valid = False
        return {
            "payload_hash": body.payload_hash,
            "valid": valid,
            "alg": "Ed25519",
        }

    return app


app = create_app()

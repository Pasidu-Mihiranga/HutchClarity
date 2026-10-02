"""Generate Ed25519 signing keypair into KEYS_DIR (default .keys/).

Writes:
  signing.pem          — private key (PEM, PKCS8)
  signing.pub.pem      — public key (PEM, SubjectPublicKeyInfo)
  clarity-keys.json    — well-known style public key document (kid + base64)

Usage:
  python scripts/keys.py
  KEYS_DIR=.keys python scripts/keys.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> int:
    keys_dir = Path(os.environ.get("KEYS_DIR", ".keys"))
    keys_dir.mkdir(parents=True, exist_ok=True)

    private_path = keys_dir / "signing.pem"
    public_path = keys_dir / "signing.pub.pem"
    well_known_path = keys_dir / "clarity-keys.json"

    if private_path.exists() and "--force" not in sys.argv:
        print(f"refusing to overwrite {private_path} (pass --force to regenerate)", file=sys.stderr)
        return 1

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    private_path.write_bytes(private_pem)
    private_path.chmod(0o600)
    public_path.write_bytes(public_pem)

    kid = "clarity-rcpt-dev"
    document = {
        "keys": [
            {
                "kid": kid,
                "alg": "Ed25519",
                "use": "sig",
                "kty": "OKP",
                "crv": "Ed25519",
                "x": base64.urlsafe_b64encode(public_raw).rstrip(b"=").decode("ascii"),
            }
        ]
    }
    well_known_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {private_path}")
    print(f"wrote {public_path}")
    print(f"wrote {well_known_path} (kid={kid})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

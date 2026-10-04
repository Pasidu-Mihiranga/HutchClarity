"""Encrypted, checksummed audit backups with audited access (plan Phase 6).

A hash chain and signed checkpoints make tampering visible. They do nothing
about *loss*: a dropped table, a failed disk or a bad migration takes the trail
with it, and an append-only store is exactly the kind that cannot be
reconstructed from anywhere else. So the trail is backed up, and the backup is
treated as what it is: a complete copy of who did what, which is as sensitive as
the live table and more portable.

Three properties, and the reason for each.

**Encrypted**, because a backup travels. AES-256-GCM under a key from the
environment, never from the repository (I14). GCM rather than CBC so the
ciphertext is authenticated: a bundle altered in storage fails to decrypt rather
than decrypting into something subtly different.

**Checksummed**, over the plaintext bundle, and verified on read. The GCM tag
already detects a corrupted file, so this is for the other question: that the
bundle which came back is the bundle that was made, by a value a human can read
off two systems and compare. The checksum is also what a restore quotes in its
audit record.

**Audited**, both ways. Creating a backup is recorded, and so is reading one:
restoring is the one operation that can put a different past in place of the
real one, and `backup.read` is how that leaves a mark. The record names the
checksum and the sequence range, never the contents.

**Infrastructure: none new.** A bundle is a file. In ``lite`` it goes wherever
the operator points it; in ``full`` that path is a mounted volume or an object
store, which is a deployment concern and not a dependency of this module.
"""

from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import ClarityModel
from clarity.platform.audit.checkpoints import AUDIT_CHECKPOINTS, Checkpoint
from clarity.platform.audit.ledger import AUDIT, AUDIT_HEAD, AuditRecord
from clarity.platform.persistence import Repository, UnitOfWorkFactory

#: Bundle format. Bumped, never edited: a reader must refuse what it cannot
#: fully understand rather than guess at a missing field.
BUNDLE_VERSION = 1

#: AES-GCM wants 96 bits of nonce. Fresh per write, prefixed to the ciphertext.
_NONCE_BYTES = 12

#: Key length for AES-256.
_KEY_BYTES = 32


class BackupRefused(RuntimeError):
    """A backup could not be written or read, with the reason."""


class BundleTampered(BackupRefused):
    """The bundle that came back is not the bundle that was written."""


class AuditBundle(ClarityModel):
    """One complete copy of the trail and the checkpoints that vouch for it."""

    bundle_version: int = BUNDLE_VERSION
    created_at: datetime
    records: list[AuditRecord]
    checkpoints: list[Checkpoint]
    public_keys: dict[str, str]
    """Published verification material, so a restored bundle can be checked
    without reaching back to the signer that is possibly also gone."""

    head_seq: int
    head_hash: str | None

    @property
    def checksum(self) -> str:
        """Over the canonical form of everything above. Quoted in the audit record."""
        return hash_payload(
            {
                "bundle_version": self.bundle_version,
                "created_at": self.created_at.isoformat(),
                "head_seq": self.head_seq,
                "head_hash": self.head_hash,
                "records": [record.model_dump(mode="json") for record in self.records],
                "checkpoints": [cp.model_dump(mode="json") for cp in self.checkpoints],
                "public_keys": dict(sorted(self.public_keys.items())),
            }
        )

    @property
    def covers(self) -> tuple[int, int]:
        """The ``seq`` range this bundle holds, inclusive. ``(0, 0)`` when empty."""
        if not self.records:
            return (0, 0)
        return (self.records[0].seq, self.records[-1].seq)


def backup_key_from(material: str | None) -> bytes:
    """Derive the AES key from the configured secret.

    SHA-256 of the secret rather than the raw bytes, so any length of secret
    works and a short one does not silently become a short key. A real
    deployment holds a 32-byte random value and this is the identity function in
    all but name; the derivation exists so the ``lite`` profile is usable with a
    passphrase without tempting anyone to pad one by hand.
    """
    if not material:
        raise BackupRefused(
            "no audit backup key is configured: set CLARITY_AUDIT_BACKUP_KEY. "
            "A backup of the audit trail is never written in the clear."
        )
    return hashlib.sha256(material.encode("utf-8")).digest()[:_KEY_BYTES]


def seal(bundle: AuditBundle, key: bytes) -> bytes:
    """Encrypt a bundle. The checksum travels outside the ciphertext, in the clear.

    Deliberately: a restore needs to state which bundle it is about *before* it
    can decrypt one, and an operator comparing two systems should not need the
    key to do it. The checksum reveals nothing, being a hash over data nobody
    can enumerate.
    """
    payload = bundle.model_dump_json().encode("utf-8")
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, payload, bundle.checksum.encode("utf-8"))
    header = f"clarity-audit-backup\nv{BUNDLE_VERSION}\n{bundle.checksum}\n".encode()
    return header + base64.b64encode(nonce + ciphertext)


def unseal(blob: bytes, key: bytes) -> AuditBundle:
    """Decrypt and verify a bundle, or refuse with what was wrong."""
    try:
        head, _, body = blob.partition(b"\n")
        version_line, _, rest = body.partition(b"\n")
        checksum_line, _, encoded = rest.partition(b"\n")
    except ValueError as error:  # pragma: no cover - partition does not raise
        raise BackupRefused(f"not an audit backup: {error}") from error

    if head != b"clarity-audit-backup":
        raise BackupRefused("not an audit backup bundle")
    claimed_version = version_line.decode("utf-8", "replace")
    if claimed_version != f"v{BUNDLE_VERSION}":
        raise BackupRefused(
            f"bundle format {claimed_version} is not {f'v{BUNDLE_VERSION}'}: "
            "a reader must not guess at a format it does not know"
        )
    claimed = checksum_line.decode("utf-8", "replace")

    try:
        raw = base64.b64decode(encoded, validate=True)
        nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        payload = AESGCM(key).decrypt(nonce, ciphertext, claimed.encode("utf-8"))
    except InvalidTag as error:
        raise BundleTampered(
            "the bundle did not authenticate: it was altered, or the checksum "
            "in its header does not belong to it, or the key is wrong"
        ) from error
    except (ValueError, TypeError) as error:
        # Also tampering, not a separate category. A single flipped bit lands on
        # a character outside the base64 alphabet often enough that treating this
        # as "could not be decoded" made an altered bundle raise one of two
        # different exceptions depending on which bit moved, which is how a
        # corruption test came to pass four times out of five.
        raise BundleTampered(
            f"the bundle's body is not intact and could not be decoded: {error}"
        ) from error

    bundle = AuditBundle.model_validate_json(payload)
    if bundle.checksum != claimed:
        # Unreachable while GCM binds the checksum as associated data, which is
        # the point of binding it. Kept because the invariant is the contract,
        # not the mechanism that currently enforces it.
        raise BundleTampered(
            f"the bundle's contents hash to {bundle.checksum}, not the {claimed} it claims"
        )
    return bundle


def bundle_from(open_unit: UnitOfWorkFactory, *, created_at: datetime) -> AuditBundle:
    """Read the whole trail and its checkpoints out of the store."""
    with open_unit() as unit:
        records: Repository[str, AuditRecord] = unit.repository(AUDIT)
        checkpoints: Repository[str, Checkpoint] = unit.repository(AUDIT_CHECKPOINTS)
        heads: Repository[str, dict[str, Any]] = unit.repository(AUDIT_HEAD)
        found = [r for key in sorted(records.keys()) if (r := records.get(key)) is not None]
        signed = [
            c for key in sorted(checkpoints.keys()) if (c := checkpoints.get(key)) is not None
        ]
        head = heads.get("head")
    return AuditBundle(
        created_at=created_at,
        records=found,
        checkpoints=signed,
        public_keys={},
        head_seq=int(head["seq"]) if head else 0,
        head_hash=str(head["chain_hash"]) if head else None,
    )


def write_bundle(bundle: AuditBundle, path: Path, key: bytes) -> str:
    """Seal a bundle to ``path``. Returns its checksum.

    Written to a temporary file in the same directory and renamed, so a failure
    half way through leaves the previous backup rather than a truncated one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_bytes(seal(bundle, key))
    temporary.replace(path)
    return bundle.checksum


def read_bundle(path: Path, key: bytes) -> AuditBundle:
    if not path.exists():
        raise BackupRefused(f"no backup bundle at {path}")
    return unseal(path.read_bytes(), key)


__all__ = [
    "BUNDLE_VERSION",
    "AuditBundle",
    "BackupRefused",
    "BundleTampered",
    "backup_key_from",
    "bundle_from",
    "read_bundle",
    "seal",
    "unseal",
    "write_bundle",
]

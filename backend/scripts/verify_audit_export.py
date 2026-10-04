#!/usr/bin/env python3
"""Verify a Clarity audit export offline (audit assurance plan 5.10, ADR-0039).

Run by whoever received the export, not by Clarity:

    python verify_audit_export.py export.json

It needs the Python standard library and ``cryptography``, and **nothing from
Clarity**. That is the whole point: a verifier that imports the code it is
checking proves only that the code agrees with itself. Everything it needs to
recompute is reimplemented here, from the export's own ``how_to_verify`` field,
and this file can be copied out of the repository and run anywhere.

It exits 0 when the export verifies and 1 when it does not, so it can be a step
in somebody else's pipeline.

What it checks:

- every record's ``detail_hash`` against the canonical hash of its ``detail``;
- every record's ``chain_hash`` against the canonical hash of its other fields;
- for a contiguous export, that each record follows its predecessor;
- every checkpoint's ``statement_hash`` against its fields, and its Ed25519
  signature against the published public key for its ``kid``;
- that a checkpoint whose ``seq`` is in the export matches that record's hash.

What it deliberately does **not** do: treat a selection as a whole. A scoped
export says ``contiguous: false``, and this prints that in the verdict, because a
verifier that read a redacted export as complete would be worse than no verifier.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from typing import Any

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:  # pragma: no cover - the message is the feature
    print("this verifier needs the 'cryptography' package: pip install cryptography")
    raise SystemExit(2) from None

EXPORT_VERSION = 1

#: The record fields that go into the hash, in the order the canonical form sorts
#: them. Listed explicitly rather than taken from the record, so a record carrying
#: an extra field cannot smuggle it past the hash.
HASHED_FIELDS = (
    "hash_version",
    "seq",
    "event_type",
    "actor_ref",
    "actor_kind",
    "session_ref",
    "object_ref",
    "case_id",
    "payload_hash",
    "detail_hash",
    "occurred_at",
    "recorded_at",
    "prev_hash",
)


def canonical_bytes(value: Any) -> bytes:
    """RFC 8785-compatible subset: sorted ASCII keys, no whitespace, UTF-8.

    Matches ``clarity.kernel.canonical``. Floats are refused there and here: a
    canonical form that rounds is not canonical.
    """

    def normalise(item: Any) -> Any:
        if isinstance(item, bool) or item is None or isinstance(item, str | int):
            return item
        if isinstance(item, float):
            raise TypeError("floats are not allowed in a canonical payload")
        if isinstance(item, dict):
            ordered = sorted(item.items(), key=lambda kv: str(kv[0]))
            return {str(key): normalise(value) for key, value in ordered}
        if isinstance(item, list | tuple):
            return [normalise(v) for v in item]
        raise TypeError(f"cannot canonicalize {type(item).__name__}")

    return json.dumps(
        normalise(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def hash_payload(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


def record_hash(record: dict[str, Any]) -> str:
    fields = {name: record.get(name) for name in HASHED_FIELDS}
    fields["prev_hash"] = record.get("prev_hash") or "genesis"
    return hash_payload(fields)


def statement_hash(seq: int, chain_head: str, recorded_at: str) -> str:
    return hash_payload(
        {
            "purpose": "clarity.audit.checkpoint",
            "seq": seq,
            "chain_head": chain_head,
            "recorded_at": recorded_at,
        }
    )


def signature_valid(checkpoint: dict[str, Any], public_keys: dict[str, str]) -> bool:
    encoded = public_keys.get(checkpoint.get("kid", ""))
    if not encoded:
        return False
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded))
        public.verify(
            base64.b64decode(checkpoint["signature"]),
            str(checkpoint["statement_hash"]).encode("utf-8"),
        )
    except (InvalidSignature, ValueError, KeyError, TypeError):
        return False
    return True


def verify(export: dict[str, Any]) -> tuple[bool, list[str], int]:
    problems: list[str] = []
    version = export.get("export_version")
    if version != EXPORT_VERSION:
        return False, [f"export format {version} is not {EXPORT_VERSION}"], 0

    records: list[dict[str, Any]] = export.get("records", [])
    contiguous = bool(export.get("contiguous"))
    keys: dict[str, str] = export.get("public_keys", {})

    previous: dict[str, Any] | None = None
    for record in records:
        where = f"record {record.get('seq')}"
        if hash_payload(record.get("detail", {})) != record.get("detail_hash"):
            problems.append(f"{where}: detail does not match its hash")
        if record_hash(record) != record.get("chain_hash"):
            problems.append(f"{where}: the record hash does not match its contents")
        if contiguous and previous is not None:
            if record.get("seq") != previous.get("seq", 0) + 1:
                problems.append(f"{where}: follows {previous.get('seq')}, so the run has a gap")
            if record.get("prev_hash") != previous.get("chain_hash"):
                problems.append(f"{where}: does not follow its predecessor")
        previous = record

    by_seq = {record.get("seq"): record for record in records}
    attested = 0
    for checkpoint in export.get("checkpoints", []):
        where = f"checkpoint {checkpoint.get('seq')}"
        expected = statement_hash(
            int(checkpoint["seq"]), str(checkpoint["chain_head"]), str(checkpoint["recorded_at"])
        )
        if checkpoint.get("statement_hash") != expected:
            problems.append(f"{where}: the statement does not match its fields")
            continue
        if not signature_valid(checkpoint, keys):
            problems.append(f"{where}: the signature does not verify (kid {checkpoint.get('kid')})")
            continue
        covered = by_seq.get(checkpoint.get("seq"))
        if covered is not None and covered.get("chain_hash") != checkpoint.get("chain_head"):
            problems.append(f"{where}: the record at that seq has a different hash")
            continue
        attested = max(attested, int(checkpoint["seq"]))

    return not problems, problems, attested


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as handle:
        export = json.load(handle)

    intact, problems, attested = verify(export)
    records = len(export.get("records", []))
    checkpoints = len(export.get("checkpoints", []))
    contiguous = bool(export.get("contiguous"))

    print(f"scope:       {export.get('scope', 'unstated')}")
    print(f"records:     {records} ({'a contiguous run' if contiguous else 'a selection'})")
    print(f"checkpoints: {checkpoints}")
    if attested:
        print(f"attested:    up to record {attested} by a signed checkpoint")
    else:
        print("attested:    by no checkpoint in this export, which is weaker")
    if not contiguous:
        print(
            "note:        this is a selection, not the whole trail. Records between\n"
            "             the ones here are not accounted for by this file."
        )
    if intact:
        print("\nVERIFIED: every hash recomputed and matched, every signature valid.")
        return 0
    print("\nNOT VERIFIED:")
    for problem in problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

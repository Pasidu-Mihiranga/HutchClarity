"""Verifiable export bundles and the regulator pack (plan Phase 7, ADR-0039).

An export has to be checkable **without trusting Clarity**, or it is just a
printout. So a bundle carries four things and nothing else is needed:

1. the records, in order, with their hashes;
2. the signed checkpoints that cover them;
3. the public keys, so the signatures can be checked;
4. the instructions, in the file, for recomputing both.

And then ``scripts/verify_audit_export.py`` does it with nothing but the Python
standard library and ``cryptography``: no Clarity import, no network, no database.
That constraint is the whole design. A verifier that imports the code it is
checking proves that the code agrees with itself.

**Not encrypted**, unlike a backup. A backup is Clarity's own copy and travels in
Clarity's custody; an export is handed to someone else on purpose, and encrypting
it would mean handing over the key too, which is theatre. What protects an export
is that its contents are pseudonymous (I13) and that altering it is detectable.

**Scoped, and the scope is stated in the file.** An export for one case holds that
case's records; a chain of only those records is not contiguous, so the bundle
says which records were selected and carries each one's own hash and link, which a
verifier checks individually against the checkpoint that covers them. A verifier
that silently accepted a gap would accept a redacted export as complete, so a
partial export is **labelled** partial and the verifier says so in its output.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from clarity.kernel.canonical import hash_payload
from clarity.kernel.common import ClarityModel
from clarity.platform.audit.checkpoints import Checkpoint, signature_valid, statement_hash
from clarity.platform.audit.ledger import AuditRecord, record_hash

#: Export format. A verifier refuses a version it does not know rather than
#: guessing, because guessing is how a verifier comes to pass something bad.
EXPORT_VERSION = 1

HOW_TO_VERIFY = (
    "For each record: recompute the canonical hash of every field except "
    "chain_hash (see record_hash in the accompanying script) and compare it to "
    "chain_hash; check detail_hash against the canonical hash of detail; and for "
    "a contiguous export, check prev_hash against the previous record's "
    "chain_hash. For each checkpoint: recompute statement_hash from (seq, "
    "chain_head, recorded_at) with the purpose label clarity.audit.checkpoint, "
    "and verify the Ed25519 signature over its UTF-8 bytes with the public key "
    "for its kid. A checkpoint whose seq is in this export must match that "
    "record's chain_hash."
)


class AuditExport(ClarityModel):
    """What a regulator receives. Self-describing, and checkable offline."""

    export_version: int = EXPORT_VERSION
    created_at: datetime
    scope: str
    """What was selected, in words: "case CS-2026-0012" or "the whole trail"."""

    contiguous: bool
    """True when the records are an unbroken run. A scoped export is **not**, and
    saying so is what keeps a verifier from reading a selection as a whole."""

    records: list[AuditRecord]
    checkpoints: list[Checkpoint]
    public_keys: dict[str, str]
    algorithm: str = "Ed25519"
    how_to_verify: str = HOW_TO_VERIFY

    @property
    def digest(self) -> str:
        """Over the whole export, so two copies can be compared by one value."""
        return hash_payload(
            {
                "export_version": self.export_version,
                "created_at": self.created_at.isoformat(),
                "scope": self.scope,
                "contiguous": self.contiguous,
                "records": [record.model_dump(mode="json") for record in self.records],
                "checkpoints": [cp.model_dump(mode="json") for cp in self.checkpoints],
                "public_keys": dict(sorted(self.public_keys.items())),
            }
        )


class ExportVerdict(ClarityModel):
    """What a verifier concluded, in terms a report can quote."""

    intact: bool
    contiguous: bool
    records: int
    checkpoints: int
    attested: int
    """How many records a signed checkpoint covers. Zero means the export is
    internally consistent and attested by nothing, which is weaker and said so."""

    problems: list[str] = Field(default_factory=list)

    @property
    def summary(self) -> str:
        if not self.intact:
            return f"the export does not verify: {'; '.join(self.problems)}"
        scope = "a contiguous run" if self.contiguous else "a selection"
        attested = (
            f"attested up to record {self.attested}"
            if self.attested
            else "attested by no checkpoint in this export"
        )
        return (
            f"{self.records} record(s) as {scope}, each hash recomputed and matching, "
            f"{self.checkpoints} checkpoint signature(s) valid, {attested}"
        )


def verify_export(export: AuditExport) -> ExportVerdict:
    """Check an export the way the offline script does, and for the same reasons.

    Kept here as well so the behaviour is under test in CI: the script is the
    artefact a regulator runs, and a script nobody tests is a script that works
    until it matters.
    """
    problems: list[str] = []

    if export.export_version != EXPORT_VERSION:
        return ExportVerdict(
            intact=False,
            contiguous=export.contiguous,
            records=len(export.records),
            checkpoints=len(export.checkpoints),
            attested=0,
            problems=[f"export format {export.export_version} is not {EXPORT_VERSION}"],
        )

    previous: AuditRecord | None = None
    for record in export.records:
        where = f"record {record.seq}"
        if hash_payload(record.detail) != record.detail_hash:
            problems.append(f"{where}: detail does not match its hash")
        if record_hash(record) != record.chain_hash:
            problems.append(f"{where}: the record hash does not match its contents")
        if export.contiguous and previous is not None:
            if record.seq != previous.seq + 1:
                problems.append(f"{where}: follows {previous.seq}, so the run has a gap")
            if record.prev_hash != previous.chain_hash:
                problems.append(f"{where}: does not follow its predecessor")
        previous = record

    by_seq = {record.seq: record for record in export.records}
    attested = 0
    for checkpoint in export.checkpoints:
        where = f"checkpoint {checkpoint.seq}"
        if checkpoint.statement_hash != statement_hash(
            checkpoint.seq, checkpoint.chain_head, checkpoint.recorded_at
        ):
            problems.append(f"{where}: the statement does not match its fields")
            continue
        if not signature_valid(checkpoint, export.public_keys):
            problems.append(f"{where}: the signature does not verify (kid {checkpoint.kid})")
            continue
        covered = by_seq.get(checkpoint.seq)
        if covered is not None and covered.chain_hash != checkpoint.chain_head:
            problems.append(f"{where}: the record at that seq has a different hash")
            continue
        attested = max(attested, checkpoint.seq)

    return ExportVerdict(
        intact=not problems,
        contiguous=export.contiguous,
        records=len(export.records),
        checkpoints=len(export.checkpoints),
        attested=attested,
        problems=problems,
    )


def export_document(export: AuditExport) -> dict[str, Any]:
    """The JSON a regulator is handed, digest included."""
    return {**export.model_dump(mode="json"), "digest": export.digest}


__all__ = [
    "EXPORT_VERSION",
    "HOW_TO_VERIFY",
    "AuditExport",
    "ExportVerdict",
    "export_document",
    "verify_export",
]

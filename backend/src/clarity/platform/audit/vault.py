"""The backup and restore operations, with their audit records (Phase 6).

``backup.py`` knows how to seal a bundle and ``recovery.py`` knows how to measure
one. This is the service an operator or a drill actually calls, and the one that
writes the trail's own record of what was done to it.

**Who may.** Taking a backup and restoring one are not the same authority and are
not granted together: ``audit:export`` covers reading the trail out, and
restoring needs ``audit:restore`` because it is the only operation in the system
that can replace history. ``audit:export`` is grantable and time-boxed (ADR-0036);
``audit:restore`` is not, and comes from the platform admin role only, so taking
it is a change somebody approved rather than a duty handed out for an afternoon.
Both remove money permissions from whoever holds them (separation of duties).

**The order a restore happens in**, which is the part worth being careful about:

1. Read the bundle and verify it decrypts and checksums.
2. Measure it against the external checkpoint, **before** touching the database,
   so the operator sees what will be lost while it is still their choice.
3. Write the records.
4. Record the restore *into the restored trail*, so the restore is part of the
   history it created rather than a note beside it.

Step 2 before step 3 is not a detail. A restore that discovers the loss
afterwards has already overwritten the evidence of how much there was.

**A bundle ends one record before its own.** ``backup.created`` is appended after
the bundle has been read, because the record quotes the checksum and the checksum
covers the records. So a bundle covering 1 to 400 is followed by a
``backup.created`` at 401, and restoring it leaves a trail with no record that
the backup was taken. That is deliberate rather than tidy: the alternative is a
record whose checksum field is written before the checksum exists. The loss report
counts that record as lost, correctly, and the ``restore.performed`` record that
follows names the checksum, so the pair still tells the whole story.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from clarity.kernel.common import utc_now
from clarity.platform.audit.backup import (
    AuditBundle,
    BackupRefused,
    bundle_from,
    read_bundle,
    write_bundle,
)
from clarity.platform.audit.checkpoints import AUDIT_CHECKPOINTS, Checkpoint, Checkpointer
from clarity.platform.audit.ledger import (
    AUDIT,
    AUDIT_HEAD,
    ActorKind,
    AuditEventType,
    AuditLedger,
)
from clarity.platform.audit.recovery import LossReport, assess_bundle
from clarity.platform.persistence import Repository, UnitOfWorkFactory
from clarity.platform.security.principal import Permission, Principal

_KEY_WIDTH = 12


class RecoveryRefused(RuntimeError):
    """The operation was not permitted, or would have lost something silently."""


def _key(seq: int) -> str:
    return str(seq).zfill(_KEY_WIDTH)


class AuditVault:
    """Takes backups of the trail and restores them, recording both."""

    def __init__(
        self,
        ledger: AuditLedger,
        checkpoints: Checkpointer,
        *,
        key: Callable[[], bytes],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._ledger = ledger
        self._checkpoints = checkpoints
        self._open_unit: UnitOfWorkFactory = ledger.open_unit
        #: A callable, not the bytes: the key is read when it is needed, so a
        #: process that never takes a backup never holds one in memory.
        self._key = key
        self._clock = clock or utc_now

    # -- backing up ---------------------------------------------------------- #

    def back_up(self, by: Principal, path: Path) -> AuditBundle:
        """Write the whole trail to ``path``, sealed, and record that it happened."""
        if not by.has(Permission.AUDIT_EXPORT):
            raise RecoveryRefused("taking a backup of the trail needs audit:export")

        bundle = bundle_from(self._open_unit, created_at=self._clock())
        bundle = bundle.model_copy(update={"public_keys": self._checkpoints.public_keys()})
        checksum = write_bundle(bundle, path, self._key())
        first, last = bundle.covers

        self._ledger.append(
            AuditEventType.BACKUP_CREATED,
            actor_ref=by.ref,
            actor_kind=ActorKind.STAFF,
            object_ref=f"backup:{checksum[:23]}",
            payload={"checksum": checksum, "covers": [first, last]},
            detail={
                # The name of the file, never its path: a path can name a mount,
                # a host or a customer's directory, and none of that belongs in
                # a record anyone with audit access can read.
                "file": path.name,
                "checksum": checksum,
                "records": len(bundle.records),
                "checkpoints": len(bundle.checkpoints),
                "covers_from": first,
                "covers_to": last,
            },
        )
        return bundle

    # -- restoring ----------------------------------------------------------- #

    def inspect(self, by: Principal, path: Path, witness: Checkpoint | None = None) -> LossReport:
        """Read a bundle and report what restoring it would and would not recover.

        Recorded as ``backup.read``: opening a backup is itself an event, whether
        or not a restore follows.
        """
        if not by.has(Permission.AUDIT_RESTORE):
            raise RecoveryRefused("opening a backup of the trail needs audit:restore")

        bundle = read_bundle(path, self._key())
        report = assess_bundle(bundle, witness)
        self._ledger.append(
            AuditEventType.BACKUP_READ,
            actor_ref=by.ref,
            actor_kind=ActorKind.STAFF,
            object_ref=f"backup:{bundle.checksum[:23]}",
            payload={"checksum": bundle.checksum},
            detail={
                "file": path.name,
                "checksum": bundle.checksum,
                "head_seq": bundle.head_seq,
                "witness_seq": report.witness_seq,
                "complete": report.complete,
                "lost_from": report.lost_from,
                "lost_to": report.lost_to,
            },
        )
        return report

    def restore(
        self,
        by: Principal,
        path: Path,
        *,
        witness: Checkpoint | None = None,
        accept_loss: bool = False,
    ) -> LossReport:
        """Replace the trail with a bundle's contents and report the loss.

        ``accept_loss`` is required when the bundle is measurably short of the
        external checkpoint. A restore that silently drops three hundred records
        is the failure this whole phase exists to prevent, so the default is to
        refuse and make the operator say, in the call, that they know.
        """
        report = self.inspect(by, path, witness)
        if not report.complete and not accept_loss:
            raise RecoveryRefused(
                f"{report.summary}. Pass accept_loss=True to restore anyway, "
                "which records the loss in the restored trail."
            )
        bundle = read_bundle(path, self._key())

        with self._open_unit() as unit, unit.as_custodian():
            # The named exception to append-only: replacing the trail is the one
            # thing a restore is for, and saying so here is what keeps every
            # other write path from being able to do it (ADR-0038). On PostgreSQL
            # the span assumes clarity_audit_custodian, the only role granted
            # DELETE on these tables. The application role is not a member of it.
            records: Repository[str, Any] = unit.repository(AUDIT)
            signed: Repository[str, Checkpoint] = unit.repository(AUDIT_CHECKPOINTS)
            heads: Repository[str, dict[str, Any]] = unit.repository(AUDIT_HEAD)
            for key in list(records.keys()):
                records.delete(key)
            for key in list(signed.keys()):
                signed.delete(key)
            for record in bundle.records:
                records.put(_key(record.seq), record)
            for checkpoint in bundle.checkpoints:
                signed.put(_key(checkpoint.seq), checkpoint)
            if bundle.head_hash is not None:
                heads.put("head", {"seq": bundle.head_seq, "chain_hash": bundle.head_hash})
            unit.commit()

        chain = self._ledger.verify()
        if not chain.intact:
            raise RecoveryRefused(
                f"the restored trail does not verify at seq {chain.broken_at}: {chain.reason}"
            )

        # Into the restored trail, so the restore is part of the history it made.
        self._ledger.append(
            AuditEventType.RESTORE_PERFORMED,
            actor_ref=by.ref,
            actor_kind=ActorKind.STAFF,
            object_ref=f"backup:{bundle.checksum[:23]}",
            payload={"checksum": bundle.checksum, "report": report.summary},
            detail={
                "file": path.name,
                "checksum": bundle.checksum,
                "restored_to_seq": report.restored_to_seq,
                "witness_seq": report.witness_seq,
                "complete": report.complete,
                "lost_from": report.lost_from,
                "lost_to": report.lost_to,
                "lost_count": report.lost_count,
                "accepted_loss": not report.complete,
            },
        )
        return report


__all__ = ["AuditVault", "BackupRefused", "RecoveryRefused"]

"""Recovery: backups, the loss report, and replay with no side effects (Phase 6).

The three acceptance tests from the plan, plus the cases that make them mean
something:

1. Given a backup and later activity, when the database is restored, the loss
   report names the exact ``seq`` range lost.
2. Given a restore, when state is rebuilt by replay, there are zero adapter
   calls.
3. Given a refund executed after the backup point, when reconciliation runs, it
   is re-ingested once and not executed again.

The first is the one that needed the most care. A bundle is internally complete
by construction, so nothing inside it knows what came after it: the loss can only
be measured against a checkpoint held outside the backup, which is what the
public witness endpoint is for.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from clarity.contracts.decision import ActionType
from clarity.integration.ports import Command, CommandResult
from clarity.integration.replay import (
    ReadOnlyCommandPort,
    SealedCommandPort,
    SideEffectRefused,
)
from clarity.modules.receipts.signing import DevSigningService
from clarity.platform.audit.backup import (
    BackupRefused,
    BundleTampered,
    backup_key_from,
    read_bundle,
    unseal,
)
from clarity.platform.audit.checkpoints import Checkpointer
from clarity.platform.audit.ledger import AuditEventType, AuditLedger
from clarity.platform.audit.recovery import (
    ActionToCheck,
    Standing,
    actions_in_window,
    reconcile,
)
from clarity.platform.audit.vault import AuditVault, RecoveryRefused
from clarity.platform.persistence.memory import MemoryStore, MemoryUnitOfWork
from clarity.platform.security.principal import Assurance, Permission, Principal, Role

KEY = backup_key_from("a-test-backup-key")


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, by: timedelta) -> None:
        self.now += by


class Trail:
    """A ledger, its checkpointer and a vault over them."""

    def __init__(self) -> None:
        self.clock = Clock()
        self.store = MemoryStore()
        self.ledger = AuditLedger(self.unit, clock=self.clock)
        self.checkpoints = Checkpointer(
            self.ledger,
            DevSigningService(kid="audit-recovery-test"),
            self.unit,
            every_records=lambda: 1000,
            max_age=lambda: timedelta(days=1),
            clock=self.clock,
        )
        self.vault = AuditVault(self.ledger, self.checkpoints, key=lambda: KEY, clock=self.clock)

    def unit(self) -> MemoryUnitOfWork:
        return MemoryUnitOfWork(self.store)

    def append(self, count: int, *, start: int = 0) -> None:
        for index in range(start, start + count):
            self.ledger.append(
                AuditEventType.STAFF_ACTION,
                actor_ref="sup:ruwan",
                object_ref=f"plan:{index}",
                payload={"i": index},
            )
            self.clock.advance(timedelta(seconds=1))


def operator(*permissions: Permission, role: Role = Role.PLATFORM_ADMIN) -> Principal:
    return Principal(
        ref="admin:kamal",
        roles=frozenset({role}),
        assurance=Assurance.MFA_RECENT,
        granted=frozenset(permissions),
    )


#: An account with no audit authority at all. ``PLATFORM_ADMIN`` will not do:
#: it carries ``audit:export`` and ``audit:restore`` by role, which is the point
#: of those being role permissions rather than grants.
NOBODY = operator(role=Role.AGENT)
EXPORT_ONLY = Principal(
    ref="comp:alice",
    roles=frozenset({Role.AGENT}),
    assurance=Assurance.MFA_RECENT,
    granted=frozenset({Permission.AUDIT_EXPORT}),
)


BACKUP_OPERATOR = operator(Permission.AUDIT_EXPORT)
RESTORE_OPERATOR = operator(Permission.AUDIT_EXPORT, Permission.AUDIT_RESTORE)


# --------------------------------------------------------------------------- #
# The bundle
# --------------------------------------------------------------------------- #


def test_a_backup_round_trips_and_records_itself(tmp_path: Path):
    trail = Trail()
    trail.append(5)
    path = tmp_path / "trail.backup"

    bundle = trail.vault.back_up(BACKUP_OPERATOR, path)

    assert path.exists()
    assert read_bundle(path, KEY).checksum == bundle.checksum
    recorded = trail.ledger.of_type(AuditEventType.BACKUP_CREATED)
    assert len(recorded) == 1
    assert recorded[0].detail["checksum"] == bundle.checksum
    assert recorded[0].detail["covers_to"] == 5


def test_a_backup_is_never_written_in_the_clear(tmp_path: Path):
    trail = Trail()
    trail.ledger.append(
        AuditEventType.STAFF_ACTION,
        actor_ref="sup:ruwan",
        object_ref="plan:secret",
        payload={},
        detail={"note": "a-distinctive-string-only-in-the-detail"},
    )
    path = tmp_path / "trail.backup"
    trail.vault.back_up(BACKUP_OPERATOR, path)

    blob = path.read_bytes()

    assert b"a-distinctive-string-only-in-the-detail" not in blob
    assert blob.startswith(b"clarity-audit-backup\n")


def test_the_path_of_a_backup_is_not_recorded(tmp_path: Path):
    """A path names a mount, a host, sometimes a person. The file name is enough."""
    trail = Trail()
    trail.append(1)
    path = tmp_path / "trail.backup"

    trail.vault.back_up(BACKUP_OPERATOR, path)

    detail = trail.ledger.of_type(AuditEventType.BACKUP_CREATED)[0].detail
    assert detail["file"] == "trail.backup"
    assert str(tmp_path) not in str(detail)


def test_an_altered_bundle_is_refused(tmp_path: Path):
    trail = Trail()
    trail.append(3)
    path = tmp_path / "trail.backup"
    trail.vault.back_up(BACKUP_OPERATOR, path)

    blob = bytearray(path.read_bytes())
    blob[-10] = blob[-10] ^ 0x01
    path.write_bytes(bytes(blob))

    with pytest.raises(BundleTampered):
        read_bundle(path, KEY)


def test_the_wrong_key_cannot_open_a_bundle(tmp_path: Path):
    trail = Trail()
    trail.append(3)
    path = tmp_path / "trail.backup"
    trail.vault.back_up(BACKUP_OPERATOR, path)

    with pytest.raises(BundleTampered):
        read_bundle(path, backup_key_from("the-wrong-key"))


def test_a_bundle_of_an_unknown_format_is_refused(tmp_path: Path):
    trail = Trail()
    trail.append(1)
    path = tmp_path / "trail.backup"
    trail.vault.back_up(BACKUP_OPERATOR, path)
    blob = path.read_bytes().replace(b"\nv1\n", b"\nv99\n", 1)

    with pytest.raises(BackupRefused, match="is not v1"):
        unseal(blob, KEY)


def test_no_configured_key_means_no_backup():
    with pytest.raises(BackupRefused, match="CLARITY_AUDIT_BACKUP_KEY"):
        backup_key_from(None)


def test_backing_up_needs_the_export_duty(tmp_path: Path):
    trail = Trail()
    trail.append(1)

    with pytest.raises(RecoveryRefused, match="audit:export"):
        trail.vault.back_up(NOBODY, tmp_path / "trail.backup")


def test_restoring_needs_more_than_the_export_duty(tmp_path: Path):
    """Reading the trail out and replacing it are different authorities."""
    trail = Trail()
    trail.append(1)
    path = tmp_path / "trail.backup"
    trail.vault.back_up(BACKUP_OPERATOR, path)

    with pytest.raises(RecoveryRefused, match="audit:restore"):
        trail.vault.restore(EXPORT_ONLY, path)


# --------------------------------------------------------------------------- #
# Acceptance 1: the loss report names the exact range
# --------------------------------------------------------------------------- #


def test_a_restore_names_the_exact_range_it_lost(tmp_path: Path):
    trail = Trail()
    trail.append(10)
    path = tmp_path / "trail.backup"
    bundle = trail.vault.back_up(BACKUP_OPERATOR, path)
    # The bundle's own ``backup.created`` record is appended after the bundle was
    # read, so it sits one past the end of what the bundle holds. That is why the
    # expectation is the bundle's range and not the trail's head.
    backed_up_to = bundle.covers[1]

    # Activity after the backup, checkpointed, and the checkpoint kept outside.
    trail.append(7, start=10)
    witness = trail.checkpoints.checkpoint()
    assert witness is not None
    assert witness.seq > backed_up_to

    report = trail.vault.restore(RESTORE_OPERATOR, path, witness=witness, accept_loss=True)

    assert not report.complete
    assert report.lost_from == backed_up_to + 1
    assert report.lost_to == witness.seq
    assert report.lost_count == witness.seq - backed_up_to
    assert f"{report.lost_from} to {report.lost_to}" in report.summary


def test_a_restore_refuses_to_lose_records_silently(tmp_path: Path):
    """The operator has to say they know. That is the whole point of the phase."""
    trail = Trail()
    trail.append(4)
    path = tmp_path / "trail.backup"
    trail.vault.back_up(BACKUP_OPERATOR, path)
    trail.append(4, start=4)
    witness = trail.checkpoints.checkpoint()

    with pytest.raises(RecoveryRefused, match="accept_loss"):
        trail.vault.restore(RESTORE_OPERATOR, path, witness=witness)


def test_a_restore_with_nothing_lost_reports_complete(tmp_path: Path):
    trail = Trail()
    trail.append(6)
    witness = trail.checkpoints.checkpoint()
    path = tmp_path / "trail.backup"
    trail.vault.back_up(BACKUP_OPERATOR, path)

    report = trail.vault.restore(RESTORE_OPERATOR, path, witness=witness)

    assert report.complete
    assert report.lost_count == 0
    assert "complete" in report.summary


def test_a_forged_witness_proves_nothing(tmp_path: Path):
    """Otherwise anyone could manufacture a loss report, or hide one."""
    trail = Trail()
    trail.append(4)
    witness = trail.checkpoints.checkpoint()
    assert witness is not None
    forged = witness.model_copy(update={"seq": 9999})
    path = tmp_path / "trail.backup"
    trail.vault.back_up(BACKUP_OPERATOR, path)

    report = trail.vault.inspect(RESTORE_OPERATOR, path, forged)

    assert not report.intact
    assert report.reason is not None
    assert "proves nothing" in report.reason


def test_the_restore_is_recorded_in_the_trail_it_restored(tmp_path: Path):
    trail = Trail()
    trail.append(5)
    path = tmp_path / "trail.backup"
    trail.vault.back_up(BACKUP_OPERATOR, path)
    trail.append(3, start=5)
    witness = trail.checkpoints.checkpoint()

    trail.vault.restore(RESTORE_OPERATOR, path, witness=witness, accept_loss=True)

    restored = trail.ledger.of_type(AuditEventType.RESTORE_PERFORMED)
    assert len(restored) == 1
    assert restored[0].detail["accepted_loss"] is True
    assert trail.ledger.verify().intact, "and the trail still verifies afterwards"


def test_inspecting_a_backup_is_itself_recorded(tmp_path: Path):
    trail = Trail()
    trail.append(2)
    path = tmp_path / "trail.backup"
    trail.vault.back_up(BACKUP_OPERATOR, path)

    trail.vault.inspect(RESTORE_OPERATOR, path)

    assert len(trail.ledger.of_type(AuditEventType.BACKUP_READ)) == 1


# --------------------------------------------------------------------------- #
# Acceptance 2: zero adapter calls during a replay
# --------------------------------------------------------------------------- #


def a_command() -> Command:
    return Command(
        action_type=ActionType.REFUND,
        subscriber_ref="sub:9f2a",
        idempotency_key="IDK-1",
    )


def test_a_replay_cannot_reach_a_hutch_system():
    sealed = SealedCommandPort()

    with pytest.raises(SideEffectRefused, match="must not reach a HUTCH system"):
        sealed.execute(a_command())
    with pytest.raises(SideEffectRefused):
        sealed.status_of("IDK-1")


def test_a_sealed_port_reports_what_was_attempted():
    """The drill asserts zero, so the count has to exist and be honest."""
    sealed = SealedCommandPort()
    assert sealed.call_count == 0

    with pytest.raises(SideEffectRefused):
        sealed.execute(a_command())

    assert sealed.call_count == 1
    assert sealed.attempts == ["execute:REFUND:IDK-1"]


def test_a_sealed_port_says_it_supports_nothing():
    """So code that checks first takes its unavailable branch instead of raising."""
    sealed = SealedCommandPort()

    assert sealed.supports(ActionType.REFUND) is False
    assert sealed.call_count == 0, "and asking is not an adapter call"


# --------------------------------------------------------------------------- #
# Acceptance 3: re-ingested once, never executed again
# --------------------------------------------------------------------------- #


class FakeHutch:
    """A command port that remembers what it was asked, for reconciliation."""

    source = None  # type: ignore[assignment]

    def __init__(self, *done: str) -> None:
        self.done = set(done)
        self.executions: list[str] = []

    def execute(self, command: Command) -> CommandResult:
        self.executions.append(command.idempotency_key)
        raise AssertionError("reconciliation must never execute anything")

    def status_of(self, idempotency_key: str) -> CommandResult | None:
        if idempotency_key not in self.done:
            return None
        return CommandResult(accepted=True, adapter_ref=f"HUTCH-{idempotency_key}", replayed=True)

    def supports(self, action_type: ActionType) -> bool:
        return True


def test_a_refund_hutch_already_made_is_re_ingested_not_executed():
    hutch = FakeHutch("IDK-after-backup")
    port = ReadOnlyCommandPort(hutch)  # type: ignore[arg-type]
    lost = ActionToCheck("IDK-after-backup", case_id="CS-1", known_locally=False)

    plan = reconcile([lost], port.status_of)

    assert [item.standing for item in plan.items] == [Standing.MISSING_LOCALLY]
    assert plan.to_re_ingest[0].action.case_id == "CS-1"
    assert hutch.executions == [], "nothing was executed"
    assert port.lookups == ["IDK-after-backup"], "it was asked, once"


def test_reconciliation_cannot_execute_even_if_asked():
    hutch = FakeHutch()
    port = ReadOnlyCommandPort(hutch)  # type: ignore[arg-type]

    with pytest.raises(SideEffectRefused):
        port.execute(a_command())

    assert hutch.executions == []
    assert port.refused == ["REFUND:IDK-1"]


def test_an_action_both_sides_hold_needs_nothing():
    port = ReadOnlyCommandPort(FakeHutch("IDK-1"))  # type: ignore[arg-type]

    plan = reconcile([ActionToCheck("IDK-1", known_locally=True)], port.status_of)

    assert plan.items[0].standing is Standing.AGREED
    assert plan.needing_a_person == []


def test_an_action_hutch_never_did_is_safe_to_put_through_the_normal_path():
    port = ReadOnlyCommandPort(FakeHutch())  # type: ignore[arg-type]

    plan = reconcile([ActionToCheck("IDK-never", known_locally=False)], port.status_of)

    assert plan.safe_to_retry[0].action.idempotency_key == "IDK-never"
    assert "nothing was executed" in plan.items[0].detail


def test_an_unreachable_system_is_unknown_and_does_not_stop_the_rest():
    """A reconciliation that halts at the first failure leaves the window unexamined."""

    def flaky(key: str) -> CommandResult | None:
        if key == "IDK-2":
            raise RuntimeError("charging is down")
        return CommandResult(accepted=True, adapter_ref="HUTCH-1", replayed=True)

    plan = reconcile(
        [ActionToCheck("IDK-1"), ActionToCheck("IDK-2"), ActionToCheck("IDK-3")],
        flaky,
    )

    assert [item.standing for item in plan.items] == [
        Standing.AGREED,
        Standing.UNKNOWN,
        Standing.AGREED,
    ]
    assert "charging is down" in plan.of(Standing.UNKNOWN)[0].detail
    assert len(plan.needing_a_person) == 1


def test_no_loss_means_nothing_to_reconcile():
    actions = [ActionToCheck("IDK-1"), ActionToCheck("IDK-2")]

    assert actions_in_window(actions, lost_from=None, lost_to=None) == []


def test_a_loss_means_everything_is_checked_not_just_the_window():
    """The window names the records that went missing, not the actions.

    An action whose audit record survived may still have been rolled back with
    the database, so filtering the work by the window would skip exactly the
    executions a restore is most likely to have undone.
    """
    actions = [ActionToCheck("IDK-1"), ActionToCheck("IDK-2")]

    assert actions_in_window(actions, lost_from=11, lost_to=17) == actions


# --------------------------------------------------------------------------- #
# The drill: destroy the trail and bring it back (Phase 6)
# --------------------------------------------------------------------------- #


def test_the_destroy_and_restore_drill(tmp_path: Path):
    """Take a backup, destroy the trail entirely, restore, and verify.

    This is the one test that exercises every piece together, and the one worth
    running on every merge. Deleting the records *and* the head pointer is how a
    dropped table or a bad migration actually looks: not a tampered row but
    nothing at all, which no amount of hash chaining can detect from the inside.
    """
    trail = Trail()
    trail.append(12)
    witness = trail.checkpoints.checkpoint()
    assert witness is not None
    path = tmp_path / "drill.backup"
    bundle = trail.vault.back_up(BACKUP_OPERATOR, path)
    before = [record.chain_hash for record in trail.ledger.records]

    # Destroy it: every record, every checkpoint, the head pointer.
    with trail.unit() as unit:
        for collection in ("platform.audit", "platform.audit_checkpoints", "platform.audit_head"):
            repository = unit.repository(collection)
            for key in list(repository.keys()):
                repository.delete(key)
        unit.commit()
    assert len(trail.ledger) == 0, "the trail is gone"

    report = trail.vault.restore(RESTORE_OPERATOR, path, witness=witness, accept_loss=True)

    assert trail.ledger.verify().intact, "the restored chain verifies"
    restored = [r.chain_hash for r in trail.ledger.records if r.seq <= bundle.covers[1]]
    assert restored == before[: bundle.covers[1]], "every restored record is byte for byte itself"
    assert trail.checkpoints.verify(witness=witness).intact or report.lost_count > 0
    assert trail.ledger.of_type(AuditEventType.RESTORE_PERFORMED), "and the restore is on record"


def test_the_drill_reports_the_loss_the_backup_window_implies(tmp_path: Path):
    """A drill that always reports zero loss is not testing the loss report."""
    trail = Trail()
    trail.append(8)
    path = tmp_path / "drill.backup"
    bundle = trail.vault.back_up(BACKUP_OPERATOR, path)
    trail.append(5, start=8)
    witness = trail.checkpoints.checkpoint()
    assert witness is not None

    report = trail.vault.restore(RESTORE_OPERATOR, path, witness=witness, accept_loss=True)

    assert report.lost_from == bundle.covers[1] + 1
    assert report.lost_to == witness.seq
    recorded = trail.ledger.of_type(AuditEventType.RESTORE_PERFORMED)[0]
    assert recorded.detail["lost_count"] == report.lost_count


def test_a_body_that_is_not_base64_at_all_is_tampering_too(tmp_path: Path):
    """One flipped bit is tampering whichever way it breaks the bundle.

    A bit flip lands outside the base64 alphabet often enough that treating a
    decode failure as its own category made ``test_an_altered_bundle_is_refused``
    pass four times out of five, depending on which bit moved.
    """
    trail = Trail()
    trail.append(2)
    path = tmp_path / "trail.backup"
    trail.vault.back_up(BACKUP_OPERATOR, path)
    header, _, body = path.read_bytes().rpartition(b"\n")
    path.write_bytes(header + b"\n" + b"not base64 at all !!!" + body[10:])

    with pytest.raises(BundleTampered):
        read_bundle(path, KEY)

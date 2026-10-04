"""Retention, legal hold, erasure and verifiable export (Phase 7, ADR-0039).

The hard part of this phase is that the three requirements pull against the
trail's own design. Retention wants records gone; the chain needs them. Erasure
wants a person's data gone; deleting a record breaks the chain for everything
after it. Legal hold wants some records kept whatever the other two say.

So the tests are mostly about the seams: that an archived trail still verifies,
that a hold actually stops both of the other operations, that erasure leaves the
chain intact, and that an export can be checked by something that has never
imported Clarity.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from clarity.modules.receipts.signing import DevSigningService
from clarity.platform.audit.backup import backup_key_from, read_bundle
from clarity.platform.audit.checkpoints import Checkpointer
from clarity.platform.audit.export import AuditExport, export_document, verify_export
from clarity.platform.audit.ledger import AuditEventType, AuditLedger
from clarity.platform.audit.lifecycle import (
    AuditLifecycle,
    LifecycleRefused,
    verify_segment,
)
from clarity.platform.persistence.memory import MemoryStore, MemoryUnitOfWork
from clarity.platform.security.principal import Assurance, Permission, Principal, Role

KEY = backup_key_from("a-lifecycle-test-key")
VERIFIER = Path(__file__).resolve().parents[2] / "scripts" / "verify_audit_export.py"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, by: timedelta) -> None:
        self.now += by


def officer(*permissions: Permission) -> Principal:
    return Principal(
        ref="comp:alice",
        roles=frozenset({Role.COMPLIANCE}),
        assurance=Assurance.MFA_RECENT,
        granted=frozenset(permissions),
    )


COMPLIANCE = Principal(
    ref="sec:dilani",
    roles=frozenset({Role.SECURITY_ADMIN}),
    assurance=Assurance.MFA_RECENT,
)
ARCHIVIST = Principal(
    ref="admin:kamal",
    roles=frozenset({Role.PLATFORM_ADMIN}),
    assurance=Assurance.MFA_RECENT,
)


class World:
    def __init__(self, tmp_path: Path, *, retain: timedelta = timedelta(days=30)) -> None:
        self.clock = Clock()
        self.store = MemoryStore()
        self.dir = tmp_path
        self.ledger = AuditLedger(self.unit, clock=self.clock)
        self.checkpoints = Checkpointer(
            self.ledger,
            DevSigningService(kid="audit-lifecycle"),
            self.unit,
            every_records=lambda: 1000,
            max_age=lambda: timedelta(days=365),
            clock=self.clock,
        )
        self.lifecycle = AuditLifecycle(
            self.ledger,
            self.checkpoints,
            key=lambda: KEY,
            directory=lambda: self.dir,
            retain=lambda _as_of: retain,
            clock=self.clock,
        )

    def unit(self) -> MemoryUnitOfWork:
        return MemoryUnitOfWork(self.store)

    def append(self, count: int, *, subject: str = "sub_aaaa", case: str | None = None) -> None:
        for index in range(count):
            self.ledger.append(
                AuditEventType.ACTION_EXECUTED,
                actor_ref="clarity",
                object_ref=f"plan:{index}",
                payload={"i": index},
                case_id=case,
                detail={"subject": subject, "total_amount_lkr": "900.00"},
            )
            self.clock.advance(timedelta(minutes=1))


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


# --------------------------------------------------------------------------- #
# Archival: the records move, and the chain stays continuous
# --------------------------------------------------------------------------- #


def test_an_archived_trail_still_verifies(world: World):
    """The seam this phase exists to get right.

    Record 1 is gone from the table, so a verifier that insisted the table start
    at 1 would report the trail truncated. The floor says the records below it are
    elsewhere and names the hash the last removed one had, so the walk resumes at
    the boundary and the chain is continuous across it.
    """
    world.append(20)
    world.clock.advance(timedelta(days=60))

    segment = world.lifecycle.archive(ARCHIVIST, until_seq=12)

    assert segment is not None
    assert segment.from_seq == 1 and segment.to_seq == 12
    assert world.ledger.records[0].seq == 13, "the hot table starts above the floor"
    result = world.ledger.verify()
    assert result.intact, result.reason
    assert result.verified_from == 13


def test_an_archived_segment_verifies_against_its_index_entry(world: World):
    world.append(20)
    world.checkpoints.checkpoint()
    world.clock.advance(timedelta(days=60))
    segment = world.lifecycle.archive(ARCHIVIST, until_seq=12)
    assert segment is not None

    bundle = read_bundle(world.dir / segment.file, KEY)
    intact, note = verify_segment(segment, bundle)

    assert intact, note
    assert bundle.records[0].seq == 1, "and the archived records really are in it"
    assert bundle.records[-1].seq == 12


def test_a_segment_with_no_covering_checkpoint_says_so(world: World):
    """Sealed is not the same as attested, and the difference is not glossed."""
    world.append(20)
    world.clock.advance(timedelta(days=60))
    segment = world.lifecycle.archive(ARCHIVIST, until_seq=12)
    assert segment is not None
    assert segment.checkpoint_seq is None

    intact, note = verify_segment(segment, read_bundle(world.dir / segment.file, KEY))

    assert intact
    assert "no signed checkpoint" in note


def test_a_tampered_segment_is_caught(world: World):
    world.append(20)
    world.clock.advance(timedelta(days=60))
    segment = world.lifecycle.archive(ARCHIVIST, until_seq=12)
    assert segment is not None
    bundle = read_bundle(world.dir / segment.file, KEY)
    forged = bundle.model_copy(
        update={"records": [r.model_copy(update={"actor_ref": "x"}) for r in bundle.records]}
    )

    intact, note = verify_segment(segment, forged)

    assert not intact
    assert "checksum" in note


def test_archival_only_takes_records_past_the_retention_period(world: World):
    world.append(10)
    world.clock.advance(timedelta(days=60))
    world.append(5)

    due = world.lifecycle.due_for_archive()

    assert due == 10, "the five written just now are not old enough"


def test_nothing_is_archived_before_anything_is_due(world: World):
    world.append(10)

    assert world.lifecycle.due_for_archive() == 0
    assert world.lifecycle.archive(ARCHIVIST) is None


def test_the_whole_trail_cannot_be_archived(world: World):
    """The hot table keeps the head, so the chain has somewhere to continue from."""
    world.append(10)
    world.clock.advance(timedelta(days=60))

    with pytest.raises(LifecycleRefused, match="whole trail"):
        world.lifecycle.archive(ARCHIVIST, until_seq=10)


def test_archiving_needs_the_restore_duty(world: World):
    world.append(10)
    world.clock.advance(timedelta(days=60))

    with pytest.raises(LifecycleRefused, match="audit:restore"):
        world.lifecycle.archive(officer(), until_seq=5)


def test_a_second_archive_continues_from_the_floor(world: World):
    world.append(30)
    world.clock.advance(timedelta(days=60))
    world.lifecycle.archive(ARCHIVIST, until_seq=10)

    second = world.lifecycle.archive(ARCHIVIST, until_seq=20)

    assert second is not None
    assert second.from_seq == 11, "it picks up where the first left off"
    assert world.ledger.verify().intact
    assert [s.to_seq for s in world.lifecycle.segments()] == [10, 20]


# --------------------------------------------------------------------------- #
# Legal hold outranks both retention and erasure
# --------------------------------------------------------------------------- #


def test_a_hold_on_a_range_stops_archival_behind_it(world: World):
    world.append(20)
    world.clock.advance(timedelta(days=60))
    world.lifecycle.place_hold(
        COMPLIANCE, hold_id="HOLD-1", reason="regulator query", from_seq=5, to_seq=8
    )

    due = world.lifecycle.due_for_archive()

    assert due == 4, "archival pauses behind the hold rather than skipping it"


def test_archiving_across_a_hold_is_refused(world: World):
    world.append(20)
    world.clock.advance(timedelta(days=60))
    world.lifecycle.place_hold(
        COMPLIANCE, hold_id="HOLD-1", reason="regulator query", from_seq=5, to_seq=8
    )

    with pytest.raises(LifecycleRefused, match="legal hold"):
        world.lifecycle.archive(ARCHIVIST, until_seq=12)


def test_a_hold_on_a_subject_protects_their_records_without_naming_seqs(world: World):
    """Whoever places a hold should not have to know the seq numbers.

    ``held_seqs`` is asserted as a superset, not an exact set: the
    ``hold.placed`` record itself names the subject, so the hold protects its own
    record too. That is the right direction and not worth excluding.
    """
    world.append(6, subject="sub_bbbb")
    world.append(6, subject="sub_aaaa")
    world.clock.advance(timedelta(days=60))
    world.lifecycle.place_hold(
        COMPLIANCE, hold_id="HOLD-2", reason="dispute", subject_ref="sub_bbbb"
    )

    held = world.lifecycle.held_seqs()

    assert {1, 2, 3, 4, 5, 6} <= held, "every record about that subscriber"
    assert held.isdisjoint({7, 8, 9, 10, 11, 12}), "and none about the other one"
    assert world.lifecycle.due_for_archive() == 0, "so nothing can be archived behind it"


def test_a_released_hold_stops_blocking(world: World):
    world.append(20)
    world.clock.advance(timedelta(days=60))
    world.lifecycle.place_hold(
        COMPLIANCE, hold_id="HOLD-1", reason="regulator query", from_seq=5, to_seq=8
    )
    world.lifecycle.release_hold(COMPLIANCE, "HOLD-1", reason="query closed")

    assert world.lifecycle.held_seqs() == set()
    assert world.lifecycle.archive(ARCHIVIST, until_seq=12) is not None


def test_a_hold_must_record_why(world: World):
    with pytest.raises(LifecycleRefused, match="must record why"):
        world.lifecycle.place_hold(COMPLIANCE, hold_id="HOLD-1", reason="  ", from_seq=1, to_seq=2)


def test_a_hold_names_a_subject_or_a_range(world: World):
    with pytest.raises(LifecycleRefused, match="subject or a seq range"):
        world.lifecycle.place_hold(COMPLIANCE, hold_id="HOLD-1", reason="because")


def test_placing_a_hold_needs_the_assign_duty(world: World):
    with pytest.raises(LifecycleRefused, match="audit:assign"):
        world.lifecycle.place_hold(officer(), hold_id="HOLD-1", reason="x", from_seq=1, to_seq=2)


def test_holds_are_recorded_both_ways(world: World):
    world.lifecycle.place_hold(COMPLIANCE, hold_id="HOLD-1", reason="query", from_seq=1, to_seq=2)
    world.lifecycle.release_hold(COMPLIANCE, "HOLD-1", reason="closed")

    assert len(world.ledger.of_type(AuditEventType.HOLD_PLACED)) == 1
    assert len(world.ledger.of_type(AuditEventType.HOLD_RELEASED)) == 1


# --------------------------------------------------------------------------- #
# Erasure: the link goes, the records stay, the chain holds
# --------------------------------------------------------------------------- #


def test_erasure_destroys_the_link_and_keeps_the_chain(world: World):
    world.append(8, subject="sub_aaaa")
    world.lifecycle.register("sub_aaaa", masked="07X XXX 4567", account_ref="ACC-1")

    outcome = world.lifecycle.erase(COMPLIANCE, "sub_aaaa", reason="erasure request ER-9")

    assert outcome.erased
    assert outcome.records_retained == 8
    entry = world.lifecycle.pseudonym("sub_aaaa")
    assert entry is not None and entry.is_erased
    assert entry.masked == "erased", "nothing is left that leads to a person"
    assert entry.account_ref is None
    assert world.ledger.verify().intact, "and the trail still verifies"
    assert len(world.ledger.records) >= 8, "because the records are still there"


def test_the_erasure_response_says_what_was_kept_and_why(world: World):
    """A person asking has to be told the truth, including the part they dislike."""
    world.append(3, subject="sub_aaaa")
    world.lifecycle.register("sub_aaaa", masked="07X XXX 4567")

    outcome = world.lifecycle.erase(COMPLIANCE, "sub_aaaa", reason="ER-9")

    assert "3 audit record(s) remain, pseudonymous" in outcome.summary
    assert "break the chain" in outcome.summary


def test_a_legal_hold_refuses_an_erasure_and_records_the_refusal(world: World):
    world.append(3, subject="sub_aaaa")
    world.lifecycle.register("sub_aaaa", masked="07X XXX 4567")
    world.lifecycle.place_hold(
        COMPLIANCE, hold_id="HOLD-3", reason="fraud investigation", subject_ref="sub_aaaa"
    )

    outcome = world.lifecycle.erase(COMPLIANCE, "sub_aaaa", reason="ER-9")

    assert not outcome.erased
    assert "HOLD-3" in outcome.reason
    entry = world.lifecycle.pseudonym("sub_aaaa")
    assert entry is not None and not entry.is_erased
    recorded = world.ledger.of_type(AuditEventType.ERASURE_PERFORMED)
    assert len(recorded) == 1, "the refusal is on record, so the person can be told why"
    assert recorded[0].detail["erased"] is False


def test_erasing_twice_is_safe(world: World):
    world.lifecycle.register("sub_aaaa", masked="07X XXX 4567")
    world.lifecycle.erase(COMPLIANCE, "sub_aaaa", reason="ER-9")

    again = world.lifecycle.erase(COMPLIANCE, "sub_aaaa", reason="ER-9 again")

    assert again.erased
    assert again.reason == "already erased"


def test_a_returning_customer_does_not_undo_an_erasure(world: World):
    world.lifecycle.register("sub_aaaa", masked="07X XXX 4567")
    world.lifecycle.erase(COMPLIANCE, "sub_aaaa", reason="ER-9")

    world.lifecycle.register("sub_aaaa", masked="07X XXX 4567", account_ref="ACC-NEW")

    entry = world.lifecycle.pseudonym("sub_aaaa")
    assert entry is not None and entry.is_erased
    assert entry.account_ref is None


def test_erasing_an_unknown_pseudonym_says_so_rather_than_claiming_success(world: World):
    outcome = world.lifecycle.erase(COMPLIANCE, "sub_never", reason="ER-9")

    assert not outcome.erased
    assert "no pseudonym link" in outcome.reason


def test_erasure_needs_the_assign_duty(world: World):
    with pytest.raises(LifecycleRefused, match="audit:assign"):
        world.lifecycle.erase(officer(), "sub_aaaa", reason="ER-9")


# --------------------------------------------------------------------------- #
# Verifiable export, and the offline verifier
# --------------------------------------------------------------------------- #


def an_export(world: World, *, contiguous: bool = True, scope: str = "the whole trail"):
    records = world.ledger.records
    return AuditExport(
        created_at=world.clock.now,
        scope=scope,
        contiguous=contiguous,
        records=records,
        checkpoints=world.checkpoints.all(),
        public_keys=world.checkpoints.public_keys(),
    )


def test_an_export_verifies_in_process(world: World):
    world.append(6)
    world.checkpoints.checkpoint()

    verdict = verify_export(an_export(world))

    assert verdict.intact, verdict.problems
    assert verdict.attested > 0
    assert "every hash recomputed" not in verdict.summary  # that wording is the script's
    assert "signature(s) valid" in verdict.summary


def test_an_export_the_offline_verifier_accepts(world: World, tmp_path: Path):
    """The one that matters: checked by something that has never imported Clarity.

    Run as a subprocess, so the test cannot accidentally lend the verifier any of
    Clarity's code. A verifier that imports what it checks proves only that the
    code agrees with itself.
    """
    world.append(6)
    world.checkpoints.checkpoint()
    path = tmp_path / "export.json"
    path.write_text(json.dumps(export_document(an_export(world))), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VERIFIER), str(path)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERIFIED" in result.stdout
    assert "attested:    up to record" in result.stdout


def test_the_offline_verifier_rejects_an_altered_export(world: World, tmp_path: Path):
    world.append(6)
    world.checkpoints.checkpoint()
    document = export_document(an_export(world))
    document["records"][2]["actor_ref"] = "agent:nadeesha"
    path = tmp_path / "export.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VERIFIER), str(path)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )

    assert result.returncode == 1
    assert "NOT VERIFIED" in result.stdout
    assert "does not match its contents" in result.stdout


def test_the_offline_verifier_rejects_a_forged_checkpoint(world: World, tmp_path: Path):
    world.append(6)
    world.checkpoints.checkpoint()
    document = export_document(an_export(world))
    document["checkpoints"][0]["signature"] = "AA" * 44
    path = tmp_path / "export.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VERIFIER), str(path)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )

    assert result.returncode == 1
    assert "signature does not verify" in result.stdout


def test_the_offline_verifier_says_a_selection_is_a_selection(world: World, tmp_path: Path):
    """A scoped export must not read as the whole trail.

    A verifier that silently accepted a gap would accept a redacted export as
    complete, which is the one way a verifier can be worse than nothing.
    """
    world.append(8, case="CS-1")
    world.checkpoints.checkpoint()
    selected = [r for r in world.ledger.records if r.seq in {2, 5, 7}]
    export = AuditExport(
        created_at=world.clock.now,
        scope="case CS-1",
        contiguous=False,
        records=selected,
        checkpoints=world.checkpoints.all(),
        public_keys=world.checkpoints.public_keys(),
    )
    path = tmp_path / "export.json"
    path.write_text(json.dumps(export_document(export)), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VERIFIER), str(path)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )

    assert result.returncode == 0, "a selection can still be internally sound"
    assert "a selection" in result.stdout
    assert "not the whole trail" in result.stdout


def test_a_gap_in_an_export_claiming_to_be_contiguous_is_caught(world: World):
    world.append(8)
    selected = [r for r in world.ledger.records if r.seq in {1, 2, 5}]
    export = AuditExport(
        created_at=world.clock.now,
        scope="the whole trail",
        contiguous=True,
        records=selected,
        checkpoints=[],
        public_keys={},
    )

    verdict = verify_export(export)

    assert not verdict.intact
    assert any("gap" in problem for problem in verdict.problems)


def test_an_export_of_an_unknown_format_is_refused(world: World):
    world.append(2)
    export = an_export(world).model_copy(update={"export_version": 99})

    verdict = verify_export(export)

    assert not verdict.intact
    assert "is not 1" in verdict.problems[0]


def test_the_in_process_and_offline_verifiers_agree(world: World, tmp_path: Path):
    """Two implementations of the same rules, which is the point and the risk.

    The script exists so a regulator needs nothing from Clarity. That means the
    canonical form is written twice, and two implementations drift. This is the
    test that notices.
    """
    world.append(10)
    world.checkpoints.checkpoint()
    document = export_document(an_export(world))
    path = tmp_path / "export.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    in_process = verify_export(an_export(world))
    offline = subprocess.run(
        [sys.executable, str(VERIFIER), str(path)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )

    assert in_process.intact is (offline.returncode == 0)
    assert f"up to record {in_process.attested}" in offline.stdout

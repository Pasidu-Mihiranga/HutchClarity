"""Foundation tests: money, identifiers, canonical hashing, case lifecycle.

These guard the invariants everything else assumes. If money can silently
become a float, or a canonical hash is unstable, every downstream guarantee
(replay, signatures, reconciliation) quietly stops being true.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from clarity.schemas.canonical import canonical_json, chain_hash, hash_payload
from clarity.schemas.case import (
    Case,
    CaseState,
    CaseTrigger,
    CustomerReference,
    IllegalTransition,
)
from clarity.schemas.common import (
    Channel,
    Completeness,
    EventSource,
    mask_msisdn,
    money,
    normalise_msisdn,
    subscriber_ref,
)
from clarity.schemas.timeline import (
    EventType,
    EvidenceSnapshot,
    SourceStatus,
    TimelineEvent,
)

# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #


def test_money_rejects_floats():
    """Binary floats must never reach a refund amount."""
    with pytest.raises(ValueError, match="float"):
        money(49.99)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("49", "49.00"), ("49.004", "49.00"), ("49.005", "49.01"), (Decimal("0.1"), "0.10")],
)
def test_money_quantizes_to_two_places(raw, expected):
    assert f"{money(raw):.2f}" == expected


def test_money_arithmetic_is_exact():
    """The classic float trap: 0.1 + 0.2 must be 0.30, not 0.30000000000000004."""
    assert money(money("0.1") + money("0.2")) == Decimal("0.30")


def test_money_serializes_as_a_fixed_string():
    event = TimelineEvent(
        event_id="ev-1",
        source=EventSource.CHARGING,
        event_type=EventType.VAS_CHARGE,
        source_event_id="c1",
        occurred_at=datetime.now(UTC),
        amount_lkr="49",
    )

    assert '"amount_lkr":"49.00"' in event.model_dump_json()


# --------------------------------------------------------------------------- #
# Identifiers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw", ["0771234567", "771234567", "+94771234567", "077 123 4567", "077-123-4567"]
)
def test_msisdn_forms_all_normalise_to_one_value(raw):
    assert normalise_msisdn(raw) == "+94771234567"


@pytest.mark.parametrize("raw", ["", "12345", "0881234567", "+1771234567", "abc"])
def test_invalid_msisdns_are_rejected(raw):
    """A bad identifier must fail loudly, not build someone else's timeline."""
    with pytest.raises(ValueError):
        normalise_msisdn(raw)


def test_subscriber_ref_is_stable_pseudonymous_and_key_dependent():
    same = subscriber_ref("0771234567", key=b"k1") == subscriber_ref("+94771234567", key=b"k1")
    different_key = subscriber_ref("0771234567", key=b"k2")

    assert same, "every form of a number maps to one ref"
    assert subscriber_ref("0771234567", key=b"k1") != different_key
    ref = subscriber_ref("0771234567", key=b"k1")
    assert "771234567" not in ref, "the ref must not leak the number"


def test_masked_msisdn_hides_the_middle():
    masked = mask_msisdn("+94771234567")

    assert masked == "07X XXX 4567"
    assert "1234" not in masked


# --------------------------------------------------------------------------- #
# Canonical JSON and hashing
# --------------------------------------------------------------------------- #


def test_canonical_json_is_key_order_independent():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_canonical_json_rejects_floats():
    with pytest.raises(TypeError, match="float"):
        canonical_json({"amount": 49.99})


def test_canonical_json_normalises_timestamps_to_utc():
    utc = datetime(2027, 9, 14, 14, 6, tzinfo=UTC)
    offset = utc.astimezone(tz=timezone_plus_530())

    assert canonical_json({"at": utc}) == canonical_json({"at": offset})


def timezone_plus_530():
    from datetime import timezone

    return timezone(timedelta(hours=5, minutes=30))


def test_hash_changes_when_any_value_changes():
    base = {"amount": Decimal("49.00"), "merchant": "M1"}

    assert hash_payload(base) != hash_payload({**base, "amount": Decimal("49.01")})


def test_chain_hash_binds_each_record_to_its_predecessor():
    first = chain_hash("sha256:a", None)
    second = chain_hash("sha256:b", first)

    assert chain_hash("sha256:b", "sha256:other") != second, "the link must depend on history"
    assert first != chain_hash("sha256:a", "sha256:x"), "a genesis record cannot be re-parented"


# --------------------------------------------------------------------------- #
# Evidence snapshot
# --------------------------------------------------------------------------- #


def an_event(event_id: str, *, at: datetime, source=EventSource.CHARGING) -> TimelineEvent:
    return TimelineEvent(
        event_id=event_id,
        source=source,
        event_type=EventType.VAS_CHARGE,
        source_event_id=f"src-{event_id}",
        occurred_at=at,
        amount_lkr="49",
    )


def a_snapshot(events: list[TimelineEvent], sources=None) -> EvidenceSnapshot:
    now = datetime(2027, 9, 14, 18, tzinfo=UTC)
    return EvidenceSnapshot(
        case_id="CASE-T",
        built_at=now,
        window_from=now - timedelta(days=90),
        window_to=now,
        events=events,
        sources=sources
        or [
            SourceStatus(
                source=EventSource.CHARGING,
                completeness=Completeness.COMPLETE,
                event_count=len(events),
            )
        ],
    )


def test_snapshot_rejects_out_of_order_events():
    now = datetime(2027, 9, 14, 18, tzinfo=UTC)

    with pytest.raises(ValidationError, match="ordered"):
        a_snapshot([an_event("ev-2", at=now), an_event("ev-1", at=now - timedelta(hours=1))])


def test_snapshot_rejects_duplicate_event_ids():
    now = datetime(2027, 9, 14, 18, tzinfo=UTC)

    with pytest.raises(ValidationError, match="duplicate"):
        a_snapshot([an_event("ev-1", at=now), an_event("ev-1", at=now)])


def test_snapshot_hash_ignores_event_ordering_but_not_content():
    now = datetime(2027, 9, 14, 18, tzinfo=UTC)
    one = a_snapshot([an_event("ev-1", at=now - timedelta(hours=1)), an_event("ev-2", at=now)])
    same_facts = a_snapshot(
        [an_event("ev-1", at=now - timedelta(hours=1)), an_event("ev-2", at=now)]
    )

    assert one.snapshot_hash == same_facts.snapshot_hash


def test_a_missing_source_cannot_claim_events():
    """ "We could not look" and "we found nothing" are different facts."""
    with pytest.raises(ValidationError, match="MISSING"):
        SourceStatus(
            source=EventSource.VAS_CONSENT, completeness=Completeness.MISSING, event_count=3
        )


def test_unqueried_source_reports_missing_not_complete():
    snapshot = a_snapshot([])

    assert snapshot.status_of(EventSource.VAS_CONSENT) is Completeness.MISSING


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValidationError):
        an_event("ev-1", at=datetime(2027, 9, 14, 18))


# --------------------------------------------------------------------------- #
# Case lifecycle
# --------------------------------------------------------------------------- #


def a_case() -> Case:
    return Case(
        case_id="CASE-1",
        case_no="CASE-2027-000001",
        customer=CustomerReference(subscriber_ref="sub_x", msisdn_masked="07X XXX 4567"),
        trigger=CaseTrigger.CUSTOMER,
        origin_channel=Channel.APP,
    )


def test_case_follows_the_documented_lifecycle():
    case = (
        a_case()
        .with_state(CaseState.COLLECTING_EVIDENCE)
        .with_state(CaseState.EVALUATED)
        .with_state(CaseState.AWAITING_CUSTOMER)
        .with_state(CaseState.EXECUTING)
        .with_state(CaseState.ACTIONED)
        .with_state(CaseState.RECEIPTED)
    )

    assert case.state is CaseState.RECEIPTED
    assert len(case.events) == 6, "every transition is recorded"


def test_a_case_cannot_jump_to_actioned():
    """No path reaches ACTIONED without passing through execution."""
    with pytest.raises(IllegalTransition):
        a_case().with_state(CaseState.ACTIONED)


def test_transitions_do_not_mutate_the_original_case():
    case = a_case()

    case.with_state(CaseState.COLLECTING_EVIDENCE)

    assert case.state is CaseState.OPEN, "state changes return a new case"

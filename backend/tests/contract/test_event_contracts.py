"""Event contracts (issue #10, B01; ADR-0029; plan 21 §11.3).

Producers and consumers are checked against one typed, versioned schema per
event, and no payload can carry personal data.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import BaseModel

from clarity.contracts.events import (
    REGISTRY,
    ActionCompletedV1,
    DomainEventType,
    EventPayload,
    InvalidEventPayload,
    UnknownEventSchema,
    payload_model,
    validate_payload,
)
from clarity.platform.messaging.envelope import Event
from clarity.platform.messaging.outbox import outbox_in
from clarity.platform.persistence import MemoryStore, MemoryUnitOfWork

from ..support.events import SAMPLES

PLAN_21 = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "enterprise-plan"
    / ("21-migration-and-deployment-plan.md")
)
FORBIDDEN = {
    "msisdn",
    "phone",
    "mobile",
    "nic",
    "passport",
    "name",
    "email",
    "address",
    "otp",
    "card",
    "cvv",
}


# --- acceptance tests from the issue ------------------------------------------


def test_a_payload_with_personal_data_is_rejected():
    data = SAMPLES[DomainEventType.ACTION_COMPLETED].model_dump(mode="json") | {
        "msisdn": "+94781234567"
    }

    with pytest.raises(InvalidEventPayload):
        validate_payload(DomainEventType.ACTION_COMPLETED, data)


def test_every_catalogued_event_has_exactly_one_versioned_model():
    types = [event_type for event_type, _ in REGISTRY]

    assert sorted(types) == sorted(DomainEventType)
    assert len(types) == len(set(types))
    for (event_type, version), model in REGISTRY.items():
        assert model.event_type is event_type
        assert model.schema_id() == f"{event_type.value}@v{version}"


def test_an_unknown_event_type_raises_a_typed_error():
    with pytest.raises(UnknownEventSchema):
        validate_payload("refund.please", {})
    with pytest.raises(UnknownEventSchema):
        payload_model(DomainEventType.CASE_CREATED, version=99)


# --- guards ---------------------------------------------------------------------


def test_a_payload_class_cannot_be_defined_with_a_personal_data_field():
    with pytest.raises(TypeError, match="personal"):

        class _Leaky(EventPayload):  # pragma: no cover - definition itself must fail
            event_type = DomainEventType.CASE_CREATED
            customer_msisdn: str


def _fields(model: type[BaseModel]) -> set[str]:
    names: set[str] = set()
    for name, info in model.model_fields.items():
        names.add(name)
        annotation = info.annotation
        for arg in getattr(annotation, "__args__", (annotation,)):
            if isinstance(arg, type) and issubclass(arg, BaseModel):
                names |= _fields(arg)
    return names


@pytest.mark.parametrize("model", sorted(REGISTRY.values(), key=lambda m: m.schema_id()))
def test_no_registered_payload_carries_personal_data_even_nested(model: type[EventPayload]):
    leaking = {f for f in _fields(model) if set(f.split("_")) & FORBIDDEN}
    assert leaking == set()


@pytest.mark.parametrize("event_type", sorted(DomainEventType))
def test_every_event_round_trips_through_the_outbox(event_type: DomainEventType):
    sample = SAMPLES[event_type]

    with MemoryUnitOfWork(MemoryStore()) as unit:
        published = outbox_in(unit).append(Event.of(sample, subject="sub_test"))

    assert published.schema_id == sample.schema_id()
    assert published.payload() == sample


def test_the_outbox_refuses_an_event_whose_payload_does_not_match():
    """The producer finds its own mistake, inside its own transaction."""
    malformed = Event(type=DomainEventType.ACTION_COMPLETED, subject="sub_x", data={"amount": "49"})

    with MemoryUnitOfWork(MemoryStore()) as unit:
        outbox = outbox_in(unit)
        with pytest.raises(InvalidEventPayload):
            outbox.append(malformed)
        assert outbox.pending() == []


def test_money_travels_as_two_decimal_strings():
    data = SAMPLES[DomainEventType.ACTION_COMPLETED].model_dump(mode="json")

    assert data["total_amount_lkr"] == "49.00"
    assert (
        ActionCompletedV1.model_validate(data).total_amount_lkr
        == SAMPLES[DomainEventType.ACTION_COMPLETED].total_amount_lkr
    )  # type: ignore[attr-defined]


def test_the_plan_catalogue_and_the_contracts_agree():
    """Every event the plan marks 'exists' (21 §11.3) has a contract, and back."""
    section = PLAN_21.read_text(encoding="utf-8").split("### 11.3 Event catalogue", 1)[1]
    section = section.split("### 11.4", 1)[0]
    documented: set[str] = set()
    for row in section.splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) != 4 or not cells[3].startswith("exists"):
            continue
        only = re.findall(r"`([a-z_.]+)`", cells[3])
        documented |= set(only) if only else set(re.findall(r"`([a-z_.]+)`", cells[0]))

    assert documented == {event_type.value for event_type in DomainEventType}

"""Raw identifiers never reach the audit trail (ADR-0033, I13).

The assurance plan first proposed a keyed ``payload_hash`` so that a SHA-256 of
a phone number could not be reversed by enumerating a mobile prefix. That fix
was dropped: it would have made the trail verifiable by Clarity alone, which is
the one property the design exists to avoid, and it would have done nothing for
``detail``, which is stored in the clear. The control is now that the identifier
does not arrive at all.

These tests are the two halves of that: the identifiers a caller must not pass,
and the forms the codebase actually uses, which must keep working. The second
half matters as much as the first, because a false positive here fails a real
customer operation (ADR-0034).
"""

from __future__ import annotations

import base64
import hashlib

import pytest

from clarity.platform.audit.entropy import LowEntropyIdentifier, find_identifier
from clarity.platform.audit.ledger import AuditEventType, AuditLedger


@pytest.fixture
def ledger() -> AuditLedger:
    return AuditLedger()


def append(ledger: AuditLedger, **kwargs: object) -> None:
    ledger.append(
        AuditEventType.STAFF_ACTION,
        actor_ref="sup:ruwan",
        object_ref="plan:1",
        **kwargs,  # type: ignore[arg-type]
    )


REFUSED = [
    pytest.param("+94771234567", "phone number", id="msisdn-international"),
    pytest.param("0771234567", "phone number", id="msisdn-national"),
    pytest.param("94 77 123 4567", "phone number", id="msisdn-spaced"),
    pytest.param("077-123-4567", "phone number", id="msisdn-hyphenated"),
    pytest.param("941234567V", "NIC", id="nic-old"),
    pytest.param("nimal@example.lk", "email address", id="email"),
    pytest.param("4111111111111111", "card number", id="card-luhn-valid"),
]


@pytest.mark.parametrize(("value", "kind"), REFUSED)
def test_a_raw_identifier_in_a_payload_is_refused(ledger, value, kind):
    with pytest.raises(LowEntropyIdentifier) as raised:
        append(ledger, payload={"account": {"contact": value}})

    assert raised.value.kind == kind
    assert raised.value.path == "payload.account.contact"
    assert len(ledger) == 0, "and nothing was written"


@pytest.mark.parametrize(("value", "kind"), REFUSED)
def test_a_raw_identifier_in_a_detail_is_refused(ledger, value, kind):
    """``detail`` is stored in the clear, so it is the field that matters most."""
    with pytest.raises(LowEntropyIdentifier) as raised:
        append(ledger, payload={}, detail={"note": value})

    assert raised.value.kind == kind
    assert len(ledger) == 0


def test_an_identifier_inside_a_list_is_found(ledger):
    with pytest.raises(LowEntropyIdentifier) as raised:
        append(ledger, payload={"numbers": ["ok", "+94771234567"]})

    assert raised.value.path == "payload.numbers[1]"


ALLOWED = [
    pytest.param("07X XXX 4567", id="masked-msisdn"),
    pytest.param("sub:9f2a1c4e", id="subscriber-pseudonym"),
    pytest.param("12000.00", id="money"),
    pytest.param("1727784000000", id="epoch-millis"),
    pytest.param("2026-10-04T09:30:00+00:00", id="iso-timestamp"),
    pytest.param("CS-2026-0012", id="case-id"),
    pytest.param("RP-DATA-001@1.2.0", id="rule-pack-version"),
    pytest.param("TR-2026-000123", id="receipt-id"),
]


@pytest.mark.parametrize("value", ALLOWED)
def test_the_forms_the_codebase_uses_are_allowed(ledger, value):
    append(ledger, payload={"value": value}, detail={"value": value})

    assert len(ledger) == 1


def test_opaque_cryptographic_material_is_not_screened(ledger):
    """A hash or a signature has no author who could put a number in it.

    Screening them is all cost: a 64-character hex digest carries a card-shaped
    digit run often enough to fail a real append, which is how this allowance
    was found.
    """
    for index in range(2000):
        digest = hashlib.sha256(str(index).encode()).hexdigest()
        signature = base64.b64encode(hashlib.sha512(str(index).encode()).digest()).decode()
        assert find_identifier({"chain_hash": digest, "signature": signature}) is None


def test_a_pseudonym_key_does_not_excuse_a_nested_identifier():
    """The allowance is for the value at that key, not for a subtree under it."""
    assert find_identifier({"subscriber_ref": "+94771234567"}) is None, "the key is allowed"
    assert find_identifier({"account": {"subscriber_ref": "sub:1", "msisdn": "+94771234567"}}) == (
        "phone number",
        "account.msisdn",
    )

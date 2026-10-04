"""Logs carry no personal data (issue #16, B08; I13).

A log line is the easiest way for a phone number to leave the system: it goes
to a file, a shipper, a search index and a dashboard, and every copy outlives
the request. Redaction therefore sits on the logging pipeline, where no call
site can route around it.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest

from clarity.platform.observability.logs import (
    JsonFormatter,
    MaskingFilter,
    configure_logging,
    masking_is_installed,
    redact,
    redact_value,
)

DILANI = "+94781234567"


@pytest.fixture
def captured() -> Iterator[list[logging.LogRecord]]:
    """A handler that keeps the records a logger emitted, after filtering."""
    records: list[logging.LogRecord] = []

    class _Keep(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger("clarity.test.masking")
    logger.handlers = [_Keep()]
    logger.filters = [MaskingFilter()]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    yield records
    logger.handlers = []
    logger.filters = []


# -- acceptance 2: a log line containing an MSISDN is masked --------------- #


def test_a_log_line_with_an_msisdn_is_masked(captured: list[logging.LogRecord]) -> None:
    logging.getLogger("clarity.test.masking").info("charge disputed by %s on case CASE-1", DILANI)

    assert len(captured) == 1
    rendered = captured[0].getMessage()
    assert DILANI not in rendered
    assert "781234567" not in rendered
    assert "[msisdn]" in rendered
    assert "CASE-1" in rendered, "the case id is an identifier and must survive"


def test_an_msisdn_in_the_message_itself_is_masked(captured: list[logging.LogRecord]) -> None:
    """The common slip: an f-string rather than a logging argument."""
    logging.getLogger("clarity.test.masking").info(f"refunding {DILANI}")

    assert DILANI not in captured[0].getMessage()


def test_an_msisdn_in_a_structured_field_is_masked(captured: list[logging.LogRecord]) -> None:
    logging.getLogger("clarity.test.masking").info(
        "executed", extra={"customer": DILANI, "case_id": "CASE-2"}
    )

    record = captured[0]
    assert DILANI not in str(record.customer)  # type: ignore[attr-defined]
    assert record.case_id == "CASE-2"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+94781234567", "[msisdn]"),
        ("0781234567", "[msisdn]"),
        ("078 123 4567", "[msisdn]"),
        ("+94 78 123 4567", "[msisdn]"),
        ("199012345678", "[nic]"),
        ("912345678V", "[nic]"),
        ("dilani@example.lk", "[email]"),
        ("4111 1111 1111 1111", "[card]"),
    ],
)
def test_every_shape_of_personal_data_is_redacted(raw: str, expected: str) -> None:
    masked = redact(f"before {raw} after")
    assert raw not in masked
    assert expected in masked


def test_a_field_named_for_its_content_is_replaced_wholesale() -> None:
    """A bare value has no shape to recognise, so the field name decides."""
    assert redact_value("msisdn", "0781234567") == "[redacted]"
    assert redact_value("password", "anything at all") == "[redacted]"
    assert redact_value("case_id", "CASE-3") == "CASE-3"


def test_nested_structures_are_redacted() -> None:
    masked = redact_value("payload", {"customer": {"numbers": [DILANI]}})
    assert DILANI not in json.dumps(masked)


def test_identifiers_and_amounts_survive() -> None:
    """Redaction must not make a log useless: these are what an engineer reads."""
    line = redact("case CASE-9 plan PLAN-9 refunded LKR 49.00 for sub_abc123")
    assert "CASE-9" in line
    assert "PLAN-9" in line
    assert "49.00" in line
    assert "sub_abc123" in line, "a subscriber_ref is a pseudonym, not a number"


# -- the pipeline is wired, not just available ---------------------------- #


def test_configure_logging_installs_the_filter() -> None:
    configure_logging(log_format="text")
    assert masking_is_installed(), "redaction must be on the root logger"


def test_configure_logging_twice_does_not_double_the_handlers() -> None:
    configure_logging(log_format="text")
    first = len(logging.getLogger().handlers)
    configure_logging(log_format="text")
    assert len(logging.getLogger().handlers) == first


def test_the_json_formatter_emits_one_object_per_line() -> None:
    configure_logging(log_format="json")
    record = logging.LogRecord(
        name="clarity.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="executed for %s",
        args=(DILANI,),
        exc_info=None,
    )
    MaskingFilter().filter(record)

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "clarity.test"
    assert DILANI not in payload["message"]
    configure_logging(log_format="text")


def test_the_json_line_carries_the_correlation_id() -> None:
    """A log line has to be findable from a trace, or structure buys nothing."""
    from clarity.platform.messaging.correlation import correlated

    record = logging.LogRecord(
        name="clarity.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="executed",
        args=None,
        exc_info=None,
    )
    with correlated("REQ-77"):
        payload = json.loads(JsonFormatter().format(record))

    assert payload["correlation_id"] == "REQ-77"


def test_the_redaction_patterns_agree_with_the_ai_masker() -> None:
    """Two modules recognise a number; they must not disagree about what one is.

    ``clarity.ai.pii`` tokenises reversibly for model calls and lives a layer
    above this one, so the patterns are deliberately separate. This checks they
    still see the same thing.
    """
    from clarity.ai.pii import find_pii

    for raw in ("+94781234567", "0781234567", "912345678V", "dilani@example.lk"):
        assert find_pii(raw), f"the AI masker does not recognise {raw}"
        assert raw not in redact(raw), f"log redaction does not recognise {raw}"

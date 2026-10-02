"""Structured logs with PII redacted before they are written (B08, I13).

A log line is the easiest way for a phone number to leave the system: it goes
to a file, a shipper, a search index and a dashboard, and every copy outlives
the request. So redaction happens in a filter on the logging pipeline, where
nothing can route around it, rather than at each call site where one forgotten
f-string is a leak.

**Why these patterns are not ``clarity.ai.pii``.** That module tokenises text
reversibly so a model's reply can be restored, and it lives in L3, above this
layer (I4). Log redaction is the opposite job: irreversible, cheap, and applied
to every line. The patterns are deliberately kept in step with that module's;
``tests/unit/test_log_masking.py`` checks both agree on what a number looks like.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

#: Sri Lankan mobile and landline numbers, with or without +94, spaces, hyphens.
#: Kept in step with ``clarity.ai.pii``.
_PHONE = re.compile(
    r"(?:\+94[\s-]?|0)(?:7\d|1\d|2\d|3\d|4\d|5\d|6\d|8\d|9\d)[\s-]?\d{3}[\s-]?\d{4}\b"
)
_NIC_OLD = re.compile(r"\b\d{9}[VvXx]\b")
_NIC_NEW = re.compile(r"\b\d{12}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")

#: Longest first: a card number contains digit runs a shorter pattern matches.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_CARD, "[card]"),
    (_PHONE, "[msisdn]"),
    (_NIC_NEW, "[nic]"),
    (_NIC_OLD, "[nic]"),
    (_EMAIL, "[email]"),
)

#: Fields whose value is replaced wholesale rather than pattern matched, because
#: a bare value carries no shape to recognise.
SENSITIVE_FIELDS = frozenset({"msisdn", "phone", "nic", "email", "password", "otp", "token"})


def redact(text: str) -> str:
    """Replace anything that looks like personal data with its kind.

    Irreversible by design: a log is not a place to keep something that can be
    turned back into a customer's number.
    """
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_value(key: str, value: Any) -> Any:
    """Redact one structured field, by its name and by its content."""
    if key.lower() in SENSITIVE_FIELDS:
        return "[redacted]"
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: redact_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    return value


class MaskingFilter(logging.Filter):
    """Redacts every record before a handler can format it.

    A filter rather than a formatter: a formatter applies to one handler, and a
    second handler added later would bypass it. Attached to the root logger,
    this sees everything.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            record.args = _redact_args(record.args)
        for key, value in list(vars(record).items()):
            if key in _RESERVED:
                continue
            setattr(record, key, redact_value(key, value))
        return True


def _redact_args(args: Any) -> Any:
    if isinstance(args, dict):
        return {k: redact_value(str(k), v) for k, v in args.items()}
    if isinstance(args, tuple):
        return tuple(redact_value("", item) for item in args)
    return args


#: ``LogRecord`` attributes that are machinery, not content.
_RESERVED = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with the trace and correlation ids attached.

    The ids are what make a log line findable from a trace and the other way
    round; without them structured logs are only tidier text.
    """

    def format(self, record: logging.LogRecord) -> str:
        from clarity.platform.messaging.correlation import current_correlation_id
        from clarity.platform.observability.tracing import current_span_id, current_trace_id

        payload: dict[str, Any] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if correlation := current_correlation_id():
            payload["correlation_id"] = correlation
        if trace := current_trace_id():
            payload["trace_id"] = trace
        if span_id := current_span_id():
            payload["span_id"] = span_id
        for key, value in vars(record).items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(*, log_format: str = "text", level: int = logging.INFO) -> None:
    """Install the masking filter and the chosen formatter on the root logger.

    Called once by the composition root. Idempotent: calling it again replaces
    the handler rather than adding a second one, so logs are not doubled.
    """
    root = logging.getLogger()
    root.setLevel(level)
    for existing in list(root.handlers):
        root.removeHandler(existing)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        JsonFormatter()
        if log_format == "json"
        else logging.Formatter("%(asctime)s %(levelname)-7s %(name)s %(message)s")
    )
    root.addHandler(handler)

    # Third-party request logs are not ours and are noisy at INFO. Raising
    # them here rather than silencing the root keeps our own lines at INFO.
    for noisy in ("httpx", "httpcore", "urllib3", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # On the root logger, so no handler anywhere can be added around it.
    for existing_filter in list(root.filters):
        if isinstance(existing_filter, MaskingFilter):
            root.removeFilter(existing_filter)
    root.addFilter(MaskingFilter())
    handler.addFilter(MaskingFilter())


def masking_is_installed(logger: logging.Logger | None = None) -> bool:
    """Whether redaction is active on this logger. Used by the masking tests."""
    target = logger or logging.getLogger()
    return any(isinstance(f, MaskingFilter) for f in target.filters)


__all__ = [
    "SENSITIVE_FIELDS",
    "JsonFormatter",
    "MaskingFilter",
    "configure_logging",
    "masking_is_installed",
    "redact",
    "redact_value",
]

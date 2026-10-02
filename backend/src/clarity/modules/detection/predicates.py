"""The predicate language rule packs are written in (plan §13.2).

A rule's ``conditions`` block is a small declarative tree evaluated against an
:class:`~clarity.contracts.timeline.EvidenceSnapshot`. It is intentionally *not*
a general expression language: rules decide money, so every construct must be
reviewable by a CX engineer and a finance approver, and must terminate.

Nodes
-----
``all`` / ``any`` / ``not``
    Boolean combinators.
``exists``
    ``{event, as, where?, after?, before?, within?}`` - binds a matching event
    to a name so later conditions can refer to ``$name.field``.
``absent``
    Same selector, asserts nothing matches. This is how "no OTP was ever
    verified" is expressed, which is the crux of a consent dispute.
``count``
    ``{event, where?, at_least?, at_most?}``.
``compare``
    ``{left, op, right}`` with ``op`` in ``eq ne lt lte gt gte``.

References
----------
``$name.field`` resolves against a bound event: ``at`` is the timestamp,
``amount`` the money value, anything else an attribute. Values that do not
start with ``$`` are literals.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from clarity.contracts.timeline import EventType, EvidenceSnapshot, TimelineEvent

Bindings = dict[str, TimelineEvent]

_SELECTOR_KEYS = {"event", "as", "where", "after", "before", "within", "at_least", "at_most"}
_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


class RuleSyntaxError(ValueError):
    """A rule pack is malformed. Raised at load time, never at decision time."""


def parse_duration(text: str) -> timedelta:
    """Parse the ISO-8601 subset used in rule packs (``P400D``, ``PT30M``)."""
    match = _DURATION_RE.match(text)
    if match is None or text in {"P", "PT"}:
        raise RuleSyntaxError(f"not a supported duration: {text!r} (use e.g. P30D, PT15M)")
    parts = {k: int(v) for k, v in match.groupdict().items() if v is not None}
    if not parts:
        raise RuleSyntaxError(f"empty duration: {text!r}")
    return timedelta(**parts)


def validate_condition(node: Any, *, path: str = "conditions") -> None:
    """Structurally validate a condition tree, so bad packs fail on load."""
    if not isinstance(node, dict) or len(node) != 1:
        raise RuleSyntaxError(f"{path}: expected a single-key mapping, got {node!r}")
    ((key, value),) = node.items()

    match key:
        case "all" | "any":
            if not isinstance(value, list) or not value:
                raise RuleSyntaxError(f"{path}.{key}: expected a non-empty list")
            for index, child in enumerate(value):
                validate_condition(child, path=f"{path}.{key}[{index}]")
        case "not":
            validate_condition(value, path=f"{path}.not")
        case "exists" | "absent" | "count":
            if not isinstance(value, dict):
                raise RuleSyntaxError(f"{path}.{key}: expected a mapping")
            unknown = set(value) - _SELECTOR_KEYS
            if unknown:
                raise RuleSyntaxError(f"{path}.{key}: unknown keys {sorted(unknown)}")
            if "event" not in value:
                raise RuleSyntaxError(f"{path}.{key}: 'event' is required")
            try:
                EventType(value["event"])
            except ValueError as error:
                raise RuleSyntaxError(f"{path}.{key}: unknown event {value['event']!r}") from error
            if key == "count" and not ({"at_least", "at_most"} & set(value)):
                raise RuleSyntaxError(f"{path}.count: needs 'at_least' and/or 'at_most'")
            for field in ("within",):
                if field in value:
                    parse_duration(str(value[field]))
        case "compare":
            if not isinstance(value, dict) or set(value) != {"left", "op", "right"}:
                raise RuleSyntaxError(f"{path}.compare: expected keys left, op, right")
            if value["op"] not in {"eq", "ne", "lt", "lte", "gt", "gte"}:
                raise RuleSyntaxError(f"{path}.compare: unsupported op {value['op']!r}")
        case _:
            raise RuleSyntaxError(f"{path}: unknown condition {key!r}")


def resolve(value: Any, bindings: Bindings) -> Any:
    """Resolve ``$name.field`` against bindings; return literals unchanged."""
    if not isinstance(value, str) or not value.startswith("$"):
        return value
    reference = value[1:]
    name, _, field = reference.partition(".")
    event = bindings.get(name)
    if event is None:
        raise RuleSyntaxError(f"reference to unbound event {name!r}")
    if not field:
        return event
    match field:
        case "at":
            return event.occurred_at
        case "amount":
            return event.amount_lkr
        case "id":
            return event.event_id
        case "source":
            return event.source.value
        case _:
            return event.attr(field)


def _coerce_pair(left: Any, right: Any) -> tuple[Any, Any]:
    """Make two values comparable without silently equating different types."""
    if isinstance(left, Decimal) or isinstance(right, Decimal):

        def as_decimal(value: Any) -> Any:
            if isinstance(value, Decimal):
                return value
            if isinstance(value, int | str):
                try:
                    return Decimal(str(value))
                except ArithmeticError:
                    return value
            return value

        return as_decimal(left), as_decimal(right)
    if isinstance(left, datetime) and isinstance(right, datetime):
        return left, right
    if isinstance(left, bool) or isinstance(right, bool):
        return left, right
    if isinstance(left, str) and isinstance(right, int | float):
        return left, str(right)
    if isinstance(right, str) and isinstance(left, int | float):
        return str(left), right
    return left, right


def matches_selector(event: TimelineEvent, selector: dict[str, Any], bindings: Bindings) -> bool:
    """Does one event satisfy a selector's event type, filters and time bounds?"""
    if event.event_type is not EventType(selector["event"]):
        return False

    for field, expected in (selector.get("where") or {}).items():
        actual = event.attr(field)
        wanted = resolve(expected, bindings)
        left, right = _coerce_pair(actual, wanted)
        if left != right:
            return False

    after = selector.get("after")
    if after is not None:
        bound = resolve(after, bindings)
        if not isinstance(bound, datetime) or event.occurred_at <= bound:
            return False

    before = selector.get("before")
    if before is not None:
        bound = resolve(before, bindings)
        if not isinstance(bound, datetime) or event.occurred_at >= bound:
            return False

    within = selector.get("within")
    if within is not None:
        span = parse_duration(str(within))
        anchor = resolve(before or after, bindings) if (before or after) else None
        if isinstance(anchor, datetime) and abs(event.occurred_at - anchor) > span:
            return False

    return True


def _candidates(
    snapshot: EvidenceSnapshot, selector: dict[str, Any], bindings: Bindings
) -> list[TimelineEvent]:
    return [e for e in snapshot.events if matches_selector(e, selector, bindings)]


def solve(
    node: dict[str, Any], snapshot: EvidenceSnapshot, bindings: Bindings | None = None
) -> Iterator[Bindings]:
    """Yield every binding set that satisfies ``node``.

    Yielding (rather than returning the first) lets ``all`` backtrack: if the
    first candidate event for ``exists`` makes a later condition fail, the next
    candidate is tried. Evidence is finite and conditions cannot recurse, so
    this always terminates.
    """
    current: Bindings = dict(bindings or {})
    ((key, value),) = node.items()

    match key:
        case "all":
            yield from _solve_all(list(value), snapshot, current)
        case "any":
            for child in value:
                yield from solve(child, snapshot, current)
        case "not":
            if next(solve(value, snapshot, current), None) is None:
                yield current
        case "exists":
            candidates = _candidates(snapshot, value, current)
            name = value.get("as")
            if name is None:
                # Pure existence test: yield once, so it cannot multiply the
                # solution space of an enclosing `all`.
                if candidates:
                    yield current
            else:
                for event in candidates:
                    yield {**current, str(name): event}
        case "absent":
            if not _candidates(snapshot, value, current):
                yield current
        case "count":
            found = len(_candidates(snapshot, value, current))
            at_least = value.get("at_least")
            at_most = value.get("at_most")
            if (at_least is None or found >= int(at_least)) and (
                at_most is None or found <= int(at_most)
            ):
                yield current
        case "compare":
            left, right = _coerce_pair(
                resolve(value["left"], current), resolve(value["right"], current)
            )
            if _compare(left, value["op"], right):
                yield current
        case _:  # pragma: no cover - validate_condition rejects this earlier
            raise RuleSyntaxError(f"unknown condition {key!r}")


def _solve_all(
    nodes: list[dict[str, Any]], snapshot: EvidenceSnapshot, bindings: Bindings
) -> Iterator[Bindings]:
    if not nodes:
        yield bindings
        return
    head, *rest = nodes
    for solution in solve(head, snapshot, bindings):
        yield from _solve_all(rest, snapshot, solution)


def _compare(left: Any, op: str, right: Any) -> bool:
    try:
        match op:
            case "eq":
                return bool(left == right)
            case "ne":
                return bool(left != right)
            case "lt":
                return bool(left < right)
            case "lte":
                return bool(left <= right)
            case "gt":
                return bool(left > right)
            case "gte":
                return bool(left >= right)
    except TypeError:
        # Comparing incompatible types means the condition is simply not met.
        return False
    return False


def first_solution(node: dict[str, Any], snapshot: EvidenceSnapshot) -> Bindings | None:
    """Deterministic first satisfying binding set, or ``None``."""
    return next(solve(node, snapshot), None)

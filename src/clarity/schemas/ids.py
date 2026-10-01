"""Identifier generation.

ULIDs sort by creation time, which keeps case, decision and action ids readable
in logs and stable in indexes.
"""

from __future__ import annotations

from ulid import ULID


def new_id(prefix: str) -> str:
    """e.g. ``new_id("DEC")`` -> ``DEC-01J9Z...``."""
    return f"{prefix}-{ULID()}"


def case_no(sequence: int, *, year: int) -> str:
    """Human-quotable case number, e.g. ``CASE-2027-000184``."""
    return f"CASE-{year}-{sequence:06d}"


def receipt_id(sequence: int, *, year: int) -> str:
    """Human-quotable receipt id customers read out on 1788 (deck S6)."""
    return f"TR-{year}-{sequence:06d}"

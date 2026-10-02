"""Typed identifiers."""

from __future__ import annotations

from typing import NewType

from ulid import ULID

CaseId = NewType("CaseId", str)
DecisionId = NewType("DecisionId", str)
ActionId = NewType("ActionId", str)
ReceiptId = NewType("ReceiptId", str)


def new_id(prefix: str) -> str:
    return f"{prefix}-{ULID()}"


def case_no(sequence: int, *, year: int) -> str:
    return f"CASE-{year}-{sequence:06d}"


def receipt_id(sequence: int, *, year: int) -> str:
    return f"TR-{year}-{sequence:06d}"

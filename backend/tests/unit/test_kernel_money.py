"""Money must never accept binary floats."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from clarity.kernel import ClarityModel, Money, money


class _Amount(ClarityModel):
    amount: Money


def test_money_rejects_float() -> None:
    with pytest.raises(ValueError, match="float"):
        money(1.23)

    with pytest.raises(ValidationError):
        _Amount(amount=9.99)  # type: ignore[arg-type]


def test_money_accepts_decimal_string() -> None:
    assert money("12.50") == money("12.5")
    model = _Amount(amount="3.14")
    assert str(model.amount) == "3.14"

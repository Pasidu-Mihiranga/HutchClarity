"""Golden tests for detector plugins (positive + negative cases)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from clarity.modules.detection.domain.registry import run_all
from clarity.modules.detection.public import detect

pytestmark = pytest.mark.golden


def _matched(timeline: dict, rule_id: str):
    for item in detect(timeline):
        if item.rule_id == rule_id:
            return item
    return None


# --------------------------------------------------------------------------- #
# VAS_SILENT_RENEWAL
# --------------------------------------------------------------------------- #


def test_vas_silent_renewal_positive():
    timeline = {
        "vas": [
            {
                "id": "vas-1",
                "type": "renewal",
                "subscription_id": "SUB-1",
                "product": "Daily game",
                "amount_lkr": "49.00",
                "at": "2027-09-14T10:00:00+00:00",
            }
        ],
        "notifications": [],
        "consents": [],
    }
    found = _matched(timeline, "VAS_SILENT_RENEWAL")
    assert found is not None
    assert found.confidence >= 0.9
    assert found.amount_lkr == Decimal("49.00")


def test_vas_silent_renewal_negative_when_notice_present():
    timeline = {
        "vas": [
            {
                "id": "vas-1",
                "type": "renewal",
                "subscription_id": "SUB-1",
                "product": "Daily game",
                "amount_lkr": "49.00",
                "at": "2027-09-14T10:00:00+00:00",
            }
        ],
        "notifications": [
            {
                "kind": "renewal_notice",
                "subscription_id": "SUB-1",
                "at": "2027-09-13T10:00:00+00:00",
            }
        ],
        "consents": [],
    }
    assert _matched(timeline, "VAS_SILENT_RENEWAL") is None


# --------------------------------------------------------------------------- #
# DOUBLE_CHARGE
# --------------------------------------------------------------------------- #


def test_double_charge_positive():
    timeline = {
        "charges": [
            {
                "id": "c1",
                "amount_lkr": "100.00",
                "product": "Reload",
                "merchant_id": "M1",
                "at": "2027-09-14T08:00:00+00:00",
            },
            {
                "id": "c2",
                "amount_lkr": "100.00",
                "product": "Reload",
                "merchant_id": "M1",
                "at": "2027-09-14T08:03:00+00:00",
            },
        ]
    }
    found = _matched(timeline, "DOUBLE_CHARGE")
    assert found is not None
    assert found.confidence >= 0.95
    assert found.amount_lkr == Decimal("100.00")


def test_double_charge_negative_different_amounts():
    timeline = {
        "charges": [
            {
                "id": "c1",
                "amount_lkr": "100.00",
                "product": "Reload",
                "merchant_id": "M1",
                "at": "2027-09-14T08:00:00+00:00",
            },
            {
                "id": "c2",
                "amount_lkr": "200.00",
                "product": "Reload",
                "merchant_id": "M1",
                "at": "2027-09-14T08:03:00+00:00",
            },
        ]
    }
    assert _matched(timeline, "DOUBLE_CHARGE") is None


# --------------------------------------------------------------------------- #
# POST_PACK_BURN_RISK
# --------------------------------------------------------------------------- #


def test_post_pack_burn_risk_positive():
    timeline = {
        "packs": [
            {
                "id": "pack-1",
                "remaining_gb": 3.2,
                "hours_remaining": 6,
                "status": "active",
            }
        ],
        "usage": [],
    }
    found = _matched(timeline, "POST_PACK_BURN_RISK")
    assert found is not None
    assert found.confidence >= 0.78


def test_post_pack_burn_risk_negative_plenty_of_time():
    timeline = {
        "packs": [
            {
                "id": "pack-1",
                "remaining_gb": 3.2,
                "hours_remaining": 72,
                "status": "active",
            }
        ],
        "usage": [],
    }
    assert _matched(timeline, "POST_PACK_BURN_RISK") is None


def test_registry_exposes_seventeen_detectors():
    from clarity.modules.detection.domain.registry import DETECTORS, rule_ids

    ids = rule_ids()
    assert len(DETECTORS) == 17
    assert "VAS_SILENT_RENEWAL" in ids
    assert "DOUBLE_CHARGE" in ids
    assert "POST_PACK_BURN_RISK" in ids
    # Empty timeline produces no detections
    assert run_all({}) == []

"""JSON decision tables (JDM-like) mapping rule_id -> remedy."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Each entry is a compact GoRules-ZEN / JDM style decision table row set.
# Formulas use simple tokens: $amount, $cap, $detection.amount_lkr

ZEN_TABLES: dict[str, dict[str, Any]] = {
    "VAS_SILENT_RENEWAL": {
        "table_id": "clarity.decision.vas_silent_renewal",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "REFUND",
            "refund_amount": "$detection.amount_lkr",
            "requires_approval": False,
            "cap_lkr": "1000.00",
            "outcome_hint": "ONE_TAP_FIX",
        },
    },
    "DOUBLE_CHARGE": {
        "table_id": "clarity.decision.double_charge",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "REFUND",
            "refund_amount": "$detection.amount_lkr",
            "requires_approval": False,
            "cap_lkr": "1000.00",
            "outcome_hint": "AUTO_FIX",
            "auto_whitelisted": True,
        },
    },
    "FUP_SURPRISE": {
        "table_id": "clarity.decision.fup_surprise",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "GOODWILL_CREDIT",
            "refund_amount": "min($detection.amount_lkr, 500)",
            "requires_approval": True,
            "cap_lkr": "5000.00",
            "outcome_hint": "STAFF_APPROVAL",
        },
    },
    "LOAN_STACKING": {
        "table_id": "clarity.decision.loan_stacking",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "EXPLAIN",
            "refund_amount": "0",
            "requires_approval": False,
            "cap_lkr": "0",
            "outcome_hint": "EXPLAIN_ONLY",
        },
    },
    "WRONG_PACK": {
        "table_id": "clarity.decision.wrong_pack",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "SWAP_PACK",
            "refund_amount": "$detection.amount_lkr",
            "requires_approval": False,
            "cap_lkr": "5000.00",
            "outcome_hint": "ONE_TAP_FIX",
        },
    },
    "OUTAGE_CREDIT": {
        "table_id": "clarity.decision.outage_credit",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "GOODWILL_CREDIT",
            "refund_amount": "$detection.amount_lkr",
            "requires_approval": True,
            "cap_lkr": "5000.00",
            "outcome_hint": "STAFF_APPROVAL",
        },
    },
    "VAS_RENEWAL_UNNOTIFIED": {
        "table_id": "clarity.decision.vas_renewal_unnotified",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "REFUND",
            "refund_amount": "$detection.amount_lkr",
            "requires_approval": False,
            "cap_lkr": "1000.00",
            "outcome_hint": "ONE_TAP_FIX",
        },
    },
    "PAYMENT_PENDING_SETTLEMENT": {
        "table_id": "clarity.decision.payment_pending",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "EXPLAIN",
            "refund_amount": "0",
            "requires_approval": False,
            "cap_lkr": "0",
            "outcome_hint": "EXPLAIN_ONLY",
        },
    },
    "FUP_NOT_DISCLOSED": {
        "table_id": "clarity.decision.fup_not_disclosed",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "GOODWILL_CREDIT",
            "refund_amount": "min($detection.amount_lkr, 1000)",
            "requires_approval": True,
            "cap_lkr": "5000.00",
            "outcome_hint": "STAFF_APPROVAL",
        },
    },
    "PACK_MISMATCH": {
        "table_id": "clarity.decision.pack_mismatch",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "SWAP_PACK",
            "refund_amount": "$detection.amount_lkr",
            "requires_approval": False,
            "cap_lkr": "5000.00",
            "outcome_hint": "ONE_TAP_FIX",
        },
    },
    "SOCIAL_PACK_SCOPE": {
        "table_id": "clarity.decision.social_pack_scope",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "EXPLAIN",
            "refund_amount": "0",
            "requires_approval": False,
            "cap_lkr": "0",
            "outcome_hint": "EXPLAIN_ONLY",
        },
    },
    "PACK_SUNSET": {
        "table_id": "clarity.decision.pack_sunset",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "EXPLAIN",
            "refund_amount": "0",
            "requires_approval": False,
            "cap_lkr": "0",
            "outcome_hint": "EXPLAIN_ONLY",
        },
    },
    "LOAN_RECOVERY": {
        "table_id": "clarity.decision.loan_recovery",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "EXPLAIN",
            "refund_amount": "0",
            "requires_approval": False,
            "cap_lkr": "0",
            "outcome_hint": "EXPLAIN_ONLY",
        },
    },
    "BALANCE_BURN_PAYG": {
        "table_id": "clarity.decision.balance_burn_payg",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "OFFER_PACK",
            "refund_amount": "0",
            "requires_approval": False,
            "cap_lkr": "0",
            "outcome_hint": "EXPLAIN_ONLY",
        },
    },
    "WRONG_PACK_PURCHASE": {
        "table_id": "clarity.decision.wrong_pack_purchase",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "SWAP_PACK",
            "refund_amount": "$detection.amount_lkr",
            "requires_approval": False,
            "cap_lkr": "5000.00",
            "outcome_hint": "ONE_TAP_FIX",
        },
    },
    "OUTAGE_DURING_PACK": {
        "table_id": "clarity.decision.outage_during_pack",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "GOODWILL_CREDIT",
            "refund_amount": "$detection.amount_lkr",
            "requires_approval": True,
            "cap_lkr": "5000.00",
            "outcome_hint": "STAFF_APPROVAL",
        },
    },
    "POST_PACK_BURN_RISK": {
        "table_id": "clarity.decision.post_pack_burn_risk",
        "version": "1",
        "hit_policy": "first",
        "remedy": {
            "action_type": "PROACTIVE_OFFER",
            "refund_amount": "0",
            "requires_approval": False,
            "cap_lkr": "0",
            "outcome_hint": "EXPLAIN_ONLY",
        },
    },
}

DEFAULT_CAPS: dict[str, str] = {
    "auto_cap_lkr": "1000.00",
    "one_tap_cap_lkr": "5000.00",
    "four_eyes_threshold_lkr": "25000.00",
    "sim_swap_window_days": "7",
}


def table_for(rule_id: str) -> dict[str, Any] | None:
    table = ZEN_TABLES.get(rule_id)
    return deepcopy(table) if table else None


def all_tables() -> dict[str, dict[str, Any]]:
    return deepcopy(ZEN_TABLES)

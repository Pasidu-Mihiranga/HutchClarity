"""Unified Clarity chat intent catalogue."""

from __future__ import annotations

from enum import StrEnum


class Intent(StrEnum):
    BALANCE_DEDUCTION_QUERY = "BALANCE_DEDUCTION_QUERY"
    UNEXPECTED_CHARGE = "UNEXPECTED_CHARGE"
    RELOAD_MISSING = "RELOAD_MISSING"
    DATA_SLOW = "DATA_SLOW"
    FUP_QUERY = "FUP_QUERY"
    PACK_NOT_WORKING = "PACK_NOT_WORKING"
    PACK_ACTIVATE = "PACK_ACTIVATE"
    PACK_MISSING = "PACK_MISSING"
    PACK_RECOMMEND = "PACK_RECOMMEND"
    PACK_EXPIRY = "PACK_EXPIRY"
    VAS_SUBSCRIPTIONS = "VAS_SUBSCRIPTIONS"
    ESIM_HELP = "ESIM_HELP"
    NETWORK_STATUS = "NETWORK_STATUS"
    REFUND_STATUS = "REFUND_STATUS"
    CASE_STATUS = "CASE_STATUS"
    PREVENT_CHARGES = "PREVENT_CHARGES"
    DOUBLE_CHARGE = "DOUBLE_CHARGE"
    HANDOFF = "HANDOFF"
    FALLBACK = "FALLBACK"


class Route(StrEnum):
    ACCOUNT = "account"
    KNOWLEDGE = "knowledge"
    HANDOFF = "handoff"
    BOTH = "both"


# Catalogue for suggestions / "see more topics" (stable keys for i18n).
TOPIC_CATALOGUE: list[dict[str, str]] = [
    {"id": "balance", "intent": Intent.BALANCE_DEDUCTION_QUERY.value, "i18n_key": "qBalance"},
    {"id": "unexpected", "intent": Intent.UNEXPECTED_CHARGE.value, "i18n_key": "qSub"},
    {"id": "reload", "intent": Intent.RELOAD_MISSING.value, "i18n_key": "qMissing"},
    {"id": "slow", "intent": Intent.DATA_SLOW.value, "i18n_key": "qSlow"},
    {"id": "fup", "intent": Intent.FUP_QUERY.value, "i18n_key": "qFup"},
    {"id": "pack_issue", "intent": Intent.PACK_NOT_WORKING.value, "i18n_key": "qPackIssue"},
    {"id": "pack_activate", "intent": Intent.PACK_ACTIVATE.value, "i18n_key": "qActivate"},
    {"id": "pack_missing", "intent": Intent.PACK_MISSING.value, "i18n_key": "qPackMissing"},
    {"id": "recommend", "intent": Intent.PACK_RECOMMEND.value, "i18n_key": "qRecommend"},
    {"id": "expiry", "intent": Intent.PACK_EXPIRY.value, "i18n_key": "qExpiry"},
    {"id": "vas", "intent": Intent.VAS_SUBSCRIPTIONS.value, "i18n_key": "qVasList"},
    {"id": "esim", "intent": Intent.ESIM_HELP.value, "i18n_key": "qEsim"},
    {"id": "network", "intent": Intent.NETWORK_STATUS.value, "i18n_key": "qNetwork"},
    {"id": "refund", "intent": Intent.REFUND_STATUS.value, "i18n_key": "qRefund"},
    {"id": "case", "intent": Intent.CASE_STATUS.value, "i18n_key": "qCase"},
    {"id": "prevent", "intent": Intent.PREVENT_CHARGES.value, "i18n_key": "qPrevent"},
    {"id": "twice", "intent": Intent.DOUBLE_CHARGE.value, "i18n_key": "qTwice"},
]

"""Map chat intents to account evaluate / knowledge / handoff routes."""

from __future__ import annotations

from typing import Any

from clarity.modules.conversation.domain.intents import Intent, Route

# Legacy client evaluate intents used by static UI + cases service.
_CLIENT_INTENT: dict[str, str] = {
    Intent.BALANCE_DEDUCTION_QUERY.value: "balance",
    Intent.UNEXPECTED_CHARGE.value: "sub",
    Intent.VAS_SUBSCRIPTIONS.value: "sub",
    Intent.DOUBLE_CHARGE.value: "twice",
    Intent.RELOAD_MISSING.value: "missing",
    Intent.PACK_MISSING.value: "missing",
    Intent.DATA_SLOW.value: "slow",
    Intent.FUP_QUERY.value: "slow",
    Intent.PACK_NOT_WORKING.value: "slow",
    Intent.PACK_EXPIRY.value: "balance",
    Intent.REFUND_STATUS.value: "balance",
    Intent.CASE_STATUS.value: "balance",
    Intent.PREVENT_CHARGES.value: "knowledge",
    Intent.PACK_RECOMMEND.value: "knowledge",
    Intent.PACK_ACTIVATE.value: "knowledge",
    Intent.ESIM_HELP.value: "knowledge",
    Intent.NETWORK_STATUS.value: "knowledge",
    Intent.HANDOFF.value: "human",
    Intent.FALLBACK.value: "balance",
}

_ROUTE: dict[str, str] = {
    Intent.BALANCE_DEDUCTION_QUERY.value: Route.ACCOUNT.value,
    Intent.UNEXPECTED_CHARGE.value: Route.ACCOUNT.value,
    Intent.VAS_SUBSCRIPTIONS.value: Route.ACCOUNT.value,
    Intent.DOUBLE_CHARGE.value: Route.ACCOUNT.value,
    Intent.RELOAD_MISSING.value: Route.ACCOUNT.value,
    Intent.PACK_MISSING.value: Route.ACCOUNT.value,
    Intent.DATA_SLOW.value: Route.ACCOUNT.value,
    Intent.FUP_QUERY.value: Route.ACCOUNT.value,
    Intent.PACK_NOT_WORKING.value: Route.ACCOUNT.value,
    Intent.PACK_EXPIRY.value: Route.ACCOUNT.value,
    Intent.REFUND_STATUS.value: Route.ACCOUNT.value,
    Intent.CASE_STATUS.value: Route.ACCOUNT.value,
    Intent.PREVENT_CHARGES.value: Route.KNOWLEDGE.value,
    Intent.PACK_RECOMMEND.value: Route.KNOWLEDGE.value,
    Intent.PACK_ACTIVATE.value: Route.KNOWLEDGE.value,
    Intent.ESIM_HELP.value: Route.KNOWLEDGE.value,
    Intent.NETWORK_STATUS.value: Route.BOTH.value,
    Intent.HANDOFF.value: Route.HANDOFF.value,
    Intent.FALLBACK.value: Route.ACCOUNT.value,
}

_FOLLOW_UPS: dict[str, list[dict[str, str]]] = {
    Intent.UNEXPECTED_CHARGE.value: [
        {"id": "disable", "i18n_key": "fuDisable", "intent": Intent.VAS_SUBSCRIPTIONS.value},
        {"id": "subs", "i18n_key": "fuSubs", "intent": Intent.VAS_SUBSCRIPTIONS.value},
        {"id": "prevent", "i18n_key": "fuPrevent", "intent": Intent.PREVENT_CHARGES.value},
        {"id": "support", "i18n_key": "fuSupport", "intent": Intent.HANDOFF.value},
    ],
    Intent.BALANCE_DEDUCTION_QUERY.value: [
        {"id": "subs", "i18n_key": "fuSubs", "intent": Intent.VAS_SUBSCRIPTIONS.value},
        {"id": "prevent", "i18n_key": "fuPrevent", "intent": Intent.PREVENT_CHARGES.value},
        {"id": "support", "i18n_key": "fuSupport", "intent": Intent.HANDOFF.value},
    ],
    Intent.DATA_SLOW.value: [
        {"id": "fup", "i18n_key": "fuFup", "intent": Intent.FUP_QUERY.value},
        {"id": "usage", "i18n_key": "fuUsage", "intent": Intent.FUP_QUERY.value},
        {"id": "buy", "i18n_key": "fuBuy", "intent": Intent.PACK_RECOMMEND.value},
        {"id": "network", "i18n_key": "fuNetwork", "intent": Intent.NETWORK_STATUS.value},
    ],
    Intent.FUP_QUERY.value: [
        {"id": "usage", "i18n_key": "fuUsage", "intent": Intent.FUP_QUERY.value},
        {"id": "buy", "i18n_key": "fuBuy", "intent": Intent.PACK_RECOMMEND.value},
        {"id": "network", "i18n_key": "fuNetwork", "intent": Intent.NETWORK_STATUS.value},
    ],
    Intent.PACK_RECOMMEND.value: [
        {"id": "compare", "i18n_key": "fuCompare", "intent": Intent.PACK_RECOMMEND.value},
        {"id": "details", "i18n_key": "fuDetails", "intent": Intent.PACK_RECOMMEND.value},
        {"id": "activate", "i18n_key": "fuActivate", "intent": Intent.PACK_ACTIVATE.value},
    ],
    Intent.ESIM_HELP.value: [
        {"id": "support", "i18n_key": "fuSupport", "intent": Intent.HANDOFF.value},
    ],
    Intent.HANDOFF.value: [],
}


def route_for(intent: str) -> str:
    return _ROUTE.get(intent, Route.ACCOUNT.value)


def client_intent_for(intent: str) -> str:
    """Map to legacy evaluate intent (balance/sub/twice/slow/missing/knowledge/human)."""
    return _CLIENT_INTENT.get(intent, "balance")


def follow_ups_for(intent: str) -> list[dict[str, str]]:
    return list(_FOLLOW_UPS.get(intent, [
        {"id": "support", "i18n_key": "fuSupport", "intent": Intent.HANDOFF.value},
        {"id": "balance", "i18n_key": "qBalance", "intent": Intent.BALANCE_DEDUCTION_QUERY.value},
    ]))


def routing_payload(intent: str) -> dict[str, Any]:
    return {
        "intent": intent,
        "route": route_for(intent),
        "client_intent": client_intent_for(intent),
        "follow_ups": follow_ups_for(intent),
    }

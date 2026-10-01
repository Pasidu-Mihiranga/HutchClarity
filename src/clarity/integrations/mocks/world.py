"""A synthetic HUTCH, good enough to decide real-shaped cases.

**Everything here is simulated.** No HUTCH system, API, schema or data was
available (Guidelines §4). The world models only what the deck's causes need:
balances, charges, payments, VAS subscriptions with consent evidence, packs
with FUP terms, usage counters, loans and identity/risk signals.

It is deliberately stateful: a refund really credits the balance, a
deactivation really stops a subscription, and a merchant block is really
readable afterwards. That makes before/after values on a Trust Receipt and the
recurrence test ("PASSED only if really blocked", deck S6) honest rather than
decorative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from clarity.schemas.common import (
    EventSource,
    Language,
    mask_msisdn,
    money,
    normalise_msisdn,
    subscriber_ref,
)
from clarity.schemas.timeline import EventType, TimelineEvent

#: Demo HMAC key. A real deployment keeps this in the KMS (plan §19).
DEMO_SUBSCRIBER_KEY = b"clarity-demo-subscriber-key-not-a-secret"

#: Fixed "now" so the demo is reproducible and screenshots stay stable.
DEMO_NOW = datetime(2027, 9, 14, 18, 0, tzinfo=UTC)


def ref_for(msisdn: str) -> str:
    return subscriber_ref(msisdn, key=DEMO_SUBSCRIBER_KEY)


@dataclass
class Subscription:
    """A VAS/DCB subscription, with the consent evidence that decides disputes."""

    subscription_id: str
    merchant_id: str
    merchant_name: str
    product: str
    price_lkr: Decimal
    active: bool = True
    otp_verified_at: datetime | None = None
    second_confirmation_at: datetime | None = None


@dataclass
class Pack:
    """A data pack as sold, including the FUP terms shown at purchase."""

    offering_id: str
    name: str
    price_lkr: Decimal
    purchased_at: datetime
    expires_at: datetime
    catalogue_version: str
    fup_cap_gb: Decimal | None = None
    after_cap_speed: str | None = None
    fup_disclosed_at_purchase: bool = True
    active: bool = True


@dataclass
class Account:
    """One synthetic subscriber and everything the eight sources know about them."""

    msisdn: str
    balance_lkr: Decimal
    language: Language = Language.EN
    segment: str = "prepaid"
    subscriptions: list[Subscription] = field(default_factory=list)
    packs: list[Pack] = field(default_factory=list)
    safeguards: dict[str, Any] = field(default_factory=dict)
    blocked_merchants: set[str] = field(default_factory=set)
    sim_swap_at: datetime | None = None
    fraud_flag: bool = False
    refunds_last_30d: int = 0
    #: Raw source records, keyed by source. Mock drivers filter these by window.
    records: dict[EventSource, list[TimelineEvent]] = field(default_factory=dict)

    @property
    def ref(self) -> str:
        return ref_for(self.msisdn)

    @property
    def masked(self) -> str:
        return mask_msisdn(self.msisdn)

    def add(self, event: TimelineEvent) -> TimelineEvent:
        self.records.setdefault(event.source, []).append(event)
        return event


class SyntheticWorld:
    """In-memory stand-in for the HUTCH estate."""

    def __init__(self, *, now: datetime = DEMO_NOW) -> None:
        self.now = now
        self._accounts: dict[str, Account] = {}
        self._seq = 0
        #: Sources the operator has marked unavailable, to demo degradation.
        self.unavailable: set[EventSource] = set()

    # -- construction ------------------------------------------------------ #

    def next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq:06d}"

    def add_account(self, account: Account) -> Account:
        self._accounts[account.ref] = account
        return account

    def account(self, ref: str) -> Account | None:
        return self._accounts.get(ref)

    def account_by_msisdn(self, msisdn: str) -> Account | None:
        return self._accounts.get(ref_for(normalise_msisdn(msisdn)))

    def accounts(self) -> list[Account]:
        return list(self._accounts.values())

    def event(
        self,
        account: Account,
        source: EventSource,
        event_type: EventType,
        occurred_at: datetime,
        *,
        amount_lkr: Any | None = None,
        **attributes: Any,
    ) -> TimelineEvent:
        """Create and file a source record."""
        return account.add(
            TimelineEvent(
                event_id=self.next_id("ev"),
                source=source,
                event_type=event_type,
                source_event_id=self.next_id(source.value[:3]),
                occurred_at=occurred_at,
                amount_lkr=amount_lkr,
                attributes=attributes,
                adapter_version="mock-0.1.0",
            )
        )

    # -- state changes the tool layer drives ------------------------------- #

    def credit_balance(self, ref: str, amount: Decimal, *, reason: str) -> tuple[Decimal, Decimal]:
        """Apply a refund/credit. Returns (before, after)."""
        account = self._require(ref)
        before = account.balance_lkr
        account.balance_lkr = money(before + amount)
        self.event(
            account,
            EventSource.CHARGING,
            EventType.BALANCE_CREDITED,
            self.now,
            amount_lkr=amount,
            reason=reason,
            balance_before=str(before),
            balance_after=str(account.balance_lkr),
        )
        return before, account.balance_lkr

    def deactivate_subscription(self, ref: str, subscription_id: str) -> bool:
        account = self._require(ref)
        for sub in account.subscriptions:
            if sub.subscription_id == subscription_id:
                was_active, sub.active = sub.active, False
                self.event(
                    account,
                    EventSource.VAS_CONSENT,
                    EventType.SUBSCRIPTION_DEACTIVATED,
                    self.now,
                    subscription_id=subscription_id,
                    merchant_id=sub.merchant_id,
                )
                return was_active
        return False

    def block_merchant(self, ref: str, merchant_id: str) -> bool:
        account = self._require(ref)
        already = merchant_id in account.blocked_merchants
        account.blocked_merchants.add(merchant_id)
        return not already

    def is_merchant_blocked(self, ref: str, merchant_id: str) -> bool:
        """Backs the recurrence test on the Trust Receipt."""
        return merchant_id in self._require(ref).blocked_merchants

    def set_safeguard(self, ref: str, kind: str, params: dict[str, Any]) -> dict[str, Any]:
        account = self._require(ref)
        before = dict(account.safeguards)
        account.safeguards[kind] = params
        return before

    def _require(self, ref: str) -> Account:
        account = self._accounts.get(ref)
        if account is None:
            raise KeyError(f"unknown subscriber_ref {ref!r}")
        return account


# --------------------------------------------------------------------------- #
# Demo scenarios — one per prototype journey (plan §1.9, §6)
# --------------------------------------------------------------------------- #


def build_demo_world(now: datetime = DEMO_NOW) -> SyntheticWorld:
    """Build the four journeys the prototype demonstrates.

    Numbers follow the deck's examples so the demo matches the pitch: a
    LKR 49 VAS charge at 14:06 with no OTP (S6/S7), a LKR 3,500 reload taken
    twice (S2), an "unlimited" pack hitting a disclosed FUP (S2), and a large
    disputed reload with a recent SIM swap (S7).
    """
    world = SyntheticWorld(now=now)
    _journey_vas_no_consent(world)
    _journey_duplicate_reload(world)
    _journey_fup_explain_only(world)
    _journey_high_risk_reload(world)
    return world


def _journey_vas_no_consent(world: SyntheticWorld) -> Account:
    """Dilani: LKR 49 daily game subscription charged with no OTP (deck S6)."""
    now = world.now
    charged_at = now.replace(hour=14, minute=6, second=0, microsecond=0)
    account = world.add_account(
        Account(
            msisdn="+94771234567",
            balance_lkr=money("263.00"),
            language=Language.SI,
            subscriptions=[
                Subscription(
                    subscription_id="SUB-GAME-1",
                    merchant_id="MER-GAMEHUB",
                    merchant_name="GameHub",
                    product="Daily game subscription",
                    price_lkr=money("49.00"),
                    otp_verified_at=None,  # the whole point: no consent evidence
                )
            ],
            packs=[
                Pack(
                    offering_id="PKG-DATA-30",
                    name="30-Day Data 10GB",
                    price_lkr=money("999.00"),
                    purchased_at=now - timedelta(days=12),
                    expires_at=now + timedelta(days=18),
                    catalogue_version="2027.08",
                    fup_cap_gb=money("10.00"),
                    after_cap_speed="512 kbps",
                )
            ],
        )
    )
    world.event(
        account,
        EventSource.CHARGING,
        EventType.VAS_CHARGE,
        charged_at,
        amount_lkr=money("49.00"),
        subscription_id="SUB-GAME-1",
        merchant_id="MER-GAMEHUB",
        merchant_name="GameHub",
        product="Daily game subscription",
        balance_before="312.00",
        balance_after="263.00",
    )
    # Evidence that rules out other causes: data remains, no loan recovery.
    world.event(
        account,
        EventSource.USAGE_FUP,
        EventType.DATA_SESSION,
        charged_at - timedelta(hours=2),
        bucket="PKG-DATA-30",
        remaining_gb="3.2",
    )
    return account


def _journey_duplicate_reload(world: SyntheticWorld) -> Account:
    """Nimal: bank took LKR 3,500 twice, balance credited once (deck S2)."""
    now = world.now
    first = now - timedelta(minutes=14)
    second = now - timedelta(minutes=11)
    account = world.add_account(
        Account(msisdn="+94772223333", balance_lkr=money("3500.00"), language=Language.EN)
    )
    for captured_at in (first, second):
        world.event(
            account,
            EventSource.PAYMENTS,
            EventType.PAYMENT_CAPTURED,
            captured_at,
            amount_lkr=money("3500.00"),
            payment_ref=world.next_id("pay"),
            bank_ref="BANKREF-77821",
            channel="bank_app",
            status="captured",
        )
    world.event(
        account,
        EventSource.CHARGING,
        EventType.BALANCE_CREDITED,
        first + timedelta(seconds=40),
        amount_lkr=money("3500.00"),
        bank_ref="BANKREF-77821",
        reason="reload",
        balance_before="0.00",
        balance_after="3500.00",
    )
    return account


def _journey_fup_explain_only(world: SyntheticWorld) -> Account:
    """Kumar: "unlimited" pack hit a FUP cap that was disclosed (deck S2)."""
    now = world.now
    account = world.add_account(
        Account(
            msisdn="+94773334444",
            balance_lkr=money("120.00"),
            language=Language.TA,
            packs=[
                Pack(
                    offering_id="PKG-UNLTD",
                    name="Unlimited Data",
                    price_lkr=money("1499.00"),
                    purchased_at=now - timedelta(days=26),
                    expires_at=now + timedelta(days=4),
                    catalogue_version="2027.07",
                    fup_cap_gb=money("50.00"),
                    after_cap_speed="256 kbps",
                    fup_disclosed_at_purchase=True,
                )
            ],
        )
    )
    world.event(
        account,
        EventSource.USAGE_FUP,
        EventType.FUP_CAP_REACHED,
        now - timedelta(hours=4),
        bucket="PKG-UNLTD",
        cap_gb="50.00",
        used_gb="50.10",
    )
    world.event(
        account,
        EventSource.USAGE_FUP,
        EventType.THROTTLE_APPLIED,
        now - timedelta(hours=4),
        bucket="PKG-UNLTD",
        speed="256 kbps",
    )
    world.event(
        account,
        EventSource.CATALOGUE,
        EventType.PACK_PURCHASED,
        now - timedelta(days=26),
        amount_lkr=money("1499.00"),
        offering_id="PKG-UNLTD",
        catalogue_version="2027.07",
        fup_cap_gb="50.00",
        fup_disclosed=True,
    )
    return account


def _journey_high_risk_reload(world: SyntheticWorld) -> Account:
    """Priya: LKR 12,000 reload not credited, with a SIM swap 2 days ago (deck S7)."""
    now = world.now
    captured_at = now - timedelta(hours=3)
    account = world.add_account(
        Account(
            msisdn="+94774445555",
            balance_lkr=money("15.00"),
            language=Language.EN,
            sim_swap_at=now - timedelta(days=2),
        )
    )
    world.event(
        account,
        EventSource.PAYMENTS,
        EventType.PAYMENT_CAPTURED,
        captured_at,
        amount_lkr=money("12000.00"),
        payment_ref=world.next_id("pay"),
        bank_ref="BANKREF-99100",
        channel="bank_app",
        status="captured",
    )
    world.event(
        account,
        EventSource.IDENTITY,
        EventType.SIM_SWAP,
        now - timedelta(days=2),
        reason="customer_request",
    )
    return account

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

from clarity.contracts.timeline import EventType, TimelineEvent
from clarity.kernel.common import (
    EventSource,
    Language,
    mask_msisdn,
    money,
    normalise_msisdn,
    subscriber_ref,
)

#: Demo HMAC key. A real deployment keeps this in the KMS (plan §19).
DEMO_SUBSCRIBER_KEY = b"clarity-demo-subscriber-key-not-a-secret"

#: Fixed "now" so the demo is reproducible and screenshots stay stable.
DEMO_NOW = datetime(2027, 9, 14, 18, 0, tzinfo=UTC)

#: Fixed self-care catalogue. Purchase updates the signed-in account only.
CATALOGUE: list[dict[str, Any]] = [
    {
        "offering_id": "PKG-ANY-5",
        "name": "Anytime 5GB",
        "category": "recommended",
        "price_lkr": "499.00",
        "data_gb": "5.00",
        "validity_days": 7,
        "after_cap_speed": "256 kbps",
        "apps": "All apps",
        "recommended": True,
    },
    {
        "offering_id": "PKG-ANY-10",
        "name": "Anytime 10GB",
        "category": "anytime",
        "price_lkr": "799.00",
        "data_gb": "10.00",
        "validity_days": 30,
        "after_cap_speed": "512 kbps",
        "apps": "All apps",
        "recommended": False,
    },
    {
        "offering_id": "PKG-UNL",
        "name": "Unlimited Data",
        "category": "unlimited",
        "price_lkr": "1499.00",
        "data_gb": "50.00",
        "validity_days": 30,
        "after_cap_speed": "256 kbps",
        "apps": "All apps",
        "recommended": False,
    },
    {
        "offering_id": "PKG-SOC",
        "name": "Social 7 Day",
        "category": "social",
        "price_lkr": "299.00",
        "data_gb": "8.00",
        "validity_days": 7,
        "after_cap_speed": "128 kbps",
        "apps": "Facebook, Instagram, WhatsApp, TikTok",
        "recommended": False,
    },
    {
        "offering_id": "PKG-WORK",
        "name": "Work and Learn 15GB",
        "category": "work",
        "price_lkr": "1299.00",
        "data_gb": "15.00",
        "validity_days": 30,
        "after_cap_speed": "1 Mbps",
        "apps": "Zoom, Teams, Google, YouTube",
        "recommended": False,
    },
    {
        "offering_id": "PKG-VOICE",
        "name": "Voice 200",
        "category": "voice",
        "price_lkr": "199.00",
        "data_gb": None,
        "validity_days": 30,
        "after_cap_speed": None,
        "apps": "Any Hutch number",
        "recommended": False,
    },
    {
        "offering_id": "PKG-COMBO",
        "name": "Combo 10GB + 100 min",
        "category": "combo",
        "price_lkr": "899.00",
        "data_gb": "10.00",
        "validity_days": 30,
        "after_cap_speed": "512 kbps",
        "apps": "All apps",
        "recommended": False,
    },
]


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
    name: str = ""
    language: Language = Language.EN
    segment: str = "prepaid"
    subscriptions: list[Subscription] = field(default_factory=list)
    packs: list[Pack] = field(default_factory=list)
    safeguards: dict[str, Any] = field(default_factory=dict)
    blocked_merchants: set[str] = field(default_factory=set)
    family: list[str] = field(default_factory=list)
    notify: str = "important"
    large_text: bool = False
    onboarded: bool = False
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
    """Stand-in for the HUTCH estate.

    Optionally write-through to a SQL store so refunds and deactivations survive
    a process restart. Adapters and rules still see the in-memory Account shape.
    """

    def __init__(self, *, now: datetime = DEMO_NOW, persist: bool = False) -> None:
        self.now = now
        self._accounts: dict[str, Account] = {}
        #: Real phones that act as a synthetic customer (CLARITY_LINKED_PHONES).
        #: In memory only: each process applies the server setting at start.
        self._linked: dict[str, str] = {}
        self._seq = 0
        self._persist = persist
        #: Sources the operator has marked unavailable, to demo degradation.
        self.unavailable: set[EventSource] = set()

    def _flush(self, account: Account | None = None) -> None:
        if not self._persist:
            return
        from clarity.integration.drivers.mock.store import save_account, save_world, session_scope
        from clarity.integration.drivers.mock.store.models import MetaRow

        with session_scope() as session:
            if account is None:
                save_world(session, self)
            else:
                save_account(session, account)
                session.merge(MetaRow(key="seq", value=str(self._seq)))

    # -- construction ------------------------------------------------------ #

    def next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq:06d}"

    def add_account(self, account: Account) -> Account:
        self._accounts[account.ref] = account
        self._flush(account)
        return account

    def account(self, ref: str) -> Account | None:
        return self._accounts.get(ref)

    def account_by_msisdn(self, msisdn: str) -> Account | None:
        normalised = normalise_msisdn(msisdn)
        linked = self._linked.get(normalised)
        if linked is not None:
            return self._accounts.get(linked)
        return self._accounts.get(ref_for(normalised))

    def link_phone(self, phone: str, ref: str) -> None:
        """Let a real phone sign in, chat and message as the customer `ref`.

        Sign-in, the chat and the channel gateway all resolve a number through
        `account_by_msisdn`, so one link covers every channel.
        """
        if ref not in self._accounts:
            raise KeyError(f"no synthetic customer {ref}")
        self._linked[normalise_msisdn(phone)] = ref

    def network_for(self, subscriber_ref: str) -> dict[str, object]:
        """Simulated coverage and outage state for one subscriber (`hutch-sim`).

        The `_network` key is private to the synthetic world: the underscore
        keeps it out of the safeguard list the customer and MCP are shown, so
        adding it here did not change what `get_customer_safeguards` returns.
        A real deployment reads the network assurance system
        (**REQUIRES HUTCH CONFIRMATION**).
        """
        clear: dict[str, object] = {
            "status": "clear",
            "text": "No outage in your area.",
            "eta": None,
            "simulated": True,
        }
        account = self._accounts.get(subscriber_ref)
        if account is None:
            return clear
        network = account.safeguards.get("_network")
        if not isinstance(network, dict):
            return clear
        return {
            "status": network.get("status") or "clear",
            "text": network.get("text") or "No outage in your area.",
            "eta": network.get("eta"),
            "simulated": True,
        }

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
        created = account.add(
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
        self._flush(account)
        return created

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
        if reason.startswith("clarity") or reason == "refund":
            account.refunds_last_30d += 1
            self._flush(account)
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
                self._flush(account)
                return was_active
        return False

    def block_merchant(self, ref: str, merchant_id: str) -> bool:
        account = self._require(ref)
        already = merchant_id in account.blocked_merchants
        account.blocked_merchants.add(merchant_id)
        self._flush(account)
        return not already

    def is_merchant_blocked(self, ref: str, merchant_id: str) -> bool:
        """Backs the recurrence test on the Trust Receipt."""
        return merchant_id in self._require(ref).blocked_merchants

    def set_safeguard(self, ref: str, kind: str, params: dict[str, Any]) -> dict[str, Any]:
        account = self._require(ref)
        before = dict(account.safeguards)
        account.safeguards[kind] = params
        self._flush(account)
        return before

    def reload(self, ref: str, amount: Decimal) -> tuple[Decimal, Decimal]:
        """Credit a reload. Returns (before, after)."""
        account = self._require(ref)
        before = account.balance_lkr
        account.balance_lkr = money(before + amount)
        self.event(
            account,
            EventSource.PAYMENTS,
            EventType.PAYMENT_CAPTURED,
            self.now,
            amount_lkr=amount,
            channel="app",
            status="captured",
            balance_before=str(before),
            balance_after=str(account.balance_lkr),
        )
        self.event(
            account,
            EventSource.CHARGING,
            EventType.BALANCE_CREDITED,
            self.now,
            amount_lkr=amount,
            reason="reload",
            balance_before=str(before),
            balance_after=str(account.balance_lkr),
        )
        self._flush(account)
        return before, account.balance_lkr

    def purchase_pack(self, ref: str, offering_id: str) -> Pack:
        """Buy a catalogue pack, debit the balance, and make it the active pack."""
        offer = next((item for item in CATALOGUE if item["offering_id"] == offering_id), None)
        if offer is None:
            raise KeyError(offering_id)
        account = self._require(ref)
        price = money(offer["price_lkr"])
        if account.balance_lkr < price:
            raise ValueError("balance is not enough for this pack")
        before = account.balance_lkr
        account.balance_lkr = money(before - price)
        for pack in account.packs:
            pack.active = False
        bought = Pack(
            offering_id=offer["offering_id"],
            name=offer["name"],
            price_lkr=price,
            purchased_at=self.now,
            expires_at=self.now + timedelta(days=int(offer["validity_days"])),
            catalogue_version="2027.09",
            fup_cap_gb=money(offer["data_gb"]) if offer["data_gb"] else None,
            after_cap_speed=offer["after_cap_speed"],
            fup_disclosed_at_purchase=True,
        )
        account.packs.append(bought)
        self.event(
            account,
            EventSource.CATALOGUE,
            EventType.PACK_PURCHASED,
            self.now,
            amount_lkr=price,
            offering_id=bought.offering_id,
            product=bought.name,
            balance_before=str(before),
            balance_after=str(account.balance_lkr),
        )
        self._flush(account)
        return bought

    def add_family(self, ref: str, msisdn: str) -> str:
        """Link another Hutch number this customer looks after. At most 10."""
        account = self._require(ref)
        other = self.account_by_msisdn(msisdn)
        if other is None or other.ref == ref:
            raise KeyError(msisdn)
        if other.msisdn in account.family:
            return other.msisdn
        if len(account.family) >= 10:
            raise ValueError("family list is full")
        account.family.append(other.msisdn)
        self._flush(account)
        return other.msisdn

    def _require(self, ref: str) -> Account:
        account = self._accounts.get(ref)
        if account is None:
            raise KeyError(f"unknown subscriber_ref {ref!r}")
        return account


# --------------------------------------------------------------------------- #
# Demo scenarios - one per prototype journey (plan §1.9, §6)
# --------------------------------------------------------------------------- #


def build_demo_world(now: datetime = DEMO_NOW, *, persist: bool = False) -> SyntheticWorld:
    """Build the demo estate: mixed Dilani plus thinner contrast accounts.

    Dilani holds every independent cause a self-care demo needs on one number.
    Nimal, Kavitha and Priya stay thinner for family / contrast. No recent SIM
    swap on Dilani (that would force STAFF_APPROVAL on every money move).
    """
    world = SyntheticWorld(now=now, persist=persist)
    _journey_mixed_dilani(world)
    _journey_nimal_thin(world)
    _journey_kavitha_thin(world)
    _journey_priya_thin(world)
    return world


def _journey_mixed_dilani(world: SyntheticWorld) -> Account:
    """Dilani: one signed-in number with independent history for every question."""
    now = world.now
    charged_at = now.replace(hour=14, minute=6, second=0, microsecond=0)
    otp_at = now - timedelta(days=20)
    account = world.add_account(
        Account(
            msisdn="+94781234567",
            name="Dilani Perera",
            balance_lkr=money("451.00"),
            language=Language.SI,
            onboarded=True,
            notify="important",
            refunds_last_30d=1,
            safeguards={
                "spend_cap": {"value": "500"},
                "data_on_expiry": {"value": "stop"},
                "_network": {
                    "status": "clear",
                    "text": "No outage in your area right now.",
                    "eta": None,
                },
            },
            subscriptions=[
                Subscription(
                    subscription_id="SUB-GAME-1",
                    merchant_id="MER-GAMEHUB",
                    merchant_name="GameHub",
                    product="Daily game subscription",
                    price_lkr=money("49.00"),
                    otp_verified_at=None,
                ),
                Subscription(
                    subscription_id="SUB-NEWS-1",
                    merchant_id="MER-NEWSBYTE",
                    merchant_name="NewsByte",
                    product="Daily headlines",
                    price_lkr=money("19.00"),
                    otp_verified_at=otp_at,
                    second_confirmation_at=otp_at + timedelta(minutes=1),
                ),
            ],
            packs=[
                Pack(
                    offering_id="PKG-ANY-10",
                    name="Anytime 10GB",
                    price_lkr=money("799.00"),
                    purchased_at=now - timedelta(days=12),
                    expires_at=now + timedelta(days=18),
                    catalogue_version="2027.08",
                    fup_cap_gb=money("10.00"),
                    after_cap_speed="512 kbps",
                    fup_disclosed_at_purchase=True,
                    active=True,
                ),
                Pack(
                    offering_id="PKG-DATA-30",
                    name="30-Day Data 10GB",
                    price_lkr=money("999.00"),
                    purchased_at=now - timedelta(days=45),
                    expires_at=now - timedelta(days=15),
                    catalogue_version="2027.07",
                    fup_cap_gb=money("10.00"),
                    after_cap_speed="512 kbps",
                    fup_disclosed_at_purchase=True,
                    active=False,
                ),
            ],
            family=["+94782223333"],
        )
    )

    # Normal reload - captured and credited.
    reload_at = now - timedelta(days=5)
    world.event(
        account,
        EventSource.PAYMENTS,
        EventType.PAYMENT_CAPTURED,
        reload_at,
        amount_lkr=money("500.00"),
        payment_ref=world.next_id("pay"),
        bank_ref="BANKREF-50011",
        channel="app",
        status="captured",
    )
    world.event(
        account,
        EventSource.CHARGING,
        EventType.BALANCE_CREDITED,
        reload_at + timedelta(seconds=30),
        amount_lkr=money("500.00"),
        bank_ref="BANKREF-50011",
        reason="reload",
        balance_before="120.00",
        balance_after="620.00",
    )

    # Duplicate-looking bank captures (same amount twice). Spaced outside the
    # 30-minute DUPLICATE_RELOAD window so Dilani's default top cause stays
    # VAS_NO_CONSENT for the one-tap journey; UI still marks "on this number".
    dup_first = now - timedelta(hours=6)
    dup_second = now - timedelta(hours=5, minutes=20)
    for captured_at in (dup_first, dup_second):
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
        dup_first + timedelta(seconds=40),
        amount_lkr=money("3500.00"),
        bank_ref="BANKREF-77821",
        reason="reload",
        balance_before="620.00",
        balance_after="4120.00",
    )

    # Active Anytime pack purchase + FUP around 85% with usage, then cap hit.
    world.event(
        account,
        EventSource.CATALOGUE,
        EventType.PACK_PURCHASED,
        now - timedelta(days=12),
        amount_lkr=money("799.00"),
        offering_id="PKG-ANY-10",
        product="Anytime 10GB",
        catalogue_version="2027.08",
        fup_cap_gb="10.00",
        fup_disclosed=True,
        balance_before="4120.00",
        balance_after="3321.00",
    )
    world.event(
        account,
        EventSource.USAGE_FUP,
        EventType.DATA_SESSION,
        charged_at - timedelta(hours=2),
        bucket="PKG-ANY-10",
        remaining_gb="1.5",
        used_gb="8.5",
    )

    # Previous pack expired + later PAYG draw. Spaced beyond PACK_EXPIRY_BURN's
    # P7D window so it does not compete with VAS on the conflict margin; the
    # trail still shows on Activity.
    world.event(
        account,
        EventSource.CATALOGUE,
        EventType.PACK_EXPIRED,
        now - timedelta(days=20),
        offering_id="PKG-DATA-30",
        product="30-Day Data 10GB",
    )
    world.event(
        account,
        EventSource.CHARGING,
        EventType.CHARGE_APPLIED,
        now - timedelta(days=10),
        amount_lkr=money("48.00"),
        reason="payg_data",
        balance_before="500.00",
        balance_after="452.00",
    )

    # Failed pack activation (catalogue / charging).
    world.event(
        account,
        EventSource.CATALOGUE,
        EventType.PACK_ACTIVATED,
        now - timedelta(days=8),
        offering_id="PKG-SOC",
        product="Social 7 Day",
        status="failed",
        reason="catalogue_timeout",
    )

    # GameHub VAS with no OTP - live cause for ONE_TAP_CONFIRM.
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
        balance_before="500.00",
        balance_after="451.00",
    )

    # Second VAS with valid consent - explain-only if asked.
    world.event(
        account,
        EventSource.VAS_CONSENT,
        EventType.CONSENT_OTP_VERIFIED,
        otp_at,
        subscription_id="SUB-NEWS-1",
        merchant_id="MER-NEWSBYTE",
    )
    world.event(
        account,
        EventSource.VAS_CONSENT,
        EventType.SECOND_CONFIRMATION,
        otp_at + timedelta(minutes=1),
        subscription_id="SUB-NEWS-1",
        merchant_id="MER-NEWSBYTE",
    )
    world.event(
        account,
        EventSource.CHARGING,
        EventType.VAS_CHARGE,
        now - timedelta(days=2),
        amount_lkr=money("19.00"),
        subscription_id="SUB-NEWS-1",
        merchant_id="MER-NEWSBYTE",
        merchant_name="NewsByte",
        product="Daily headlines",
        balance_before="470.00",
        balance_after="451.00",
    )

    # Completed refund already in history (separate from live GameHub).
    world.event(
        account,
        EventSource.CHARGING,
        EventType.BALANCE_CREDITED,
        now - timedelta(days=10),
        amount_lkr=money("99.00"),
        reason="clarity_refund",
        balance_before="352.00",
        balance_after="451.00",
        note="prior VAS refund",
    )

    # Open support case trail + watch-list complaint for GameHub.
    world.event(
        account,
        EventSource.CRM,
        EventType.TICKET_CREATED,
        now - timedelta(days=3),
        ticket_id="TCK-DILANI-1",
        subject="Slow data after evening outage",
        status="open",
        channel="app",
    )
    world.event(
        account,
        EventSource.CRM,
        EventType.COMPLAINT_RECEIVED,
        now - timedelta(days=1),
        merchant_id="MER-GAMEHUB",
        channel="app",
        text="GameHub charged without OTP",
    )
    return account


def _journey_nimal_thin(world: SyntheticWorld) -> Account:
    """Nimal: thinner family / contrast account (duplicate reload only)."""
    now = world.now
    first = now - timedelta(minutes=14)
    second = now - timedelta(minutes=11)
    account = world.add_account(
        Account(
            msisdn="+94782223333",
            name="Nimal Fernando",
            balance_lkr=money("3500.00"),
            language=Language.EN,
            onboarded=True,
        )
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


def _journey_kavitha_thin(world: SyntheticWorld) -> Account:
    """Kavitha: thinner FUP explain-only contrast account."""
    now = world.now
    account = world.add_account(
        Account(
            msisdn="+94783334444",
            name="Kavitha Selvan",
            balance_lkr=money("120.00"),
            language=Language.TA,
            onboarded=True,
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


def _journey_priya_thin(world: SyntheticWorld) -> Account:
    """Priya: thinner high-risk reload contrast (SIM swap - not the mixed demo)."""
    now = world.now
    captured_at = now - timedelta(hours=3)
    account = world.add_account(
        Account(
            msisdn="+94784445555",
            name="Priya Jayawardena",
            balance_lkr=money("15.00"),
            language=Language.EN,
            onboarded=True,
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

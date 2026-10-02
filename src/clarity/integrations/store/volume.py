"""Generate thinner customers and historical complaints for Desk / Autopsy."""

from __future__ import annotations

import random
from datetime import timedelta
from typing import Any

from clarity.integrations.mocks.world import (
    DEMO_NOW,
    Account,
    Pack,
    Subscription,
    SyntheticWorld,
)
from clarity.schemas.common import EventSource, Language, money
from clarity.schemas.timeline import EventType

COMPLAINT_TEMPLATES: dict[str, list[str]] = {
    "unexpected_balance_deduction": [
        "My balance dropped by LKR {amount} without a pack I recognise",
        "balaance gone {amount} rupees suddenly, pls check",
        "මගේ ශේෂය {amount}කින් අඩු වුණා හේතුවක් නැතුව",
        "என் இருப்பு {amount} குறைந்தது காரணம் தெரியவில்லை",
    ],
    "slow_data": [
        "Unlimited pack is very slow after fair use",
        "data manthara slow after {amount}GB, FUP?",
        "දත්ත මන්දගාමීයි pack එකෙන් පස්සේ",
        "தரவு மெதுவாக உள்ளது கேப் பிறகு",
    ],
    "duplicate_reload": [
        "Bank took LKR {amount} twice but Hutch credited once",
        "reload {amount} captured two times same bank ref",
        "බැංකුව {amount} දෙවරක් කපාගත්තා credit එකයි",
        "வங்கி {amount} இருமுறை எடுத்தது ஒரு credit மட்டும்",
    ],
    "vas_unknown_charge": [
        "Game subscription LKR {amount} charged with no OTP",
        "daily VAS {amount} I never confirmed",
        "ගේම් ගාස්තු {amount} OTP නැතුව",
        "விளையாட்டு கட்டணம் {amount} OTP இல்லாமல்",
    ],
    "fup_reached": [
        "App says days left but unlimited stopped at the cap",
        "FUP hit on {amount}GB pack, speed dropped",
        "FUP සීමාවට උඩින් වේගය අඩුයි",
        "FUP வரம்புக்குப் பிறகு வேகம் குறைவு",
    ],
    "network_outage": [
        "No signal in my area since evening",
        "network down Colombo South, any ETA?",
        "ජාලය නැහැ මගේ ප්‍රදේශයේ",
        "நெட்வொர்க் இல்லை என் பகுதியில்",
    ],
    "esim_problem": [
        "eSIM QR failed after convert from physical SIM",
        "cannot activate eSIM on this phone",
        "eSIM activate වෙන්නේ නැහැ",
        "eSIM செயல்படவில்லை",
    ],
}

_CHANNELS = ("whatsapp", "app", "ussd", "call_centre", "facebook")
_LANGS = ("en", "en", "si", "ta")  # slight English bias
_CAUSES = (
    "vas_no_consent",
    "duplicate_reload",
    "fup",
    "pack_burn",
    "reload_missing",
    "network",
)


def generate_complaints(count: int = 2000, *, seed: int = 42) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    now = DEMO_NOW
    out: list[dict[str, Any]] = []
    keys = list(COMPLAINT_TEMPLATES)
    for index in range(1, count + 1):
        key = keys[index % len(keys)]
        template = rng.choice(COMPLAINT_TEMPLATES[key])
        amount = rng.choice([49, 99, 199, 500, 999, 1499, 3500])
        text = template.format(amount=amount)
        lang = _LANGS[index % len(_LANGS)]
        out.append(
            {
                "complaint_id": f"HC-{index:05d}",
                "text": text,
                "channel": rng.choice(_CHANNELS),
                "language": lang,
                "template_key": key,
                "received_at": now - timedelta(hours=rng.randint(1, 24 * 90)),
            }
        )
    return out


def generate_volume_customers(
    world: SyntheticWorld, count: int = 40, *, seed: int = 7
) -> list[Account]:
    """Add thinner customers each carrying one primary cause."""
    rng = random.Random(seed)
    created: list[Account] = []
    for index in range(1, count + 1):
        cause = _CAUSES[index % len(_CAUSES)]
        # Avoid colliding with Dilani / Nimal / Kavitha / Priya (771-744).
        msisdn = f"+94775{index:06d}"[:12]
        if len(msisdn) < 12:
            msisdn = f"+94775{index:06d}"
        name = f"Customer {index:02d}"
        lang = Language(rng.choice(["en", "si", "ta"]))
        account = _thin_for_cause(world, msisdn, name, lang, cause, rng)
        created.append(account)
    return created


def _thin_for_cause(
    world: SyntheticWorld,
    msisdn: str,
    name: str,
    language: Language,
    cause: str,
    rng: random.Random,
) -> Account:
    now = world.now
    if cause == "vas_no_consent":
        sub_id = world.next_id("SUB")
        account = world.add_account(
            Account(
                msisdn=msisdn,
                name=name,
                balance_lkr=money(str(rng.randint(50, 400))),
                language=language,
                onboarded=True,
                subscriptions=[
                    Subscription(
                        subscription_id=sub_id,
                        merchant_id="MER-GAMEZONE",
                        merchant_name="GameZone",
                        product="Daily play pass",
                        price_lkr=money("49.00"),
                    )
                ],
            )
        )
        world.event(
            account,
            EventSource.CHARGING,
            EventType.VAS_CHARGE,
            now - timedelta(hours=rng.randint(1, 48)),
            amount_lkr=money("49.00"),
            subscription_id=sub_id,
            merchant_id="MER-GAMEZONE",
            merchant_name="GameZone",
            product="Daily play pass",
        )
        return account
    if cause == "duplicate_reload":
        account = world.add_account(
            Account(
                msisdn=msisdn,
                name=name,
                balance_lkr=money("3500.00"),
                language=language,
                onboarded=True,
            )
        )
        bank = f"BANKREF-V{rng.randint(10000, 99999)}"
        first = now - timedelta(minutes=20)
        for captured_at in (first, first + timedelta(minutes=3)):
            world.event(
                account,
                EventSource.PAYMENTS,
                EventType.PAYMENT_CAPTURED,
                captured_at,
                amount_lkr=money("3500.00"),
                payment_ref=world.next_id("pay"),
                bank_ref=bank,
                channel="bank_app",
                status="captured",
            )
        world.event(
            account,
            EventSource.CHARGING,
            EventType.BALANCE_CREDITED,
            first + timedelta(seconds=30),
            amount_lkr=money("3500.00"),
            bank_ref=bank,
            reason="reload",
        )
        return account
    if cause == "fup":
        account = world.add_account(
            Account(
                msisdn=msisdn,
                name=name,
                balance_lkr=money("80.00"),
                language=language,
                onboarded=True,
                packs=[
                    Pack(
                        offering_id="PKG-UNLTD",
                        name="Unlimited Data",
                        price_lkr=money("1499.00"),
                        purchased_at=now - timedelta(days=20),
                        expires_at=now + timedelta(days=10),
                        catalogue_version="2027.07",
                        fup_cap_gb=money("50.00"),
                        after_cap_speed="256 kbps",
                    )
                ],
            )
        )
        world.event(
            account,
            EventSource.CATALOGUE,
            EventType.PACK_PURCHASED,
            now - timedelta(days=20),
            amount_lkr=money("1499.00"),
            offering_id="PKG-UNLTD",
            fup_disclosed=True,
            fup_cap_gb="50.00",
        )
        world.event(
            account,
            EventSource.USAGE_FUP,
            EventType.FUP_CAP_REACHED,
            now - timedelta(hours=2),
            bucket="PKG-UNLTD",
            cap_gb="50.00",
            used_gb="50.20",
        )
        return account
    if cause == "pack_burn":
        account = world.add_account(
            Account(
                msisdn=msisdn,
                name=name,
                balance_lkr=money("40.00"),
                language=language,
                onboarded=True,
            )
        )
        world.event(
            account,
            EventSource.CATALOGUE,
            EventType.PACK_EXPIRED,
            now - timedelta(days=3),
            offering_id="PKG-ANY-5",
        )
        world.event(
            account,
            EventSource.CHARGING,
            EventType.CHARGE_APPLIED,
            now - timedelta(days=2),
            amount_lkr=money("120.00"),
            reason="payg_data",
        )
        return account
    if cause == "reload_missing":
        account = world.add_account(
            Account(
                msisdn=msisdn,
                name=name,
                balance_lkr=money("10.00"),
                language=language,
                onboarded=True,
            )
        )
        world.event(
            account,
            EventSource.PAYMENTS,
            EventType.PAYMENT_CAPTURED,
            now - timedelta(hours=5),
            amount_lkr=money("1000.00"),
            payment_ref=world.next_id("pay"),
            bank_ref=f"BANKREF-M{rng.randint(1000, 9999)}",
            channel="bank_app",
            status="captured",
        )
        return account
    # network
    account = world.add_account(
        Account(
            msisdn=msisdn,
            name=name,
            balance_lkr=money("200.00"),
            language=language,
            onboarded=True,
            safeguards={
                "_network": {
                    "status": "outage",
                    "text": "Local radio issue reported.",
                    "eta": "2 hours",
                }
            },
        )
    )
    return account

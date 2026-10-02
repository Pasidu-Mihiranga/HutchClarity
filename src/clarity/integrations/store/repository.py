"""Load and save SyntheticWorld from SQL tables."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from clarity.integrations.mocks.world import (
    DEMO_NOW,
    Account,
    Pack,
    Subscription,
    SyntheticWorld,
    ref_for,
)
from clarity.integrations.store.models import (
    AccountRow,
    ConsentRow,
    CustomerRow,
    EventRow,
    FamilyLinkRow,
    HistoricalComplaintRow,
    KnowledgeArticleRow,
    MetaRow,
    NetworkEventRow,
    PackageRow,
    SubscriptionRow,
    TrustReceiptRow,
)
from clarity.schemas.common import EventSource, Language, ensure_utc, money
from clarity.schemas.timeline import EventType, TimelineEvent


def _dec(value: Any) -> Decimal:
    return money(str(value))


def _dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        # SQLite drops tzinfo on round-trip; treat stored values as UTC.
        from datetime import UTC

        return value.replace(tzinfo=UTC)
    return ensure_utc(value)


def world_is_seeded(session: Session) -> bool:
    count = session.scalar(select(func.count()).select_from(CustomerRow))
    return bool(count)


def save_world(session: Session, world: SyntheticWorld) -> None:
    """Replace all customer rows with the current in-memory world."""
    session.execute(delete(EventRow))
    session.execute(delete(ConsentRow))
    session.execute(delete(NetworkEventRow))
    session.execute(delete(FamilyLinkRow))
    session.execute(delete(PackageRow))
    session.execute(delete(SubscriptionRow))
    session.execute(delete(AccountRow))
    session.execute(delete(CustomerRow))
    for account in world.accounts():
        save_account(session, account)
    session.merge(MetaRow(key="seq", value=str(world._seq)))
    session.merge(MetaRow(key="seeded_at", value=world.now.isoformat()))


def save_account(session: Session, account: Account) -> None:
    """Upsert one account and its related rows."""
    customer_id = account.ref
    session.merge(
        CustomerRow(
            id=customer_id,
            msisdn=account.msisdn,
            name=account.name,
            language=account.language.value,
            segment=account.segment,
            status="active",
        )
    )
    session.merge(
        AccountRow(
            customer_id=customer_id,
            balance_lkr=account.balance_lkr,
            notify=account.notify,
            large_text=account.large_text,
            onboarded=account.onboarded,
            sim_swap_at=account.sim_swap_at,
            fraud_flag=account.fraud_flag,
            refunds_last_30d=account.refunds_last_30d,
            safeguards=dict(account.safeguards),
            blocked_merchants=sorted(account.blocked_merchants),
        )
    )
    session.execute(delete(PackageRow).where(PackageRow.customer_id == customer_id))
    for pack in account.packs:
        session.add(
            PackageRow(
                customer_id=customer_id,
                offering_id=pack.offering_id,
                name=pack.name,
                price_lkr=pack.price_lkr,
                purchased_at=pack.purchased_at,
                expires_at=pack.expires_at,
                catalogue_version=pack.catalogue_version,
                fup_cap_gb=pack.fup_cap_gb,
                after_cap_speed=pack.after_cap_speed,
                fup_disclosed_at_purchase=pack.fup_disclosed_at_purchase,
                active=pack.active,
            )
        )
    session.execute(delete(SubscriptionRow).where(SubscriptionRow.customer_id == customer_id))
    session.execute(delete(ConsentRow).where(ConsentRow.customer_id == customer_id))
    for sub in account.subscriptions:
        session.add(
            SubscriptionRow(
                subscription_id=sub.subscription_id,
                customer_id=customer_id,
                merchant_id=sub.merchant_id,
                merchant_name=sub.merchant_name,
                product=sub.product,
                price_lkr=sub.price_lkr,
                active=sub.active,
                otp_verified_at=sub.otp_verified_at,
                second_confirmation_at=sub.second_confirmation_at,
            )
        )
        kind = "otp" if sub.otp_verified_at else "absent"
        session.add(
            ConsentRow(
                customer_id=customer_id,
                subscription_id=sub.subscription_id,
                kind=kind,
                verified_at=sub.otp_verified_at,
                note=None if sub.otp_verified_at else "no valid OTP consent found",
            )
        )
    session.execute(delete(EventRow).where(EventRow.customer_id == customer_id))
    for source, events in account.records.items():
        for event in events:
            session.add(
                EventRow(
                    event_id=event.event_id,
                    customer_id=customer_id,
                    source=source.value,
                    event_type=event.event_type.value,
                    source_event_id=event.source_event_id,
                    occurred_at=event.occurred_at,
                    amount_lkr=event.amount_lkr,
                    attributes=dict(event.attributes),
                    adapter_version=event.adapter_version,
                )
            )
    session.execute(delete(FamilyLinkRow).where(FamilyLinkRow.customer_id == customer_id))
    for msisdn in account.family:
        session.add(FamilyLinkRow(customer_id=customer_id, linked_msisdn=msisdn))


def load_world(session: Session, *, now: datetime = DEMO_NOW) -> SyntheticWorld:
    world = SyntheticWorld(now=now, persist=False)
    seq = session.get(MetaRow, "seq")
    if seq is not None:
        world._seq = int(seq.value)
    customers = session.scalars(select(CustomerRow)).all()
    for row in customers:
        account_row = row.account
        if account_row is None:
            continue
        account = Account(
            msisdn=row.msisdn,
            name=row.name,
            balance_lkr=_dec(account_row.balance_lkr),
            language=Language(row.language),
            segment=row.segment,
            notify=account_row.notify,
            large_text=account_row.large_text,
            onboarded=account_row.onboarded,
            sim_swap_at=_dt(account_row.sim_swap_at),
            fraud_flag=account_row.fraud_flag,
            refunds_last_30d=account_row.refunds_last_30d,
            safeguards=dict(account_row.safeguards or {}),
            blocked_merchants=set(account_row.blocked_merchants or []),
            family=[link.linked_msisdn for link in row.family_links],
            subscriptions=[
                Subscription(
                    subscription_id=sub.subscription_id,
                    merchant_id=sub.merchant_id,
                    merchant_name=sub.merchant_name,
                    product=sub.product,
                    price_lkr=_dec(sub.price_lkr),
                    active=sub.active,
                    otp_verified_at=_dt(sub.otp_verified_at),
                    second_confirmation_at=_dt(sub.second_confirmation_at),
                )
                for sub in row.subscriptions
            ],
            packs=[
                Pack(
                    offering_id=pack.offering_id,
                    name=pack.name,
                    price_lkr=_dec(pack.price_lkr),
                    purchased_at=_dt(pack.purchased_at) or DEMO_NOW,
                    expires_at=_dt(pack.expires_at) or DEMO_NOW,
                    catalogue_version=pack.catalogue_version,
                    fup_cap_gb=_dec(pack.fup_cap_gb) if pack.fup_cap_gb is not None else None,
                    after_cap_speed=pack.after_cap_speed,
                    fup_disclosed_at_purchase=pack.fup_disclosed_at_purchase,
                    active=pack.active,
                )
                for pack in row.packages
            ],
        )
        for event in row.events:
            occurred = _dt(event.occurred_at)
            if occurred is None:
                continue
            account.add(
                TimelineEvent(
                    event_id=event.event_id,
                    source=EventSource(event.source),
                    event_type=EventType(event.event_type),
                    source_event_id=event.source_event_id,
                    occurred_at=occurred,
                    amount_lkr=_dec(event.amount_lkr) if event.amount_lkr is not None else None,
                    attributes=dict(event.attributes or {}),
                    adapter_version=event.adapter_version,
                )
            )
        latest_net = max(row.network_events, key=lambda n: n.occurred_at, default=None)
        if latest_net is not None:
            account.safeguards["_network"] = {
                "status": latest_net.status,
                "text": latest_net.text,
                "eta": latest_net.eta,
            }
        world._accounts[account.ref] = account
    return world


def save_network(
    session: Session,
    customer_id: str,
    *,
    status: str,
    text: str,
    eta: str | None,
    occurred_at: datetime,
) -> None:
    session.add(
        NetworkEventRow(
            customer_id=customer_id,
            status=status,
            text=text,
            eta=eta,
            occurred_at=occurred_at,
        )
    )


def network_for(session: Session, customer_id: str) -> dict[str, str | None]:
    rows = session.scalars(
        select(NetworkEventRow)
        .where(NetworkEventRow.customer_id == customer_id)
        .order_by(NetworkEventRow.occurred_at.desc())
    ).all()
    if not rows:
        return {"status": "clear", "text": "No outage in your area.", "eta": None}
    top = rows[0]
    return {"status": top.status, "text": top.text, "eta": top.eta}


def upsert_knowledge(session: Session, articles: list[dict[str, Any]]) -> None:
    for article in articles:
        session.merge(
            KnowledgeArticleRow(
                article_id=article["article_id"],
                title=article["title"],
                body=article["body"],
                keywords=list(article.get("keywords") or []),
                language=article.get("language", "en"),
            )
        )


def search_knowledge(session: Session, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    q = query.lower()
    rows = session.scalars(select(KnowledgeArticleRow)).all()
    scored: list[tuple[int, KnowledgeArticleRow]] = []
    for row in rows:
        score = 0
        hay = f"{row.title} {row.body} {' '.join(row.keywords)}".lower()
        for token in q.replace("?", " ").split():
            if len(token) < 2:
                continue
            if token in hay:
                score += 2
            if token in [k.lower() for k in row.keywords]:
                score += 3
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "article_id": row.article_id,
            "title": row.title,
            "body": row.body,
            "keywords": list(row.keywords),
            "language": row.language,
        }
        for _, row in scored[:limit]
    ]


def save_complaints(session: Session, complaints: list[dict[str, Any]]) -> None:
    session.execute(delete(HistoricalComplaintRow))
    for item in complaints:
        session.add(
            HistoricalComplaintRow(
                complaint_id=item["complaint_id"],
                text=item["text"],
                channel=item.get("channel", "whatsapp"),
                language=item.get("language", "en"),
                template_key=item["template_key"],
                received_at=item["received_at"],
            )
        )


def list_complaints(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(select(HistoricalComplaintRow)).all()
    return [
        {
            "complaint_id": row.complaint_id,
            "text": row.text,
            "channel": row.channel,
            "language": row.language,
            "template_key": row.template_key,
            "received_at": row.received_at,
        }
        for row in rows
    ]


def customer_id_for_msisdn(msisdn: str) -> str:
    return ref_for(msisdn)


def save_receipt(session: Session, receipt: Any, *, subscriber_ref: str) -> None:
    """Persist a Trust Receipt document as JSON."""
    session.merge(
        TrustReceiptRow(
            receipt_id=receipt.receipt_id,
            case_id=receipt.case_id,
            subscriber_ref=subscriber_ref,
            payload_json=receipt.payload.model_dump(mode="json"),
            payload_hash=receipt.payload_hash,
            signature_json=receipt.signature.model_dump(mode="json"),
            issued_at=receipt.payload.issued_at,
        )
    )


def list_receipts(session: Session) -> list[tuple[Any, str]]:
    """Load Trust Receipts oldest-first as (receipt, subscriber_ref)."""
    from clarity.schemas.receipt import ReceiptPayload, ReceiptSignature, TrustReceipt

    rows = session.scalars(select(TrustReceiptRow).order_by(TrustReceiptRow.issued_at.asc())).all()
    out: list[tuple[Any, str]] = []
    for row in rows:
        receipt = TrustReceipt(
            payload=ReceiptPayload.model_validate(row.payload_json),
            payload_hash=row.payload_hash,
            signature=ReceiptSignature.model_validate(row.signature_json),
            verify_url=f"http://localhost:8000/v/{row.receipt_id}",
        )
        out.append((receipt, row.subscriber_ref))
    return out


def events_for_customer(
    session: Session, customer_id: str, *, source: str | None = None
) -> list[dict[str, Any]]:
    query = select(EventRow).where(EventRow.customer_id == customer_id)
    if source is not None:
        query = query.where(EventRow.source == source)
    rows = session.scalars(query.order_by(EventRow.occurred_at.desc())).all()
    return [
        {
            "event_id": row.event_id,
            "source": row.source,
            "event_type": row.event_type,
            "source_event_id": row.source_event_id,
            "occurred_at": row.occurred_at.isoformat(),
            "amount_lkr": str(row.amount_lkr) if row.amount_lkr is not None else None,
            "attributes": dict(row.attributes or {}),
        }
        for row in rows
    ]


def subscriptions_for_customer(session: Session, customer_id: str) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(SubscriptionRow).where(SubscriptionRow.customer_id == customer_id)
    ).all()
    return [
        {
            "subscription_id": row.subscription_id,
            "merchant_id": row.merchant_id,
            "merchant_name": row.merchant_name,
            "product": row.product,
            "price_lkr": str(row.price_lkr),
            "active": row.active,
            "otp_verified_at": row.otp_verified_at.isoformat() if row.otp_verified_at else None,
        }
        for row in rows
    ]


def consent_for_customer(session: Session, customer_id: str) -> list[dict[str, Any]]:
    rows = session.scalars(select(ConsentRow).where(ConsentRow.customer_id == customer_id)).all()
    return [
        {
            "subscription_id": row.subscription_id,
            "kind": row.kind,
            "verified_at": row.verified_at.isoformat() if row.verified_at else None,
            "note": row.note,
        }
        for row in rows
    ]


def account_for_customer(session: Session, customer_id: str) -> dict[str, Any] | None:
    row = session.get(AccountRow, customer_id)
    if row is None:
        return None
    return {
        "customer_id": customer_id,
        "balance_lkr": str(row.balance_lkr),
        "notify": row.notify,
        "onboarded": row.onboarded,
        "safeguards": dict(row.safeguards or {}),
        "blocked_merchants": list(row.blocked_merchants or []),
    }


def packages_catalogue(session: Session) -> list[dict[str, Any]]:
    """Distinct packages seen in the estate (mock catalogue surface)."""
    from clarity.integrations.mocks.world import CATALOGUE

    return list(CATALOGUE)

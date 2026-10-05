"""SQLAlchemy models for the synthetic HUTCH estate.

Related tables, not one fat customer row. Mock adapters and the Timeline
Builder still speak TimelineEvent; this is only the durable store.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class CustomerRow(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    msisdn: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    language: Mapped[str] = mapped_column(String(8), default="en")
    segment: Mapped[str] = mapped_column(String(32), default="prepaid")
    status: Mapped[str] = mapped_column(String(16), default="active")

    account: Mapped[AccountRow | None] = relationship(back_populates="customer", uselist=False)
    packages: Mapped[list[PackageRow]] = relationship(back_populates="customer")
    subscriptions: Mapped[list[SubscriptionRow]] = relationship(back_populates="customer")
    events: Mapped[list[EventRow]] = relationship(back_populates="customer")
    consent_records: Mapped[list[ConsentRow]] = relationship(back_populates="customer")
    network_events: Mapped[list[NetworkEventRow]] = relationship(back_populates="customer")
    family_links: Mapped[list[FamilyLinkRow]] = relationship(
        back_populates="customer",
        foreign_keys="FamilyLinkRow.customer_id",
    )


class AccountRow(Base):
    __tablename__ = "accounts"

    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), primary_key=True)
    balance_lkr: Mapped[Any] = mapped_column(Numeric(12, 2), default=0)
    notify: Mapped[str] = mapped_column(String(16), default="important")
    large_text: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    sim_swap_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fraud_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    refunds_last_30d: Mapped[int] = mapped_column(Integer, default=0)
    active_profile_msisdn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    safeguards: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    blocked_merchants: Mapped[list[str]] = mapped_column(JSON, default=list)

    customer: Mapped[CustomerRow] = relationship(back_populates="account")


class PackageRow(Base):
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    offering_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120))
    price_lkr: Mapped[Any] = mapped_column(Numeric(12, 2))
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    catalogue_version: Mapped[str] = mapped_column(String(32), default="2027.09")
    fup_cap_gb: Mapped[Any | None] = mapped_column(Numeric(12, 2), nullable=True)
    after_cap_speed: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fup_disclosed_at_purchase: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    customer: Mapped[CustomerRow] = relationship(back_populates="packages")


class SubscriptionRow(Base):
    __tablename__ = "subscriptions"

    subscription_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    merchant_id: Mapped[str] = mapped_column(String(64))
    merchant_name: Mapped[str] = mapped_column(String(120))
    product: Mapped[str] = mapped_column(String(120))
    price_lkr: Mapped[Any] = mapped_column(Numeric(12, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    otp_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    second_confirmation_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    customer: Mapped[CustomerRow] = relationship(back_populates="subscriptions")


class ConsentRow(Base):
    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    subscription_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32))  # otp | second_confirm | absent
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    customer: Mapped[CustomerRow] = relationship(back_populates="consent_records")


class EventRow(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    source_event_id: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    amount_lkr: Mapped[Any | None] = mapped_column(Numeric(12, 2), nullable=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    adapter_version: Mapped[str] = mapped_column(String(32), default="mock-0.1.0")

    customer: Mapped[CustomerRow] = relationship(back_populates="events")


class NetworkEventRow(Base):
    __tablename__ = "network_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    status: Mapped[str] = mapped_column(String(32))  # clear | outage
    text: Mapped[str] = mapped_column(String(255))
    eta: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    customer: Mapped[CustomerRow] = relationship(back_populates="network_events")


class FamilyLinkRow(Base):
    __tablename__ = "family_links"
    __table_args__ = (UniqueConstraint("customer_id", "linked_msisdn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    linked_msisdn: Mapped[str] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(16), default="elder")

    customer: Mapped[CustomerRow] = relationship(
        back_populates="family_links", foreign_keys=[customer_id]
    )


class KnowledgeArticleRow(Base):
    __tablename__ = "knowledge_articles"

    article_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(8), default="en")


class HistoricalComplaintRow(Base):
    __tablename__ = "historical_complaints"

    complaint_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(32), default="whatsapp")
    language: Mapped[str] = mapped_column(String(8), default="en")
    template_key: Mapped[str] = mapped_column(String(64), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TrustReceiptRow(Base):
    __tablename__ = "trust_receipts"

    receipt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    subscriber_ref: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(128))
    signature_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MetaRow(Base):
    __tablename__ = "store_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))

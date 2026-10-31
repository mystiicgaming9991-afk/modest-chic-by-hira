"""Customer persistence — guest profiles, addresses, and consent records.

All entities inherit :class:`BaseModel` for standard audit columns.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from modest_chic_backend.db.base import BaseModel


class Customer(BaseModel):
    """A guest buyer identity resolved by normalized phone during checkout.

    No password or sign-in is associated with this record — that belongs
    to feature 024 (customer email OTP login).  ``merged_into_id`` is set
    when staff explicitly merge duplicate profiles; automated cross-person
    merging is outside V1 scope.
    """

    __tablename__ = "customers"
    __table_args__ = (
        Index("idx_cust_phone", "normalized_phone"),
        Index("idx_cust_email", "email", postgresql_where=text("email IS NOT NULL")),
        Index("idx_cust_merged", "merged_into_id"),
    )

    normalized_phone: Mapped[str | None] = mapped_column(String(30))
    display_phone: Mapped[str | None] = mapped_column(String(30))
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id")
    )


class CustomerAddress(BaseModel):
    """A reusable address record.  Order snapshots are immutable and stored
    separately — this table holds the "current" address for future orders.
    """

    __tablename__ = "customer_addresses"
    __table_args__ = (Index("idx_addr_customer", "customer_id"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    recipient_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    line1: Mapped[str] = mapped_column(String(500), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(500))
    area: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(20))
    delivery_notes: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str] = mapped_column(
        CHAR(2), nullable=False, default="PK", server_default="PK"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )


class CustomerContactConsent(BaseModel):
    """A versioned, purpose-and-channel consent decision.

    Consent withdrawal is recorded as a new row with ``consented = FALSE``
    rather than updating the old row — this preserves a complete audit trail.
    """

    __tablename__ = "customer_contact_consents"
    __table_args__ = (
        Index("idx_consent_customer", "customer_id"),
        Index("idx_consent_channel_purpose", "customer_id", "channel", "purpose"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    purpose: Mapped[str] = mapped_column(String(100), nullable=False)
    consented: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))
    policy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("policy_versions.id")
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CustomerOtpChallenge(BaseModel):
    """One-time code challenge for customer email OTP login (Spec 024)."""

    __tablename__ = "customer_otp_challenges"
    __table_args__ = (
        Index("uq_otp_token", "token_hash", unique=True),
        Index("idx_otp_email", "email"),
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


class CustomerAccount(BaseModel):
    """Verified email ownership, deliberately separate from unverified guest contact data."""

    __tablename__ = "customer_accounts"
    __table_args__ = (
        Index("uq_customer_account_email", "email", unique=True),
        Index("uq_customer_account_customer", "customer_id", unique=True),
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CustomerSession(BaseModel):
    """Session for a customer authenticated via email OTP (Spec 024)."""

    __tablename__ = "customer_sessions"
    __table_args__ = (
        Index("uq_cust_session_token", "token_hash", unique=True),
        Index("idx_cust_session_customer", "customer_id"),
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = [
    "Customer",
    "CustomerAddress",
    "CustomerContactConsent",
    "CustomerOtpChallenge",
    "CustomerAccount",
    "CustomerSession",
]

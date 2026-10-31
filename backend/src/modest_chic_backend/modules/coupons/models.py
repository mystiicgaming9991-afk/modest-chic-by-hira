"""Coupon persistence — codes, scopes, redemptions."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from modest_chic_backend.db.base import BaseModel
from modest_chic_backend.modules.coupons.enums import (
    CouponRedemptionStatus,
    CouponState,
    CouponType,
)


class Coupon(BaseModel):
    __tablename__ = "coupons"
    __table_args__ = (
        Index("uq_coupon_code", "code", unique=True),
        CheckConstraint("type <> 'PERCENT' OR value_minor <= 100", name="chk_coupon_percent"),
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[CouponType] = mapped_column(
        Enum(CouponType, name="coupon_type", native_enum=True), nullable=False
    )
    value_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, default="PKR", server_default="PKR"
    )
    min_order_minor: Mapped[int | None] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    max_discount_minor: Mapped[int | None] = mapped_column(Integer)
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    per_customer_limit: Mapped[int | None] = mapped_column(
        Integer, default=1, server_default=text("1")
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    state: Mapped[CouponState] = mapped_column(
        Enum(CouponState, name="coupon_state", native_enum=True),
        nullable=False,
        default=CouponState.ACTIVE,
        server_default=CouponState.ACTIVE.value,
    )


class CouponScope(BaseModel):
    __tablename__ = "coupon_scopes"
    __table_args__ = (Index("uq_coupon_scope", "coupon_id", "scope_type", "scope_id", unique=True),)

    coupon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class CouponRedemption(BaseModel):
    __tablename__ = "coupon_redemptions"
    __table_args__ = (
        Index("uq_coupon_redemption_key", "idempotency_key", unique=True),
        Index("idx_red_coupon", "coupon_id"),
    )

    coupon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("coupons.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id")
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    status: Mapped[CouponRedemptionStatus] = mapped_column(
        Enum(CouponRedemptionStatus, name="coupon_redemption_status", native_enum=True),
        nullable=False,
        default=CouponRedemptionStatus.RESERVED,
        server_default=CouponRedemptionStatus.RESERVED.value,
    )
    discount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = ["Coupon", "CouponRedemption", "CouponScope"]

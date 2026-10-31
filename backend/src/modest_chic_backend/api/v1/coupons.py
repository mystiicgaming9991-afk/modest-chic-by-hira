"""Coupon administration routes."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, model_validator

from modest_chic_backend.api.v1.dependencies import require_permission
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.auth.service import StaffIdentity
from modest_chic_backend.modules.coupons.enums import CouponType
from modest_chic_backend.modules.coupons.service import CouponService

router = APIRouter(prefix="/admin/coupons", tags=["admin-coupons"])


class CreateCouponRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    type: CouponType
    value_minor: int = Field(gt=0)
    min_order_minor: int | None = Field(default=None, ge=0)
    max_discount_minor: int | None = Field(default=None, gt=0)
    usage_limit: int | None = Field(default=None, gt=0)
    per_customer_limit: int | None = Field(default=1, gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    product_ids: list[UUID] = Field(default_factory=list, max_length=100)
    category_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_window(self) -> "CreateCouponRequest":
        if not self.code.strip():
            raise ValueError("Promotion code cannot be blank.")
        if self.type == CouponType.PERCENT and self.value_minor > 100:
            raise ValueError("Percentage promotions cannot exceed 100 percent.")
        for value in (self.starts_at, self.ends_at):
            if value is not None and value.utcoffset() is None:
                raise ValueError("Promotion dates must include a timezone.")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("Promotion end must be after its start.")
        return self


class UpdateCouponRequest(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    type: CouponType | None = None
    value_minor: int | None = Field(default=None, gt=0)
    min_order_minor: int | None = Field(default=None, ge=0)
    max_discount_minor: int | None = Field(default=None, gt=0)
    usage_limit: int | None = Field(default=None, gt=0)
    per_customer_limit: int | None = Field(default=None, gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    product_ids: list[UUID] | None = Field(default=None, max_length=100)
    category_ids: list[UUID] | None = Field(default=None, max_length=100)
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_window(self) -> "UpdateCouponRequest":
        for field_name in ("code", "type", "value_minor", "is_active"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        if self.code is not None and not self.code.strip():
            raise ValueError("Promotion code cannot be blank.")
        if self.type == CouponType.PERCENT and self.value_minor is not None:
            if self.value_minor > 100:
                raise ValueError("Percentage promotions cannot exceed 100 percent.")
        for value in (self.starts_at, self.ends_at):
            if value is not None and value.utcoffset() is None:
                raise ValueError("Promotion dates must include a timezone.")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("Promotion end must be after its start.")
        return self


@router.get("")
async def list_coupons(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("promotion.read"))],
) -> list[dict[str, object]]:
    database = request.app.state.database
    async with database.session() as session:
        return await CouponService(session).list_coupons()


@router.post("", status_code=201)
async def create_coupon(
    payload: CreateCouponRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("promotion.write"))],
) -> dict[str, object]:
    database = request.app.state.database
    async with database.transaction() as session:
        try:
            return await CouponService(session).create_coupon(
                code=payload.code,
                type=payload.type,
                value_minor=payload.value_minor,
                min_order_minor=payload.min_order_minor,
                max_discount_minor=payload.max_discount_minor,
                usage_limit=payload.usage_limit,
                per_customer_limit=payload.per_customer_limit,
                starts_at=payload.starts_at,
                ends_at=payload.ends_at,
                product_ids=payload.product_ids,
                category_ids=payload.category_ids,
                actor_id=identity.user.id,
            )
        except ValueError as exc:
            raise ApplicationError(400, "COUPON_ERROR", str(exc)) from exc


@router.patch("/{coupon_id}")
async def update_coupon(
    coupon_id: UUID,
    payload: UpdateCouponRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("promotion.write"))],
) -> dict[str, object]:
    database = request.app.state.database
    async with database.transaction() as session:
        try:
            result = await CouponService(session).update_coupon(
                coupon_id, payload.model_dump(exclude_unset=True)
            )
        except ValueError as exc:
            raise ApplicationError(400, "COUPON_ERROR", str(exc)) from exc
        if result is None:
            raise ApplicationError(404, "COUPON_NOT_FOUND", "Promotion not found.")
        return result

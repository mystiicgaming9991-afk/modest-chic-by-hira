"""Coupon eligibility, integer discount allocation, and redemption lifecycle."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.coupons.enums import (
    CouponRedemptionStatus,
    CouponType,
)
from modest_chic_backend.modules.coupons.models import Coupon, CouponRedemption, CouponScope
from modest_chic_backend.modules.coupons.repository import CouponRepository


class CouponService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CouponRepository(session)

    async def create_coupon(
        self,
        code: str,
        type: CouponType,
        value_minor: int,
        actor_id: uuid.UUID,
        product_ids: list[uuid.UUID] | None = None,
        category_ids: list[uuid.UUID] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        normalized_code = _normalize_code(code)
        existing = await self._repo.find_by_code(normalized_code)
        if existing:
            raise ValueError("A promotion with this code already exists.")
        if type == CouponType.PERCENT and value_minor > 100:
            raise ValueError("Percentage promotions cannot exceed 100 percent.")
        coupon = Coupon(
            code=normalized_code,
            type=type,
            value_minor=value_minor,
            created_by=actor_id,
            **kwargs,
        )
        await self._repo.create_coupon(coupon)
        scopes = [
            CouponScope(coupon_id=coupon.id, scope_type="PRODUCT", scope_id=product_id)
            for product_id in set(product_ids or [])
        ]
        scopes.extend(
            CouponScope(coupon_id=coupon.id, scope_type="CATEGORY", scope_id=category_id)
            for category_id in set(category_ids or [])
        )
        if scopes:
            await self._repo.create_scopes(coupon.id, scopes)
        return _coupon_dict(coupon, await self._repo.scopes_for(coupon.id))

    async def list_coupons(self) -> list[dict[str, Any]]:
        coupons = await self._repo.list_coupons()
        return [_coupon_dict(coupon, await self._repo.scopes_for(coupon.id)) for coupon in coupons]

    async def update_coupon(
        self, coupon_id: uuid.UUID, values: dict[str, Any]
    ) -> dict[str, Any] | None:
        coupon = await self._repo.find_by_id(coupon_id, for_update=True)
        if coupon is None:
            return None
        updates = dict(values)
        product_ids = updates.pop("product_ids", None)
        category_ids = updates.pop("category_ids", None)
        if "code" in updates:
            updates["code"] = _normalize_code(updates["code"])
            existing = await self._repo.find_by_code(updates["code"])
            if existing is not None and existing.id != coupon.id:
                raise ValueError("A promotion with this code already exists.")
        coupon_type = updates.get("type", coupon.type)
        value_minor = updates.get("value_minor", coupon.value_minor)
        if coupon_type == CouponType.PERCENT and value_minor > 100:
            raise ValueError("Percentage promotions cannot exceed 100 percent.")
        starts_at = updates.get("starts_at", coupon.starts_at)
        ends_at = updates.get("ends_at", coupon.ends_at)
        if starts_at is not None and starts_at.utcoffset() is None:
            raise ValueError("Promotion dates must include a timezone.")
        if ends_at is not None and ends_at.utcoffset() is None:
            raise ValueError("Promotion dates must include a timezone.")
        if starts_at is not None and ends_at is not None and ends_at <= starts_at:
            raise ValueError("Promotion end must be after its start.")
        for key, value in updates.items():
            setattr(coupon, key, value)
        if product_ids is not None or category_ids is not None:
            existing_scopes = await self._repo.scopes_for(coupon.id)
            if product_ids is None:
                product_ids = [
                    scope.scope_id for scope in existing_scopes if scope.scope_type == "PRODUCT"
                ]
            if category_ids is None:
                category_ids = [
                    scope.scope_id for scope in existing_scopes if scope.scope_type == "CATEGORY"
                ]
            await self._repo.delete_scopes(coupon.id)
            scopes = [
                CouponScope(coupon_id=coupon.id, scope_type="PRODUCT", scope_id=scope_id)
                for scope_id in set(product_ids or [])
            ]
            scopes.extend(
                CouponScope(coupon_id=coupon.id, scope_type="CATEGORY", scope_id=scope_id)
                for scope_id in set(category_ids or [])
            )
            if scopes:
                await self._repo.create_scopes(coupon.id, scopes)
        return _coupon_dict(coupon, await self._repo.scopes_for(coupon.id))

    async def validate_coupon(
        self,
        code: str,
        items: list[dict[str, Any]],
        customer_id: uuid.UUID | None = None,
        *,
        for_update: bool = False,
    ) -> dict[str, Any] | None:
        """Return a current discount and exact per-variant allocations, or None."""
        coupon = await self._repo.find_active_by_code(_normalize_code(code), for_update=for_update)
        now = datetime.now(UTC)
        if (
            coupon is None
            or (coupon.starts_at is not None and coupon.starts_at > now)
            or (coupon.ends_at is not None and coupon.ends_at <= now)
        ):
            return None

        subtotal = sum(int(item["line_total_minor"]) for item in items)
        if coupon.min_order_minor and subtotal < coupon.min_order_minor:
            return None
        uses = await self._repo.count_redemptions(coupon.id)
        if coupon.usage_limit is not None and uses >= coupon.usage_limit:
            return None
        if customer_id is not None and coupon.per_customer_limit is not None:
            customer_uses = await self._repo.count_redemptions(coupon.id, customer_id)
            if customer_uses >= coupon.per_customer_limit:
                return None

        scopes = await self._repo.scopes_for(coupon.id)
        scoped_items = _eligible_items(items, scopes)
        eligible_subtotal = sum(int(item["line_total_minor"]) for item in scoped_items)
        if eligible_subtotal <= 0:
            return None
        if coupon.type == CouponType.FIXED:
            discount = coupon.value_minor
        else:
            discount = eligible_subtotal * coupon.value_minor // 100
        if coupon.max_discount_minor is not None:
            discount = min(discount, coupon.max_discount_minor)
        discount = min(discount, eligible_subtotal)
        if discount <= 0:
            return None
        return {
            "coupon_id": str(coupon.id),
            "code": coupon.code,
            "discount_minor": discount,
            "allocations": _allocate_discount(scoped_items, discount),
        }

    async def reserve_redemption(
        self,
        *,
        code: str,
        items: list[dict[str, Any]],
        customer_id: uuid.UUID | None,
        order_id: uuid.UUID,
        discount_minor: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Revalidate while holding the coupon row lock, then reserve one use."""
        result = await self.validate_coupon(code, items, customer_id, for_update=True)
        if result is None or result["discount_minor"] != discount_minor:
            raise ValueError("Promotion eligibility changed before order acceptance.")
        redemption = CouponRedemption(
            coupon_id=uuid.UUID(result["coupon_id"]),
            customer_id=customer_id,
            order_id=order_id,
            status=CouponRedemptionStatus.RESERVED,
            discount_minor=discount_minor,
            idempotency_key=idempotency_key,
        )
        await self._repo.create_redemption(redemption)
        return _redemption_dict(redemption)

    async def resolve_order_redemption(
        self, order_id: uuid.UUID, status: CouponRedemptionStatus
    ) -> None:
        """Resolve an order's reserved use once; repeat resolution is harmless."""
        redemption = await self._repo.redemption_for_order(order_id)
        if redemption is None:
            return
        resolvable = {CouponRedemptionStatus.RESERVED}
        if status == CouponRedemptionStatus.RELEASED:
            resolvable.add(CouponRedemptionStatus.CONSUMED)
        if redemption.status not in resolvable:
            return
        redemption.status = status
        redemption.resolved_at = datetime.now(UTC)


def _normalize_code(code: str) -> str:
    return code.strip().upper()


def _eligible_items(items: list[dict[str, Any]], scopes: list[CouponScope]) -> list[dict[str, Any]]:
    if not scopes:
        return items
    product_ids = {scope.scope_id for scope in scopes if scope.scope_type.upper() == "PRODUCT"}
    category_ids = {scope.scope_id for scope in scopes if scope.scope_type.upper() == "CATEGORY"}
    if any(scope.scope_type.upper() not in {"PRODUCT", "CATEGORY"} for scope in scopes):
        return []
    return [
        item
        for item in items
        if uuid.UUID(item["product_id"]) in product_ids
        or category_ids.intersection(uuid.UUID(value) for value in item["category_ids"])
    ]


def _allocate_discount(items: list[dict[str, Any]], discount_minor: int) -> dict[str, int]:
    """Allocate proportional line discounts exactly, assigning remainder by stable order."""
    total = sum(int(item["line_total_minor"]) for item in items)
    if total <= 0:
        return {}
    allocations: dict[str, int] = {}
    remaining = discount_minor
    for item in sorted(items, key=lambda value: value["variant_id"]):
        amount = int(item["line_total_minor"])
        allocation = min(remaining, discount_minor * amount // total)
        allocations[str(item["variant_id"])] = allocation
        remaining -= allocation
    for variant_id in sorted(allocations):
        if remaining == 0:
            break
        item = next(item for item in items if item["variant_id"] == variant_id)
        capacity = int(item["line_total_minor"]) - allocations[variant_id]
        extra = min(remaining, capacity)
        allocations[variant_id] += extra
        remaining -= extra
    return allocations


def _coupon_dict(coupon: Any, scopes: list[CouponScope] | None = None) -> dict[str, Any]:
    return {
        "id": str(coupon.id),
        "code": coupon.code,
        "type": coupon.type.value,
        "value_minor": coupon.value_minor,
        "state": coupon.state.value,
        "is_active": coupon.is_active,
        "min_order_minor": coupon.min_order_minor,
        "max_discount_minor": coupon.max_discount_minor,
        "usage_limit": coupon.usage_limit,
        "per_customer_limit": coupon.per_customer_limit,
        "starts_at": coupon.starts_at.isoformat() if coupon.starts_at else None,
        "ends_at": coupon.ends_at.isoformat() if coupon.ends_at else None,
        "product_ids": [
            str(scope.scope_id) for scope in scopes or [] if scope.scope_type == "PRODUCT"
        ],
        "category_ids": [
            str(scope.scope_id) for scope in scopes or [] if scope.scope_type == "CATEGORY"
        ],
    }


def _redemption_dict(redemption: Any) -> dict[str, Any]:
    return {
        "id": str(redemption.id),
        "coupon_id": str(redemption.coupon_id),
        "status": redemption.status.value,
        "discount_minor": redemption.discount_minor,
        "idempotency_key": redemption.idempotency_key,
    }

"""Coupon database access."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.coupons.enums import CouponState
from modest_chic_backend.modules.coupons.models import Coupon, CouponRedemption, CouponScope


class CouponRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_code(self, code: str) -> Coupon | None:
        result = await self._session.execute(select(Coupon).where(Coupon.code == code))
        return result.scalar_one_or_none()

    async def find_by_id(self, coupon_id: uuid.UUID, *, for_update: bool = False) -> Coupon | None:
        query = select(Coupon).where(Coupon.id == coupon_id)
        if for_update:
            query = query.with_for_update()
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list_coupons(self, limit: int = 100) -> list[Coupon]:
        result = await self._session.execute(
            select(Coupon).order_by(Coupon.created_at.desc(), Coupon.id).limit(limit)
        )
        return list(result.scalars().all())

    async def find_active_by_code(self, code: str, *, for_update: bool = False) -> Coupon | None:
        query = select(Coupon).where(
            Coupon.code == code,
            Coupon.is_active,
            Coupon.state == CouponState.ACTIVE,
        )
        if for_update:
            query = query.with_for_update()
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def scopes_for(self, coupon_id: uuid.UUID) -> list[CouponScope]:
        result = await self._session.execute(
            select(CouponScope).where(CouponScope.coupon_id == coupon_id)
        )
        return list(result.scalars().all())

    async def create_scopes(self, coupon_id: uuid.UUID, scopes: list[CouponScope]) -> None:
        self._session.add_all(scopes)
        await self._session.flush()

    async def delete_scopes(self, coupon_id: uuid.UUID) -> None:
        await self._session.execute(delete(CouponScope).where(CouponScope.coupon_id == coupon_id))

    async def create_coupon(self, coupon: Coupon) -> Coupon:
        self._session.add(coupon)
        await self._session.flush()
        return coupon

    async def count_redemptions(
        self, coupon_id: uuid.UUID, customer_id: uuid.UUID | None = None
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(CouponRedemption)
            .where(
                CouponRedemption.coupon_id == coupon_id,
                CouponRedemption.status.in_(["RESERVED", "CONSUMED"]),
            )
        )
        if customer_id:
            stmt = stmt.where(CouponRedemption.customer_id == customer_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create_redemption(self, redemption: CouponRedemption) -> CouponRedemption:
        self._session.add(redemption)
        await self._session.flush()
        return redemption

    async def redemption_for_order(self, order_id: uuid.UUID) -> CouponRedemption | None:
        result = await self._session.execute(
            select(CouponRedemption).where(CouponRedemption.order_id == order_id).with_for_update()
        )
        return result.scalar_one_or_none()

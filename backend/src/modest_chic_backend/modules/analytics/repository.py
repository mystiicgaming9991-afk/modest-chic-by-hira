"""Analytics repository — read-only aggregated queries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.inventory.models import InventoryBalance
from modest_chic_backend.modules.inventory.repository import InventoryRepository
from modest_chic_backend.modules.orders.enums import OrderState, PaymentMethod
from modest_chic_backend.modules.orders.models import Order
from modest_chic_backend.modules.orders.queries import (
    packing_queue_condition,
    stock_reservation_exception_condition,
)
from modest_chic_backend.modules.reviews.models import Review


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def order_state_counts(self) -> dict[OrderState, int]:
        rows = await self._session.execute(select(Order.state, func.count()).group_by(Order.state))
        return {state: count for state, count in rows.all()}

    async def pending_cod_count(self) -> int:
        """Count orders represented by the COD confirmation queue filter."""
        count = await self._session.scalar(
            select(func.count(Order.id)).where(
                Order.payment_method == PaymentMethod.COD,
                Order.state == OrderState.PENDING_CONFIRMATION,
            )
        )
        return int(count or 0)

    async def packing_queue_count(self) -> int:
        """Count processing delivery orders that still have eligible units to pack."""
        count = await self._session.scalar(
            select(func.count(Order.id)).where(packing_queue_condition())
        )
        return int(count or 0)

    async def stock_reservation_exception_count(self) -> int:
        """Count confirmed/processing orders that cannot fulfill remaining units."""
        count = await self._session.scalar(
            select(func.count(Order.id)).where(stock_reservation_exception_condition())
        )
        return int(count or 0)

    async def pending_review_count(self) -> int:
        """Count reviews represented by the staff moderation queue filter."""
        count = await self._session.scalar(
            select(func.count(Review.id)).where(Review.status == "PENDING")
        )
        return int(count or 0)

    async def zero_available_balance_count(self) -> int:
        """Count inventory balances with no unreserved units."""
        count = await self._session.scalar(
            select(func.count(InventoryBalance.id)).where(
                InventoryBalance.on_hand == InventoryBalance.reserved
            )
        )
        return int(count or 0)

    async def low_stock_balance_count(self) -> int:
        """Count balances at or below a staff-configured threshold."""
        return await InventoryRepository(self._session).low_stock_balance_count()

    async def attributed_order_totals(
        self, start_at: datetime, end_at: datetime
    ) -> list[dict[str, Any]]:
        state_counts = {
            state: func.sum(case((Order.state == state, 1), else_=0)).label(
                f"state_{state.value.lower()}"
            )
            for state in OrderState
        }
        query = (
            select(
                Order.attribution_source,
                Order.attribution_campaign,
                Order.attribution_creator_code,
                Order.source,
                func.count(Order.id).label("order_count"),
                func.sum(Order.subtotal_minor).label("subtotal_minor"),
                func.sum(Order.discount_minor).label("discount_minor"),
                func.sum(Order.shipping_charge_minor).label("shipping_charge_minor"),
                func.sum(Order.total_minor).label("accepted_total_minor"),
                *state_counts.values(),
            )
            .where(
                Order.order_placed_at >= start_at,
                Order.order_placed_at < end_at,
                or_(
                    Order.attribution_source.is_not(None),
                    Order.attribution_campaign.is_not(None),
                    Order.attribution_creator_code.is_not(None),
                ),
            )
            .group_by(
                Order.attribution_source,
                Order.attribution_campaign,
                Order.attribution_creator_code,
                Order.source,
            )
            .order_by(
                Order.attribution_creator_code,
                Order.attribution_campaign,
                Order.attribution_source,
                Order.source,
            )
        )
        result = await self._session.execute(query)
        rows = result.all()
        dimensions = (
            "attribution_source",
            "campaign",
            "creator_code",
            "order_source",
            "order_count",
            "subtotal_minor",
            "discount_minor",
            "shipping_charge_minor",
            "accepted_total_minor",
        )
        state_dimensions = tuple(f"state_{state.value.lower()}" for state in OrderState)
        return [
            {key: value for key, value in zip((*dimensions, *state_dimensions), row, strict=True)}
            for row in rows
        ]

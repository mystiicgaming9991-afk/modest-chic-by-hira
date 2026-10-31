"""Order repository."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.orders.models import Order, OrderEvent, OrderItem


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_order(self, order_id: uuid.UUID) -> Order | None:
        return await self._session.get(Order, order_id)

    async def create_order(self, order: Order) -> Order:
        self._session.add(order)
        await self._session.flush()
        return order

    async def add_item(self, item: OrderItem) -> OrderItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def record_event(self, event: OrderEvent) -> OrderEvent:
        self._session.add(event)
        await self._session.flush()
        return event

    async def next_order_number(self) -> str:
        from datetime import UTC, datetime

        await self._session.execute(text("SELECT pg_advisory_xact_lock(9413001)"))
        today = datetime.now(UTC).strftime("%Y%m%d")
        result = await self._session.execute(select(func.count()).select_from(Order))
        count = result.scalar_one() + 1
        return f"MC-{today}-{count:04d}"

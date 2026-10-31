"""Cart database access — guest carts and item lines."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modest_chic_backend.modules.cart.models import Cart, CartItem


class CartRepository:
    """Read/write guest cart entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_token_hash(self, token_hash: str) -> Cart | None:
        result = await self._session.execute(
            select(Cart)
            .options(selectinload(Cart.items))
            .where(Cart.guest_token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_cart_with_items(self, cart_id: uuid.UUID) -> Cart | None:
        result = await self._session.execute(
            select(Cart).options(selectinload(Cart.items)).where(Cart.id == cart_id)
        )
        return result.scalar_one_or_none()

    async def create_cart(self, token_hash: str) -> Cart:
        cart = Cart(
            guest_token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            items=[],
        )
        self._session.add(cart)
        await self._session.flush()
        return cart

    async def add_or_update_item(
        self, cart_id: uuid.UUID, variant_id: uuid.UUID, quantity: int
    ) -> CartItem:
        result = await self._session.execute(
            select(CartItem).where(CartItem.cart_id == cart_id, CartItem.variant_id == variant_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.quantity = quantity
            await self._session.flush()
            return existing
        item = CartItem(cart_id=cart_id, variant_id=variant_id, quantity=quantity)
        self._session.add(item)
        await self._session.flush()
        return item

    async def remove_item(self, cart_id: uuid.UUID, item_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart_id)
        )
        await self._session.flush()

"""Guest cart business logic — create, add, update, remove, expire."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.cart.repository import CartRepository


class CartService:
    """Application service for guest cart operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CartRepository(session)

    async def get_or_create_cart(self, guest_token_hash: str) -> dict[str, Any]:
        existing = await self._repo.find_by_token_hash(guest_token_hash)
        if existing and existing.expires_at > datetime.now(UTC):
            return _cart_dict(existing)
        if existing:
            existing.items.clear()
            from datetime import timedelta

            existing.expires_at = datetime.now(UTC) + timedelta(days=7)
            existing.version += 1
            return _cart_dict(existing)
        cart = await self._repo.create_cart(guest_token_hash)
        return _cart_dict(cart)

    async def get_cart(self, guest_token_hash: str) -> dict[str, Any] | None:
        existing = await self._repo.find_by_token_hash(guest_token_hash)
        if existing is None or existing.expires_at <= datetime.now(UTC):
            return None
        return _cart_dict(existing)

    async def add_item(
        self, cart_id: uuid.UUID, variant_id: uuid.UUID, quantity: int
    ) -> dict[str, Any]:
        cart = await self._repo.get_cart_with_items(cart_id)
        if cart is None:
            raise ValueError("cart not found")
        await self._repo.add_or_update_item(cart_id, variant_id, quantity)
        cart.version += 1
        # Reload
        cart = await self._repo.get_cart_with_items(cart_id)
        assert cart is not None
        return _cart_dict(cart)

    async def remove_item(self, cart_id: uuid.UUID, item_id: uuid.UUID) -> dict[str, Any]:
        cart = await self._repo.get_cart_with_items(cart_id)
        if cart is None:
            raise ValueError("cart not found")
        await self._repo.remove_item(cart_id, item_id)
        cart.version += 1
        cart = await self._repo.get_cart_with_items(cart_id)
        assert cart is not None
        return _cart_dict(cart)


def _cart_dict(c: Any) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "version": c.version,
        "currency": c.currency,
        "expires_at": c.expires_at.isoformat(),
        "items": [
            {"id": str(i.id), "variant_id": str(i.variant_id), "quantity": i.quantity}
            for i in (c.items or [])
        ],
    }

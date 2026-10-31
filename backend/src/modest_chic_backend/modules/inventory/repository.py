"""Inventory database access — balances, reservations, movements, locations."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.catalog.models import Product, ProductVariant
from modest_chic_backend.modules.inventory.enums import (
    MovementReason,
    ReservationStatus,
)
from modest_chic_backend.modules.inventory.models import (
    InventoryBalance,
    InventoryLocation,
    InventoryMovement,
    InventoryReservation,
)
from modest_chic_backend.modules.orders.models import OrderItem


class InventoryRepository:
    """Read/write inventory entities with row-locking for concurrency."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Locations ───────────────────────────────────────────────

    async def get_location_by_key(self, key: str) -> InventoryLocation | None:
        result = await self._session.execute(
            select(InventoryLocation).where(InventoryLocation.key == key)
        )
        return result.scalar_one_or_none()

    async def list_locations(self) -> list[InventoryLocation]:
        result = await self._session.execute(
            select(InventoryLocation)
            .where(InventoryLocation.is_active.is_(True))
            .order_by(InventoryLocation.name, InventoryLocation.id)
        )
        return list(result.scalars().all())

    async def list_balances(
        self,
        *,
        variant_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        limit: int = 100,
    ) -> list[tuple[InventoryBalance, ProductVariant, Product, InventoryLocation]]:
        stmt = (
            select(InventoryBalance, ProductVariant, Product, InventoryLocation)
            .join(ProductVariant, ProductVariant.id == InventoryBalance.variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .join(InventoryLocation, InventoryLocation.id == InventoryBalance.location_id)
            .order_by(
                Product.title,
                ProductVariant.sku,
                InventoryLocation.name,
                Product.id,
                ProductVariant.id,
                InventoryLocation.id,
            )
            .limit(limit)
        )
        if variant_id:
            stmt = stmt.where(InventoryBalance.variant_id == variant_id)
        if location_id:
            stmt = stmt.where(InventoryBalance.location_id == location_id)
        result = await self._session.execute(stmt)
        return list(result.all())

    async def list_zero_available_balances(
        self, *, limit: int, offset: int
    ) -> list[tuple[InventoryBalance, ProductVariant, Product, InventoryLocation]]:
        result = await self._session.execute(
            select(InventoryBalance, ProductVariant, Product, InventoryLocation)
            .join(ProductVariant, ProductVariant.id == InventoryBalance.variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .join(InventoryLocation, InventoryLocation.id == InventoryBalance.location_id)
            .where(InventoryBalance.on_hand == InventoryBalance.reserved)
            .order_by(
                Product.title,
                ProductVariant.sku,
                InventoryLocation.name,
                Product.id,
                ProductVariant.id,
                InventoryLocation.id,
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def zero_available_balance_count(self) -> int:
        count = await self._session.scalar(
            select(func.count(InventoryBalance.id)).where(
                InventoryBalance.on_hand == InventoryBalance.reserved
            )
        )
        return int(count or 0)

    async def list_low_stock_balances(
        self, *, limit: int, offset: int
    ) -> list[tuple[InventoryBalance, ProductVariant, Product, InventoryLocation]]:
        result = await self._session.execute(
            select(InventoryBalance, ProductVariant, Product, InventoryLocation)
            .join(ProductVariant, ProductVariant.id == InventoryBalance.variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .join(InventoryLocation, InventoryLocation.id == InventoryBalance.location_id)
            .where(
                InventoryBalance.low_stock_threshold.is_not(None),
                InventoryBalance.on_hand - InventoryBalance.reserved
                <= InventoryBalance.low_stock_threshold,
            )
            .order_by(
                Product.title,
                ProductVariant.sku,
                InventoryLocation.name,
                Product.id,
                ProductVariant.id,
                InventoryLocation.id,
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def low_stock_balance_count(self) -> int:
        count = await self._session.scalar(
            select(func.count(InventoryBalance.id)).where(
                InventoryBalance.low_stock_threshold.is_not(None),
                InventoryBalance.on_hand - InventoryBalance.reserved
                <= InventoryBalance.low_stock_threshold,
            )
        )
        return int(count or 0)

    async def get_variant_with_product(
        self, variant_id: uuid.UUID
    ) -> tuple[ProductVariant, Product] | None:
        result = await self._session.execute(
            select(ProductVariant, Product)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(ProductVariant.id == variant_id)
        )
        row = result.one_or_none()
        return (row[0], row[1]) if row else None

    async def list_variants(self, *, limit: int = 500) -> list[tuple[ProductVariant, Product]]:
        result = await self._session.execute(
            select(ProductVariant, Product)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(ProductVariant.is_active.is_(True))
            .order_by(Product.title, ProductVariant.sku)
            .limit(limit)
        )
        return list(result.all())

    # ── Balances ────────────────────────────────────────────────

    async def get_balance(
        self, variant_id: uuid.UUID, location_id: uuid.UUID
    ) -> InventoryBalance | None:
        result = await self._session.execute(
            select(InventoryBalance).where(
                InventoryBalance.variant_id == variant_id,
                InventoryBalance.location_id == location_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_balance_for_update(
        self, variant_id: uuid.UUID, location_id: uuid.UUID
    ) -> InventoryBalance | None:
        result = await self._session.execute(
            select(InventoryBalance)
            .where(
                InventoryBalance.variant_id == variant_id,
                InventoryBalance.location_id == location_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_balance_by_id_for_update(self, balance_id: uuid.UUID) -> InventoryBalance | None:
        result = await self._session.execute(
            select(InventoryBalance).where(InventoryBalance.id == balance_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_or_create_balance(
        self, variant_id: uuid.UUID, location_id: uuid.UUID
    ) -> InventoryBalance:
        existing = await self.get_balance_for_update(variant_id, location_id)
        if existing:
            return existing
        balance = InventoryBalance(
            variant_id=variant_id, location_id=location_id, on_hand=0, reserved=0
        )
        self._session.add(balance)
        await self._session.flush()
        return balance

    # ── Movements ───────────────────────────────────────────────

    async def check_idempotent(self, idempotency_key: str) -> InventoryMovement | None:
        if not idempotency_key:
            return None
        result = await self._session.execute(
            select(InventoryMovement).where(InventoryMovement.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def record_movement(
        self,
        variant_id: uuid.UUID,
        location_id: uuid.UUID,
        delta_on_hand: int,
        delta_reserved: int,
        reason: MovementReason,
        *,
        actor_id: uuid.UUID | None = None,
        order_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
        notes: str | None = None,
    ) -> InventoryMovement:
        movement = InventoryMovement(
            variant_id=variant_id,
            location_id=location_id,
            delta_on_hand=delta_on_hand,
            delta_reserved=delta_reserved,
            reason=reason,
            actor_id=actor_id,
            order_id=order_id,
            idempotency_key=idempotency_key,
            notes=notes,
            created_at=func.clock_timestamp(),
            updated_at=func.clock_timestamp(),
        )
        self._session.add(movement)
        await self._session.flush()
        return movement

    # ── Reservations ────────────────────────────────────────────

    async def order_id_for_item(self, order_item_id: uuid.UUID) -> uuid.UUID | None:
        return await self._session.scalar(
            select(OrderItem.order_id).where(OrderItem.id == order_item_id)
        )

    async def create_reservation(
        self,
        balance_id: uuid.UUID,
        order_item_id: uuid.UUID,
        quantity: int,
        expires_at: datetime | None,
    ) -> InventoryReservation:
        reservation = InventoryReservation(
            balance_id=balance_id,
            order_item_id=order_item_id,
            quantity=quantity,
            status=ReservationStatus.ACTIVE,
            expires_at=expires_at,
        )
        self._session.add(reservation)
        await self._session.flush()
        return reservation

    async def get_reservation_for_update(
        self, reservation_id: uuid.UUID
    ) -> InventoryReservation | None:
        result = await self._session.execute(
            select(InventoryReservation)
            .where(InventoryReservation.id == reservation_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def find_stale_reservations(self) -> list[InventoryReservation]:
        from datetime import UTC

        now = datetime.now(UTC)
        result = await self._session.execute(
            select(InventoryReservation)
            .where(
                InventoryReservation.status == ReservationStatus.ACTIVE,
                InventoryReservation.expires_at <= now,
            )
            .with_for_update()
        )
        return list(result.scalars().all())

    async def list_movements(
        self,
        variant_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        after: uuid.UUID | None = None,
        limit: int = 20,
    ) -> list[InventoryMovement]:
        stmt = select(InventoryMovement).order_by(
            InventoryMovement.created_at.desc(), InventoryMovement.id.desc()
        )
        if variant_id:
            stmt = stmt.where(InventoryMovement.variant_id == variant_id)
        if location_id:
            stmt = stmt.where(InventoryMovement.location_id == location_id)
        if after:
            cursor = await self._session.get(InventoryMovement, after)
            if cursor is None:
                return []
            stmt = stmt.where(
                or_(
                    InventoryMovement.created_at < cursor.created_at,
                    and_(
                        InventoryMovement.created_at == cursor.created_at,
                        InventoryMovement.id < cursor.id,
                    ),
                )
            )
        stmt = stmt.limit(limit + 1)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

"""Inventory business logic — stock management and order reservations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.audit.repository import AuditRepository
from modest_chic_backend.modules.coupons.enums import CouponRedemptionStatus
from modest_chic_backend.modules.coupons.service import CouponService
from modest_chic_backend.modules.inventory.enums import (
    MovementReason,
    ReservationStatus,
)
from modest_chic_backend.modules.inventory.repository import InventoryRepository
from modest_chic_backend.modules.orders.enums import OrderState, PaymentState
from modest_chic_backend.modules.orders.models import Order


class InventoryService:
    """Application service for stock movements and reservation lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = InventoryRepository(session)
        self._audit = AuditRepository(session)

    async def list_locations(self) -> list[dict[str, object]]:
        return [
            {"id": str(location.id), "key": location.key, "name": location.name}
            for location in await self._repo.list_locations()
        ]

    async def list_variants(self, *, limit: int = 500) -> list[dict[str, object]]:
        return [
            {
                "id": str(variant.id),
                "product_id": str(product.id),
                "product_title": product.title,
                "sku": variant.sku,
                "color_name": variant.color_name,
            }
            for variant, product in await self._repo.list_variants(limit=limit)
        ]

    async def list_balances(
        self,
        *,
        variant_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        rows = await self._repo.list_balances(
            variant_id=variant_id, location_id=location_id, limit=limit
        )
        return [
            _inventory_balance_row(balance, variant, product, location)
            for balance, variant, product, location in rows
        ]

    async def zero_available_balances(
        self, *, limit: int = 100, offset: int = 0
    ) -> dict[str, object]:
        """List paginated stock balances with no units available to sell."""
        rows = await self._repo.list_zero_available_balances(limit=limit, offset=offset)
        return {
            "items": [
                _inventory_balance_row(balance, variant, product, location)
                for balance, variant, product, location in rows
            ],
            "total_count": await self._repo.zero_available_balance_count(),
            "limit": limit,
            "offset": offset,
        }

    async def low_stock_balances(self, *, limit: int = 100, offset: int = 0) -> dict[str, object]:
        """List balances at or below an explicitly configured threshold."""
        rows = await self._repo.list_low_stock_balances(limit=limit, offset=offset)
        return {
            "items": [
                _inventory_balance_row(balance, variant, product, location)
                for balance, variant, product, location in rows
            ],
            "total_count": await self._repo.low_stock_balance_count(),
            "limit": limit,
            "offset": offset,
        }

    async def set_low_stock_threshold(
        self,
        *,
        variant_id: uuid.UUID,
        location_id: uuid.UUID,
        threshold: int | None,
        actor_id: uuid.UUID,
    ) -> dict[str, object]:
        """Set or clear a staff-selected alert threshold for one stock balance."""
        if threshold is not None and threshold < 0:
            raise ValueError("low-stock threshold cannot be negative")
        balance = await self._repo.get_balance_for_update(variant_id, location_id)
        if balance is None:
            raise ValueError("no balance record for this variant+location")
        previous = balance.low_stock_threshold
        if previous == threshold:
            return _balance_dict(balance)
        balance.low_stock_threshold = threshold
        await self._audit.record(
            action="inventory.low_stock_threshold.updated",
            entity_type="inventory_balance",
            entity_id=balance.id,
            actor_id=actor_id,
            metadata={
                "variant_id": str(variant_id),
                "location_id": str(location_id),
                "previous_threshold": previous,
                "low_stock_threshold": threshold,
            },
        )
        return _balance_dict(balance)

    async def list_movements(
        self,
        *,
        variant_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        after: uuid.UUID | None = None,
        limit: int = 20,
    ) -> dict[str, object]:
        rows = await self._repo.list_movements(
            variant_id=variant_id,
            location_id=location_id,
            after=after,
            limit=limit,
        )
        has_more = len(rows) > limit
        movements = rows[:limit]
        return {
            "items": [
                {
                    "id": str(movement.id),
                    "variant_id": str(movement.variant_id),
                    "location_id": str(movement.location_id),
                    "delta_on_hand": movement.delta_on_hand,
                    "delta_reserved": movement.delta_reserved,
                    "reason": movement.reason.value,
                    "actor_id": str(movement.actor_id) if movement.actor_id else None,
                    "order_id": str(movement.order_id) if movement.order_id else None,
                    "notes": movement.notes,
                    "created_at": movement.created_at.isoformat(),
                }
                for movement in movements
            ],
            "next_cursor": str(movements[-1].id) if has_more and movements else None,
        }

    # ── Receive ─────────────────────────────────────────────────

    async def receive_stock(
        self,
        variant_id: uuid.UUID,
        location_key: str,
        quantity: int,
        actor_id: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> dict[str, object]:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if await self._repo.get_variant_with_product(variant_id) is None:
            raise ValueError("unknown variant")

        location = await self._repo.get_location_by_key(location_key)
        if location is None:
            raise ValueError(f"unknown location: {location_key}")

        replay = await self._get_replayed_balance(
            idempotency_key,
            variant_id=variant_id,
            location_id=location.id,
            delta_on_hand=quantity,
            reason=MovementReason.RECEIVE,
        )
        if replay is not None:
            return replay

        balance = await self._repo.get_or_create_balance(variant_id, location.id)
        balance.on_hand += quantity

        await self._repo.record_movement(
            variant_id=variant_id,
            location_id=location.id,
            delta_on_hand=quantity,
            delta_reserved=0,
            reason=MovementReason.RECEIVE,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
        )
        return _balance_dict(balance)

    # ── Adjust ──────────────────────────────────────────────────

    async def adjust_stock(
        self,
        variant_id: uuid.UUID,
        location_id: uuid.UUID,
        delta: int,
        reason: MovementReason,
        actor_id: uuid.UUID,
        idempotency_key: str | None = None,
        notes: str | None = None,
    ) -> dict[str, object]:
        if reason != MovementReason.ADJUST:
            raise ValueError("manual adjustments must use the ADJUST reason")
        if delta == 0:
            raise ValueError("adjustment delta cannot be zero")
        if not notes or not notes.strip():
            raise ValueError("an adjustment note is required")
        if await self._repo.get_variant_with_product(variant_id) is None:
            raise ValueError("unknown variant")

        replay = await self._get_replayed_balance(
            idempotency_key,
            variant_id=variant_id,
            location_id=location_id,
            delta_on_hand=delta,
            reason=reason,
            notes=notes.strip(),
        )
        if replay is not None:
            return replay

        balance = await self._repo.get_balance_for_update(variant_id, location_id)
        if balance is None:
            raise ValueError("no balance record for this variant+location")

        if balance.on_hand + delta < balance.reserved:
            raise ValueError(
                f"adjustment would reduce stock below reserved quantity: "
                f"on_hand={balance.on_hand}, reserved={balance.reserved}, delta={delta}"
            )

        balance.on_hand += delta

        await self._repo.record_movement(
            variant_id=variant_id,
            location_id=location_id,
            delta_on_hand=delta,
            delta_reserved=0,
            reason=reason,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            notes=notes.strip(),
        )
        return _balance_dict(balance)

    async def _get_replayed_balance(
        self,
        idempotency_key: str | None,
        *,
        variant_id: uuid.UUID,
        location_id: uuid.UUID,
        delta_on_hand: int,
        reason: MovementReason,
        notes: str | None = None,
    ) -> dict[str, object] | None:
        if not idempotency_key:
            return None
        existing = await self._repo.check_idempotent(idempotency_key)
        if existing is None:
            return None
        if (
            existing.variant_id != variant_id
            or existing.location_id != location_id
            or existing.delta_on_hand != delta_on_hand
            or existing.delta_reserved != 0
            or existing.reason != reason
            or (notes is not None and existing.notes != notes)
        ):
            raise ValueError("idempotency key was already used for a different stock movement")
        balance = await self._repo.get_balance(variant_id, location_id)
        if balance is None:
            raise ValueError("idempotent stock movement has no balance record")
        return _balance_dict(balance)

    # ── Reserve ─────────────────────────────────────────────────

    async def reserve(
        self,
        balance_id: uuid.UUID,
        order_item_id: uuid.UUID,
        quantity: int,
        expires_at: datetime | None = None,
        order_id: uuid.UUID | None = None,
    ) -> dict[str, object]:
        if quantity <= 0:
            raise ValueError("quantity must be positive")

        balance = await self._repo.get_balance_by_id_for_update(balance_id)
        if balance is None:
            raise ValueError("balance not found")

        available = balance.on_hand - balance.reserved
        if available < quantity:
            raise ValueError(
                f"insufficient available stock: available={available}, requested={quantity}"
            )

        balance.reserved += quantity

        await self._repo.create_reservation(
            balance_id=balance_id,
            order_item_id=order_item_id,
            quantity=quantity,
            expires_at=expires_at,
        )
        await self._repo.record_movement(
            variant_id=balance.variant_id,
            location_id=balance.location_id,
            delta_on_hand=0,
            delta_reserved=quantity,
            reason=MovementReason.RESERVE,
            order_id=order_id,
        )
        return _balance_dict(balance)

    # ── Release ─────────────────────────────────────────────────

    async def release(
        self, reservation_id: uuid.UUID, actor_id: uuid.UUID | None = None
    ) -> dict[str, object] | None:
        reservation = await self._repo.get_reservation_for_update(reservation_id)
        if reservation is None:
            raise ValueError("reservation not found")

        if reservation.status != ReservationStatus.ACTIVE:
            # Idempotent: already RELEASED, CONSUMED, or EXPIRED
            return {"status": reservation.status.value}

        balance = await self._repo.get_balance_by_id_for_update(reservation.balance_id)
        if balance is None:
            raise ValueError("balance not found")

        balance.reserved -= reservation.quantity
        reservation.status = ReservationStatus.RELEASED
        reservation.resolved_at = datetime.now(UTC)

        await self._repo.record_movement(
            variant_id=balance.variant_id,
            location_id=balance.location_id,
            delta_on_hand=0,
            delta_reserved=-reservation.quantity,
            reason=MovementReason.RELEASE,
            actor_id=actor_id,
            order_id=await self._repo.order_id_for_item(reservation.order_item_id),
        )
        return _balance_dict(balance)

    # ── Consume ─────────────────────────────────────────────────

    async def consume(
        self, reservation_id: uuid.UUID, actor_id: uuid.UUID | None = None
    ) -> dict[str, object] | None:
        reservation = await self._repo.get_reservation_for_update(reservation_id)
        if reservation is None:
            raise ValueError("reservation not found")

        if reservation.status != ReservationStatus.ACTIVE:
            return {"status": reservation.status.value}

        balance = await self._repo.get_balance_by_id_for_update(reservation.balance_id)
        if balance is None:
            raise ValueError("balance not found")

        balance.on_hand -= reservation.quantity
        balance.reserved -= reservation.quantity
        reservation.status = ReservationStatus.CONSUMED
        reservation.resolved_at = datetime.now(UTC)

        await self._repo.record_movement(
            variant_id=balance.variant_id,
            location_id=balance.location_id,
            delta_on_hand=-reservation.quantity,
            delta_reserved=-reservation.quantity,
            reason=MovementReason.CONSUME,
            actor_id=actor_id,
            order_id=await self._repo.order_id_for_item(reservation.order_item_id),
        )
        return _balance_dict(balance)

    # ── Expire Stale ────────────────────────────────────────────

    async def expire_stale(self) -> int:
        stale = await self._repo.find_stale_reservations()
        expired_count = 0
        for reservation in stale:
            order_id = await self._repo.order_id_for_item(reservation.order_item_id)
            order = await self._session.get(Order, order_id) if order_id else None
            if order and (
                order.state
                in {
                    OrderState.CONFIRMED,
                    OrderState.PROCESSING,
                    OrderState.FULFILLED,
                    OrderState.COMPLETED,
                }
                or order.payment_state
                in {
                    PaymentState.AUTHORIZED,
                    PaymentState.PAID,
                    PaymentState.PARTIALLY_REFUNDED,
                }
            ):
                continue
            balance = await self._repo.get_balance_by_id_for_update(reservation.balance_id)
            if balance is None:
                continue
            balance.reserved -= reservation.quantity
            reservation.status = ReservationStatus.EXPIRED
            reservation.resolved_at = datetime.now(UTC)
            if order_id:
                await CouponService(self._session).resolve_order_redemption(
                    order_id, CouponRedemptionStatus.EXPIRED
                )
            await self._repo.record_movement(
                variant_id=balance.variant_id,
                location_id=balance.location_id,
                delta_on_hand=0,
                delta_reserved=-reservation.quantity,
                reason=MovementReason.EXPIRE,
                order_id=order_id,
            )
            expired_count += 1
        return expired_count


def _balance_dict(b: Any) -> dict[str, object]:
    # b is InventoryBalance or mock — duck-typed for test compatibility
    return {
        "variant_id": str(b.variant_id),
        "location_id": str(b.location_id),
        "on_hand": b.on_hand,
        "reserved": b.reserved,
        "available": b.on_hand - b.reserved,
        "low_stock_threshold": b.low_stock_threshold,
    }


def _inventory_balance_row(
    balance: Any, variant: Any, product: Any, location: Any
) -> dict[str, object]:
    return {
        **_balance_dict(balance),
        "product_title": product.title,
        "sku": variant.sku,
        "color_name": variant.color_name,
        "location_name": location.name,
        "location_key": location.key,
    }

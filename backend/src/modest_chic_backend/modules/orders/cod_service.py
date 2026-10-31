"""Staff COD confirmation, contact history, and reservation decisions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.coupons.enums import CouponRedemptionStatus
from modest_chic_backend.modules.coupons.service import CouponService
from modest_chic_backend.modules.inventory.enums import ReservationStatus
from modest_chic_backend.modules.inventory.models import InventoryReservation
from modest_chic_backend.modules.inventory.service import InventoryService
from modest_chic_backend.modules.orders.enums import OrderState, PaymentMethod
from modest_chic_backend.modules.orders.models import Order, OrderEvent, OrderItem
from modest_chic_backend.modules.orders.queries import stock_reservation_exception_condition


class CodConfirmationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def pending(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        queue_filter = (
            Order.payment_method == PaymentMethod.COD,
            Order.state == OrderState.PENDING_CONFIRMATION,
        )
        total_count = int(
            await self._session.scalar(select(func.count(Order.id)).where(*queue_filter)) or 0
        )
        rows = await self._session.execute(
            select(
                Order,
                stock_reservation_exception_condition().label("stock_reservation_exception"),
            )
            .where(*queue_filter)
            .order_by(Order.created_at, Order.id)
            .limit(limit)
            .offset(offset)
        )
        return {
            "items": [
                {
                    **self._summary(order),
                    "stock_reservation_exception": stock_reservation_exception,
                }
                for order, stock_reservation_exception in rows.all()
            ],
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }

    async def contact_attempt(
        self,
        order_id: uuid.UUID,
        actor_id: uuid.UUID,
        channel: str,
        outcome: str,
        notes: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        normalized_notes = notes.strip()
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": "cod-contact-attempt:" + idempotency_key},
        )
        order = await self._session.scalar(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        if order is None:
            raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
        metadata = {"channel": channel, "outcome": outcome, "notes": normalized_notes}
        previous_event = await self._session.scalar(
            select(OrderEvent).where(OrderEvent.idempotency_key == idempotency_key)
        )
        if previous_event is not None:
            if (
                previous_event.order_id != order_id
                or previous_event.event_type != "cod.contact_attempt"
                or previous_event.event_metadata != metadata
            ):
                raise ApplicationError(
                    409,
                    "CONTACT_ATTEMPT_REPLAY_CONFLICT",
                    "This contact attempt key was used with different details.",
                )
            return self._summary(order)
        if (
            order.payment_method != PaymentMethod.COD
            or order.state != OrderState.PENDING_CONFIRMATION
        ):
            raise ApplicationError(
                409, "ORDER_NOT_PENDING", "Order is not awaiting COD confirmation."
            )
        self._session.add(
            OrderEvent(
                order_id=order.id,
                event_type="cod.contact_attempt",
                actor_type="staff",
                actor_id=actor_id,
                event_metadata=metadata,
                idempotency_key=idempotency_key,
            )
        )
        await self._session.flush()
        return self._summary(order)

    async def decide(
        self,
        order_id: uuid.UUID,
        actor_id: uuid.UUID,
        confirmed: bool,
        channel: str,
        notes: str,
    ) -> dict[str, Any]:
        order = await self._pending_order_for_update(order_id)
        items = (
            await self._session.scalars(select(OrderItem).where(OrderItem.order_id == order_id))
        ).all()
        if not items:
            raise ApplicationError(409, "ORDER_ITEMS_MISSING", "Order items are missing.")
        reservations = (
            await self._session.scalars(
                select(InventoryReservation)
                .where(InventoryReservation.order_item_id.in_([item.id for item in items]))
                .order_by(InventoryReservation.id)
                .with_for_update()
            )
        ).all()
        now = datetime.now(UTC)
        if confirmed:
            for item in items:
                valid_quantity = sum(
                    reservation.quantity
                    for reservation in reservations
                    if reservation.order_item_id == item.id
                    and reservation.status == ReservationStatus.ACTIVE
                    and (reservation.expires_at is None or reservation.expires_at > now)
                )
                if valid_quantity < item.quantity:
                    raise ApplicationError(
                        409,
                        "RESERVATION_UNAVAILABLE",
                        "This order no longer has enough reserved stock.",
                    )
            order.state = OrderState.CONFIRMED
            order.confirmed_at = now
            await CouponService(self._session).resolve_order_redemption(
                order.id, CouponRedemptionStatus.CONSUMED
            )
            event_type = "cod.confirmed"
        else:
            inventory = InventoryService(self._session)
            for reservation in reservations:
                if reservation.status == ReservationStatus.ACTIVE:
                    await inventory.release(reservation.id, actor_id=actor_id)
            order.state = OrderState.CANCELLED
            order.cancelled_at = now
            await CouponService(self._session).resolve_order_redemption(
                order.id, CouponRedemptionStatus.RELEASED
            )
            event_type = "cod.declined"
        self._session.add(
            OrderEvent(
                order_id=order.id,
                event_type=event_type,
                previous_state=OrderState.PENDING_CONFIRMATION,
                new_state=order.state,
                actor_type="staff",
                actor_id=actor_id,
                event_metadata={"channel": channel, "notes": notes},
            )
        )
        await self._session.flush()
        return self._summary(order)

    async def _pending_order_for_update(self, order_id: uuid.UUID) -> Order:
        order = await self._session.scalar(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        if order is None:
            raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
        if (
            order.payment_method != PaymentMethod.COD
            or order.state != OrderState.PENDING_CONFIRMATION
        ):
            raise ApplicationError(
                409, "ORDER_NOT_PENDING", "Order is not awaiting COD confirmation."
            )
        return order

    @staticmethod
    def _summary(order: Order) -> dict[str, Any]:
        return {
            "id": str(order.id),
            "number": order.number,
            "state": order.state.value,
            "customer_name": order.customer_name,
            "customer_phone": order.customer_phone,
            "total_minor": order.total_minor,
            "fulfillment_method": order.fulfillment_method.value,
            "address_city": order.address_city,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        }

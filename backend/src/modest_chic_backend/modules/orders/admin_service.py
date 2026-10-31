"""Permissioned order search and snapshot detail for staff."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.coupons.enums import CouponRedemptionStatus
from modest_chic_backend.modules.coupons.service import CouponService
from modest_chic_backend.modules.fulfillment.models import (
    Pickup,
    Shipment,
    ShipmentEvent,
    ShipmentItem,
)
from modest_chic_backend.modules.inventory.enums import ReservationStatus
from modest_chic_backend.modules.inventory.models import InventoryReservation
from modest_chic_backend.modules.inventory.service import InventoryService
from modest_chic_backend.modules.orders.enums import OrderSource, OrderState, PaymentState
from modest_chic_backend.modules.orders.models import (
    Order,
    OrderEvent,
    OrderItem,
    OrderPolicyAcceptance,
)
from modest_chic_backend.modules.orders.queries import (
    packing_queue_condition,
    stock_reservation_exception_condition,
)
from modest_chic_backend.modules.payments.models import Payment, PaymentEvent
from modest_chic_backend.modules.policies.models import PolicyVersion
from modest_chic_backend.modules.refunds.models import Refund
from modest_chic_backend.modules.returns.models import Return


class OrderAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def pack_delivery(
        self,
        order_id: uuid.UUID,
        actor_id: uuid.UUID,
        idempotency_key: str,
        allocations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        requested = _shipment_allocations(allocations)
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": "shipment-pack:" + idempotency_key},
        )
        order = await self._session.scalar(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        if order is None:
            raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
        existing = await self._session.scalar(
            select(Shipment).where(Shipment.idempotency_key == idempotency_key)
        )
        if existing is not None:
            if existing.order_id != order_id:
                raise ApplicationError(
                    409,
                    "SHIPMENT_REPLAY_CONFLICT",
                    "This pack request key belongs to another order.",
                )
            existing_items = (
                await self._session.scalars(
                    select(ShipmentItem).where(ShipmentItem.shipment_id == existing.id)
                )
            ).all()
            if {item.order_item_id: item.quantity for item in existing_items} != requested:
                raise ApplicationError(
                    409,
                    "SHIPMENT_REPLAY_CONFLICT",
                    "This pack request key was already used with different allocations.",
                )
            return _shipment_summary(existing)
        if order.fulfillment_method.value != "DELIVERY":
            raise ApplicationError(
                409, "DELIVERY_REQUIRED", "Only delivery orders can be packed for shipment."
            )
        if order.state != OrderState.PROCESSING:
            raise ApplicationError(
                409, "ORDER_NOT_PROCESSING", "Only an order in processing can be packed."
            )
        if order.payment_method.value == "COD":
            if order.confirmed_at is None:
                raise ApplicationError(
                    409, "COD_NOT_CONFIRMED", "COD confirmation is required before packing."
                )
        elif order.payment_state not in {PaymentState.AUTHORIZED, PaymentState.PAID}:
            raise ApplicationError(
                409, "PAYMENT_NOT_ELIGIBLE", "Verified payment is required before packing."
            )

        if not requested:
            raise ApplicationError(
                422, "SHIPMENT_ITEMS_REQUIRED", "Allocate at least one order item."
            )

        order_items = (
            await self._session.scalars(
                select(OrderItem)
                .where(OrderItem.order_id == order_id)
                .order_by(OrderItem.id)
                .with_for_update()
            )
        ).all()
        item_by_id = {item.id: item for item in order_items}
        if not set(requested).issubset(item_by_id):
            raise ApplicationError(
                422, "SHIPMENT_ITEM_INVALID", "An allocated item does not belong to this order."
            )
        item_ids = list(item_by_id)
        packed_rows = await self._session.execute(
            select(ShipmentItem.order_item_id, func.sum(ShipmentItem.quantity))
            .join(Shipment, Shipment.id == ShipmentItem.shipment_id)
            .where(Shipment.order_id == order_id)
            .group_by(ShipmentItem.order_item_id)
        )
        packed = {item_id: int(quantity) for item_id, quantity in packed_rows.all()}
        reservation_rows = await self._session.execute(
            select(InventoryReservation.order_item_id, func.sum(InventoryReservation.quantity))
            .where(
                InventoryReservation.order_item_id.in_(item_ids),
                InventoryReservation.status == ReservationStatus.ACTIVE,
            )
            .group_by(InventoryReservation.order_item_id)
        )
        reserved = {item_id: int(quantity) for item_id, quantity in reservation_rows.all()}
        for item_id, quantity in requested.items():
            item = item_by_id[item_id]
            already_packed = packed.get(item_id, 0)
            remaining_ordered = item.quantity - already_packed
            remaining_reserved = reserved.get(item_id, 0) - already_packed
            if quantity > remaining_ordered or quantity > remaining_reserved:
                raise ApplicationError(
                    409,
                    "SHIPMENT_QUANTITY_EXCEEDED",
                    "Packing exceeds the order's unfulfilled, reserved quantity.",
                )

        shipment = Shipment(
            order_id=order_id,
            status="PACKED",
            idempotency_key=idempotency_key,
            created_by=actor_id,
        )
        self._session.add(shipment)
        await self._session.flush()
        shipment.merchant_reference = f"{order.number}-{shipment.id.hex[:10].upper()}"
        self._session.add_all(
            [
                ShipmentItem(
                    shipment_id=shipment.id,
                    order_item_id=item_id,
                    quantity=quantity,
                )
                for item_id, quantity in requested.items()
            ]
        )
        self._session.add(
            ShipmentEvent(
                shipment_id=shipment.id,
                event_type="PACKED",
                notes="Shipment allocated and packed; courier booking has not been requested.",
                created_by=actor_id,
            )
        )
        await self._session.flush()
        return _shipment_summary(shipment)

    async def handoff_delivery(
        self, order_id: uuid.UUID, actor_id: uuid.UUID, idempotency_key: str
    ) -> dict[str, Any]:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": "delivery-handoff:" + idempotency_key},
        )
        order = await self._session.scalar(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        if order is None:
            raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
        previous_event = await self._session.scalar(
            select(OrderEvent).where(OrderEvent.idempotency_key == idempotency_key)
        )
        if previous_event is not None:
            if (
                previous_event.order_id != order_id
                or previous_event.event_type != "order.delivery_handed_off"
            ):
                raise ApplicationError(
                    409,
                    "ORDER_COMMAND_REPLAY_CONFLICT",
                    "This command key belongs to another order action.",
                )
            return _order_summary(order)
        if order.fulfillment_method.value != "DELIVERY":
            raise ApplicationError(
                409, "DELIVERY_REQUIRED", "Only delivery orders can be handed to a courier."
            )
        if order.state != OrderState.PROCESSING:
            raise ApplicationError(
                409, "ORDER_NOT_PROCESSING", "Only a processing order can be handed off."
            )
        if order.payment_method.value == "COD":
            if order.confirmed_at is None:
                raise ApplicationError(
                    409, "COD_NOT_CONFIRMED", "COD confirmation is required before handoff."
                )
        elif order.payment_state not in {PaymentState.AUTHORIZED, PaymentState.PAID}:
            raise ApplicationError(
                409, "PAYMENT_NOT_ELIGIBLE", "Verified payment is required before handoff."
            )

        shipments = list(
            (
                await self._session.scalars(
                    select(Shipment)
                    .where(Shipment.order_id == order_id)
                    .order_by(Shipment.id)
                    .with_for_update()
                )
            ).all()
        )
        if not shipments or any(shipment.status != "PACKED" for shipment in shipments):
            raise ApplicationError(
                409,
                "SHIPMENTS_NOT_READY",
                "Every shipment must be packed and awaiting handoff.",
            )

        order_items = list(
            (
                await self._session.scalars(
                    select(OrderItem)
                    .where(OrderItem.order_id == order_id)
                    .order_by(OrderItem.id)
                    .with_for_update()
                )
            ).all()
        )
        if not order_items:
            raise ApplicationError(409, "ORDER_ITEMS_MISSING", "Order items are unavailable.")
        shipment_rows = await self._session.execute(
            select(ShipmentItem.order_item_id, func.sum(ShipmentItem.quantity))
            .where(ShipmentItem.shipment_id.in_([shipment.id for shipment in shipments]))
            .group_by(ShipmentItem.order_item_id)
        )
        packed = {item_id: int(quantity) for item_id, quantity in shipment_rows.all()}
        expected = {
            item.id: item.quantity - item.fulfilled_quantity
            for item in order_items
            if item.quantity > item.fulfilled_quantity
        }
        if packed != expected:
            raise ApplicationError(
                409,
                "SHIPMENTS_INCOMPLETE",
                "All remaining order quantities must be allocated before handoff.",
            )

        item_ids = list(expected)
        reservations = list(
            (
                await self._session.scalars(
                    select(InventoryReservation)
                    .where(
                        InventoryReservation.order_item_id.in_(item_ids),
                        InventoryReservation.status == ReservationStatus.ACTIVE,
                    )
                    .order_by(InventoryReservation.balance_id, InventoryReservation.id)
                    .with_for_update()
                )
            ).all()
        )
        reserved: dict[uuid.UUID, int] = {}
        for reservation in reservations:
            reserved[reservation.order_item_id] = (
                reserved.get(reservation.order_item_id, 0) + reservation.quantity
            )
        if reserved != expected:
            raise ApplicationError(
                409,
                "RESERVATION_MISMATCH",
                "Active stock reservations must match the shipment allocations.",
            )

        inventory = InventoryService(self._session)
        for reservation in reservations:
            await inventory.consume(reservation.id, actor_id=actor_id)
        now = datetime.now(UTC)
        shipment_ids = [str(shipment.id) for shipment in shipments]
        for shipment in shipments:
            shipment.status = "HANDED_OFF"
            shipment.shipped_at = now
            self._session.add(
                ShipmentEvent(
                    shipment_id=shipment.id,
                    event_type="HANDED_OFF",
                    notes="Parcel handed to courier by authorized staff.",
                    created_by=actor_id,
                )
            )
        for item in order_items:
            item.fulfilled_quantity = item.quantity
        order.state = OrderState.FULFILLED
        order.fulfilled_at = now
        self._session.add(
            OrderEvent(
                order_id=order.id,
                event_type="order.delivery_handed_off",
                previous_state=OrderState.PROCESSING,
                new_state=OrderState.FULFILLED,
                actor_type="staff",
                actor_id=actor_id,
                event_metadata={"shipment_ids": shipment_ids},
                idempotency_key=idempotency_key,
                effective_at=now,
            )
        )
        await self._session.flush()
        return _order_summary(order)

    async def cancel_order(
        self, order_id: uuid.UUID, actor_id: uuid.UUID, idempotency_key: str, reason: str
    ) -> dict[str, Any]:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ApplicationError(422, "CANCELLATION_REASON_REQUIRED", "A reason is required.")
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": "order-cancel:" + idempotency_key},
        )
        order = await self._session.scalar(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        if order is None:
            raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
        previous_event = await self._session.scalar(
            select(OrderEvent).where(OrderEvent.idempotency_key == idempotency_key)
        )
        if previous_event is not None:
            if (
                previous_event.order_id != order_id
                or previous_event.event_type != "order.cancelled"
                or (previous_event.event_metadata or {}).get("reason") != normalized_reason
            ):
                raise ApplicationError(
                    409,
                    "ORDER_COMMAND_REPLAY_CONFLICT",
                    "This command key was already used for a different order action or reason.",
                )
            return _order_summary(order)
        if order.state not in {
            OrderState.PENDING_CONFIRMATION,
            OrderState.CONFIRMED,
            OrderState.PROCESSING,
        }:
            raise ApplicationError(
                409,
                "ORDER_NOT_CANCELLABLE",
                "Only an unfulfilled order can be cancelled.",
            )
        if order.payment_state not in {PaymentState.PENDING, PaymentState.FAILED}:
            raise ApplicationError(
                409,
                "PAYMENT_REQUIRES_RESOLUTION",
                "Resolve authorization, collection, or refund through the payment workflow first.",
            )

        shipments = list(
            (
                await self._session.scalars(
                    select(Shipment)
                    .where(Shipment.order_id == order_id)
                    .order_by(Shipment.id)
                    .with_for_update()
                )
            ).all()
        )
        if any(shipment.status != "PACKED" for shipment in shipments):
            raise ApplicationError(
                409,
                "SHIPMENT_REQUIRES_RESOLUTION",
                "A booked, handed-off, or otherwise progressed shipment cannot be cancelled here.",
            )
        pickups = list(
            (
                await self._session.scalars(
                    select(Pickup)
                    .where(Pickup.order_id == order_id)
                    .order_by(Pickup.id)
                    .with_for_update()
                )
            ).all()
        )
        if any(pickup.status.upper() == "COLLECTED" for pickup in pickups):
            raise ApplicationError(
                409,
                "PICKUP_ALREADY_COLLECTED",
                "A collected pickup cannot be cancelled here.",
            )

        items = list(
            (
                await self._session.scalars(
                    select(OrderItem)
                    .where(OrderItem.order_id == order_id)
                    .order_by(OrderItem.id)
                    .with_for_update()
                )
            ).all()
        )
        if not items or any(item.fulfilled_quantity > 0 for item in items):
            raise ApplicationError(
                409,
                "ORDER_ALREADY_FULFILLED",
                "Fulfilled quantities must be handled through returns and refunds.",
            )
        reservations = list(
            (
                await self._session.scalars(
                    select(InventoryReservation)
                    .where(
                        InventoryReservation.order_item_id.in_([item.id for item in items]),
                        InventoryReservation.status == ReservationStatus.ACTIVE,
                    )
                    .order_by(InventoryReservation.balance_id, InventoryReservation.id)
                    .with_for_update()
                )
            ).all()
        )
        inventory = InventoryService(self._session)
        for reservation in reservations:
            await inventory.release(reservation.id, actor_id=actor_id)
        await CouponService(self._session).resolve_order_redemption(
            order.id, CouponRedemptionStatus.RELEASED
        )

        now = datetime.now(UTC)
        for shipment in shipments:
            shipment.status = "CANCELLED"
            self._session.add(
                ShipmentEvent(
                    shipment_id=shipment.id,
                    event_type="CANCELLED",
                    notes="Shipment cancelled before courier handoff.",
                    created_by=actor_id,
                )
            )
        for pickup in pickups:
            pickup.status = "CANCELLED"
        previous_state = order.state
        order.state = OrderState.CANCELLED
        order.cancelled_at = now
        self._session.add(
            OrderEvent(
                order_id=order.id,
                event_type="order.cancelled",
                previous_state=previous_state,
                new_state=OrderState.CANCELLED,
                actor_type="staff",
                actor_id=actor_id,
                event_metadata={"reason": normalized_reason},
                idempotency_key=idempotency_key,
                effective_at=now,
            )
        )
        await self._session.flush()
        return _order_summary(order)

    async def start_processing(
        self, order_id: uuid.UUID, actor_id: uuid.UUID, idempotency_key: str
    ) -> dict[str, Any]:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": "order-command:" + idempotency_key},
        )
        order = await self._session.scalar(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        if order is None:
            raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
        previous_event = await self._session.scalar(
            select(OrderEvent).where(OrderEvent.idempotency_key == idempotency_key)
        )
        if previous_event is not None:
            if (
                previous_event.order_id != order_id
                or previous_event.event_type != "order.processing_started"
            ):
                raise ApplicationError(
                    409,
                    "ORDER_COMMAND_REPLAY_CONFLICT",
                    "This command key belongs to another order.",
                )
            return _order_summary(order)
        if order.state != OrderState.CONFIRMED:
            raise ApplicationError(
                409, "ORDER_NOT_CONFIRMED", "Only a confirmed order can enter processing."
            )
        if order.payment_state in {PaymentState.FAILED, PaymentState.REFUNDED}:
            raise ApplicationError(
                409, "PAYMENT_NOT_PROCESSABLE", "This order has no processable payment state."
            )
        stock_exception = await self._session.scalar(
            select(stock_reservation_exception_condition()).where(Order.id == order_id)
        )
        if stock_exception:
            raise ApplicationError(
                409,
                "RESERVATION_UNAVAILABLE",
                "This order no longer has enough active reserved stock.",
            )
        order.state = OrderState.PROCESSING
        self._session.add(
            OrderEvent(
                order_id=order.id,
                event_type="order.processing_started",
                previous_state=OrderState.CONFIRMED,
                new_state=OrderState.PROCESSING,
                actor_type="staff",
                actor_id=actor_id,
                idempotency_key=idempotency_key,
            )
        )
        await self._session.flush()
        return _order_summary(order)

    async def search(
        self,
        *,
        query: str | None = None,
        state: OrderState | None = None,
        source: OrderSource | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        packing_only: bool = False,
        stock_exception_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        stmt = select(Order).order_by(Order.created_at.desc(), Order.id.desc())
        if query:
            term = f"%{query.strip()}%"
            stmt = stmt.where(
                Order.number.ilike(term)
                | Order.customer_name.ilike(term)
                | Order.customer_phone.ilike(term)
                | Order.customer_email.ilike(term)
            )
        if state is not None:
            stmt = stmt.where(Order.state == state)
        if packing_only:
            stmt = stmt.where(packing_queue_condition())
        if stock_exception_only:
            stmt = stmt.where(stock_reservation_exception_condition())
        if source is not None:
            stmt = stmt.where(Order.source == source)
        if from_date is not None:
            stmt = stmt.where(Order.created_at >= datetime.combine(from_date, time.min, tzinfo=UTC))
        if to_date is not None:
            stmt = stmt.where(
                Order.created_at
                < datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=UTC)
            )
        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._session.scalars(stmt)).all()
        return [_order_summary(order) for order in rows]

    async def detail(
        self,
        order_id: uuid.UUID,
        *,
        include_customer_details: bool,
        include_payments: bool,
        include_refunds: bool,
    ) -> dict[str, Any] | None:
        order = await self._session.get(Order, order_id)
        if order is None:
            return None
        stock_reservation_exception = await self._session.scalar(
            select(stock_reservation_exception_condition()).where(Order.id == order_id)
        )
        items = (
            await self._session.scalars(
                select(OrderItem)
                .where(OrderItem.order_id == order_id)
                .order_by(OrderItem.created_at, OrderItem.id)
            )
        ).all()
        events = (
            await self._session.scalars(
                select(OrderEvent)
                .where(OrderEvent.order_id == order_id)
                .order_by(OrderEvent.effective_at, OrderEvent.id)
            )
        ).all()
        payments: Sequence[Payment] = ()
        if include_payments:
            payments = (
                await self._session.scalars(
                    select(Payment)
                    .where(Payment.order_id == order_id)
                    .order_by(Payment.attempt_number)
                )
            ).all()
        payment_events: Sequence[PaymentEvent] = []
        if payments:
            payment_events = (
                await self._session.scalars(
                    select(PaymentEvent)
                    .where(PaymentEvent.payment_id.in_([payment.id for payment in payments]))
                    .order_by(PaymentEvent.created_at, PaymentEvent.id)
                )
            ).all()
        shipments = (
            await self._session.scalars(select(Shipment).where(Shipment.order_id == order_id))
        ).all()
        shipment_items: Sequence[ShipmentItem] = []
        if shipments:
            shipment_items = (
                await self._session.scalars(
                    select(ShipmentItem)
                    .where(ShipmentItem.shipment_id.in_([shipment.id for shipment in shipments]))
                    .order_by(ShipmentItem.created_at, ShipmentItem.id)
                )
            ).all()
        shipment_events: Sequence[ShipmentEvent] = []
        if shipments:
            shipment_events = (
                await self._session.scalars(
                    select(ShipmentEvent)
                    .where(ShipmentEvent.shipment_id.in_([shipment.id for shipment in shipments]))
                    .order_by(ShipmentEvent.created_at, ShipmentEvent.id)
                )
            ).all()
        pickups = (
            await self._session.scalars(select(Pickup).where(Pickup.order_id == order_id))
        ).all()
        returns = (
            await self._session.scalars(select(Return).where(Return.order_id == order_id))
        ).all()
        policy_acceptances = (
            await self._session.execute(
                select(OrderPolicyAcceptance, PolicyVersion)
                .join(PolicyVersion, PolicyVersion.id == OrderPolicyAcceptance.policy_version_id)
                .where(OrderPolicyAcceptance.order_id == order_id)
                .order_by(OrderPolicyAcceptance.policy_type)
            )
        ).all()
        refunds: Sequence[Refund] = ()
        if include_refunds:
            refunds = (
                await self._session.scalars(select(Refund).where(Refund.order_id == order_id))
            ).all()
        return {
            **_order_summary(order),
            "stock_reservation_exception": bool(stock_reservation_exception),
            "customer_id": (
                str(order.customer_id) if include_customer_details and order.customer_id else None
            ),
            "customer_email": order.customer_email if include_customer_details else None,
            "address": {
                "line1": order.address_line1,
                "line2": order.address_line2,
                "area": order.address_area,
                "city": order.address_city,
                "postal_code": order.address_postal_code,
                "country_code": order.address_country_code,
                "delivery_notes": order.delivery_notes,
            },
            "subtotal_minor": order.subtotal_minor,
            "discount_minor": order.discount_minor,
            "shipping_charge_minor": order.shipping_charge_minor,
            "policy_version_id": str(order.policy_version_id) if order.policy_version_id else None,
            "accepted_policies": [
                {
                    "type": acceptance.policy_type,
                    "policy_version_id": str(policy.id),
                    "version": policy.version,
                }
                for acceptance, policy in policy_acceptances
            ],
            "attribution": {
                "source": order.attribution_source,
                "campaign": order.attribution_campaign,
                "creator_code": order.attribution_creator_code,
            },
            "items": [
                {
                    "id": str(item.id),
                    "variant_id": str(item.variant_id) if item.variant_id else None,
                    "sku": item.sku,
                    "product_title": item.product_title,
                    "variant_name": item.variant_name,
                    "quantity": item.quantity,
                    "fulfilled_quantity": item.fulfilled_quantity,
                    "unit_price_minor": item.unit_price_minor,
                    "sale_price_minor": item.sale_price_minor,
                    "discount_allocated_minor": item.discount_allocated_minor,
                    "line_total_minor": item.line_total_minor,
                }
                for item in items
            ],
            "events": [_event_dict(event) for event in events],
            "payments": [
                {
                    "id": str(payment.id),
                    "provider": payment.provider,
                    "method": payment.method,
                    "attempt_number": payment.attempt_number,
                    "amount_minor": payment.amount_minor,
                    "currency": payment.currency,
                    "status": payment.status,
                    "provider_txn_id": payment.provider_txn_id,
                    "events": [
                        _payment_event_dict(event)
                        for event in payment_events
                        if event.payment_id == payment.id
                    ],
                }
                for payment in payments
            ],
            "shipments": [
                {
                    "id": str(shipment.id),
                    "courier": shipment.courier,
                    "tracking_number": shipment.tracking_number,
                    "status": shipment.status,
                    "shipped_at": _iso(shipment.shipped_at),
                    "delivered_at": _iso(shipment.delivered_at),
                    "merchant_reference": shipment.merchant_reference,
                    "items": [
                        {"order_item_id": str(item.order_item_id), "quantity": item.quantity}
                        for item in shipment_items
                        if item.shipment_id == shipment.id
                    ],
                    "events": [
                        _shipment_event_dict(event)
                        for event in shipment_events
                        if event.shipment_id == shipment.id
                    ],
                }
                for shipment in shipments
            ],
            "pickups": [
                {
                    "id": str(pickup.id),
                    "status": pickup.status,
                    "ready_at": _iso(pickup.ready_at),
                    "collected_at": _iso(pickup.collected_at),
                }
                for pickup in pickups
            ],
            "returns": [
                {"id": str(entry.id), "state": entry.state, "reason": entry.reason}
                for entry in returns
            ],
            "refunds": [
                {
                    "id": str(entry.id),
                    "amount_minor": entry.amount_minor,
                    "state": entry.state,
                    "reason": entry.reason,
                    "provider_reference": entry.provider_reference,
                }
                for entry in refunds
            ],
        }


def _order_summary(order: Order) -> dict[str, Any]:
    return {
        "id": str(order.id),
        "number": order.number,
        "source": order.source.value,
        "state": order.state.value,
        "payment_state": order.payment_state.value,
        "payment_method": order.payment_method.value,
        "fulfillment_method": order.fulfillment_method.value,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "total_minor": order.total_minor,
        "currency": order.currency,
        "created_at": _iso(order.created_at),
    }


def _shipment_summary(shipment: Shipment) -> dict[str, Any]:
    return {
        "id": str(shipment.id),
        "order_id": str(shipment.order_id),
        "status": shipment.status,
        "merchant_reference": shipment.merchant_reference,
    }


def _shipment_allocations(allocations: list[dict[str, Any]]) -> dict[uuid.UUID, int]:
    requested: dict[uuid.UUID, int] = {}
    for allocation in allocations:
        item_id = uuid.UUID(str(allocation["order_item_id"]))
        quantity = int(allocation["quantity"])
        if quantity <= 0:
            raise ApplicationError(
                422, "SHIPMENT_QUANTITY_INVALID", "Shipment quantities must be positive."
            )
        requested[item_id] = requested.get(item_id, 0) + quantity
    return requested


def _event_dict(event: OrderEvent) -> dict[str, Any]:
    return {
        "event_type": event.event_type,
        "previous_state": event.previous_state.value if event.previous_state else None,
        "new_state": event.new_state.value if event.new_state else None,
        "actor_type": event.actor_type,
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "metadata": event.event_metadata,
        "effective_at": _iso(event.effective_at),
    }


def _payment_event_dict(event: PaymentEvent) -> dict[str, Any]:
    return {"event_type": event.event_type, "created_at": _iso(event.created_at)}


def _shipment_event_dict(event: ShipmentEvent) -> dict[str, Any]:
    return {
        "event_type": event.event_type,
        "location": event.location,
        "notes": event.notes,
        "actor_id": str(event.created_by) if event.created_by else None,
        "created_at": _iso(event.created_at),
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None

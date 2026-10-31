"""Reusable SQL filters for staff order work queues."""

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from modest_chic_backend.modules.fulfillment.models import Shipment, ShipmentItem
from modest_chic_backend.modules.inventory.enums import ReservationStatus
from modest_chic_backend.modules.inventory.models import InventoryReservation
from modest_chic_backend.modules.orders.enums import (
    FulfillmentMethod,
    OrderState,
    PaymentMethod,
    PaymentState,
)
from modest_chic_backend.modules.orders.models import Order, OrderItem


def packing_queue_condition() -> ColumnElement[bool]:
    """Match processing delivery orders with eligible payment and units left to pack."""
    packed_quantity = (
        select(func.coalesce(func.sum(ShipmentItem.quantity), 0))
        .join(Shipment, Shipment.id == ShipmentItem.shipment_id)
        .where(
            Shipment.order_id == Order.id,
            Shipment.status == "PACKED",
            ShipmentItem.order_item_id == OrderItem.id,
        )
        .correlate(Order, OrderItem)
        .scalar_subquery()
    )
    has_unpacked_items = exists(
        select(OrderItem.id).where(
            OrderItem.order_id == Order.id,
            OrderItem.quantity > OrderItem.fulfilled_quantity + packed_quantity,
        )
    )
    payment_is_eligible = or_(
        and_(
            Order.payment_method == PaymentMethod.COD,
            Order.confirmed_at.is_not(None),
        ),
        and_(
            Order.payment_method != PaymentMethod.COD,
            Order.payment_state.in_({PaymentState.AUTHORIZED, PaymentState.PAID}),
        ),
    )
    return and_(
        Order.state == OrderState.PROCESSING,
        Order.fulfillment_method == FulfillmentMethod.DELIVERY,
        payment_is_eligible,
        has_unpacked_items,
    )


def stock_reservation_exception_condition() -> ColumnElement[bool]:
    """Match actionable orders with outstanding units lacking live reservations."""
    reserved_quantity = (
        select(func.coalesce(func.sum(InventoryReservation.quantity), 0))
        .where(
            InventoryReservation.order_item_id == OrderItem.id,
            InventoryReservation.status == ReservationStatus.ACTIVE,
            or_(
                InventoryReservation.expires_at.is_(None),
                InventoryReservation.expires_at > func.now(),
            ),
        )
        .correlate(OrderItem)
        .scalar_subquery()
    )
    outstanding_quantity = OrderItem.quantity - OrderItem.fulfilled_quantity
    has_unreserved_units = exists(
        select(OrderItem.id).where(
            OrderItem.order_id == Order.id,
            outstanding_quantity > 0,
            reserved_quantity < outstanding_quantity,
        )
    )
    is_awaiting_cod_confirmation = and_(
        Order.state == OrderState.PENDING_CONFIRMATION,
        Order.payment_method == PaymentMethod.COD,
    )
    is_fulfillment_eligible = Order.state.in_({OrderState.CONFIRMED, OrderState.PROCESSING})
    return and_(
        or_(is_awaiting_cod_confirmation, is_fulfillment_eligible),
        has_unreserved_units,
    )

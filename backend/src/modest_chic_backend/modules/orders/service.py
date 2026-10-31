"""Order business logic — creation, state transitions, snapshots."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.orders.enums import (
    FulfillmentMethod,
    OrderSource,
    OrderState,
    PaymentMethod,
    PaymentState,
)
from modest_chic_backend.modules.orders.models import Order, OrderEvent, OrderItem
from modest_chic_backend.modules.orders.repository import OrderRepository

_VALID_TRANSITIONS: dict[OrderState, set[OrderState]] = {
    OrderState.PENDING_CONFIRMATION: {OrderState.CONFIRMED, OrderState.CANCELLED},
    OrderState.CONFIRMED: {OrderState.PROCESSING, OrderState.CANCELLED},
    OrderState.PROCESSING: {OrderState.FULFILLED, OrderState.CANCELLED},
    OrderState.FULFILLED: {OrderState.COMPLETED},
    OrderState.COMPLETED: set(),
    OrderState.CANCELLED: set(),
}


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = OrderRepository(session)

    async def create_order(
        self,
        *,
        customer_name: str | None,
        customer_phone: str | None,
        fulfillment_method: str,
        payment_method: str,
        items: list[dict[str, Any]],
        subtotal_minor: int,
        total_minor: int,
        discount_minor: int = 0,
        shipping_charge_minor: int = 0,
        checkout_idempotency_key: str,
        source: str = "STOREFRONT",
        actor_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        number = await self._repo.next_order_number()
        request_hash = hashlib.sha256(
            json.dumps(items, sort_keys=True, default=str).encode()
        ).hexdigest()

        order = Order(
            number=number,
            checkout_idempotency_key=checkout_idempotency_key,
            checkout_request_hash=request_hash,
            source=OrderSource(source),
            customer_name=customer_name,
            customer_phone=customer_phone,
            fulfillment_method=FulfillmentMethod(fulfillment_method),
            payment_method=PaymentMethod(payment_method),
            subtotal_minor=subtotal_minor,
            discount_minor=discount_minor,
            shipping_charge_minor=shipping_charge_minor,
            total_minor=total_minor,
            state=OrderState.PENDING_CONFIRMATION,
            payment_state=PaymentState.PENDING,
            created_by=actor_id,
            **kwargs,
        )
        await self._repo.create_order(order)

        for item_data in items:
            item = OrderItem(
                order_id=order.id,
                variant_id=(
                    uuid.UUID(str(item_data["variant_id"])) if item_data.get("variant_id") else None
                ),
                sku=str(item_data["sku"]),
                product_title=str(item_data["product_title"]),
                variant_name=str(item_data["variant_name"]),
                color_name=item_data.get("color_name"),
                quantity=int(item_data["quantity"]),
                unit_price_minor=int(item_data["unit_price_minor"]),
                sale_price_minor=item_data.get("sale_price_minor"),
                discount_allocated_minor=int(item_data.get("discount_allocated_minor", 0)),
                line_total_minor=int(item_data["line_total_minor"]),
            )
            await self._repo.add_item(item)

        await self._repo.record_event(
            OrderEvent(
                order_id=order.id,
                event_type="order.placed",
                new_state=OrderState.PENDING_CONFIRMATION,
                actor_type="staff" if actor_id else "system",
                actor_id=actor_id,
            )
        )
        return _order_dict(order)

    async def transition(
        self,
        order_id: uuid.UUID,
        to_state: OrderState,
        event_type: str,
        actor_type: str,
        actor_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        order = await self._repo.get_order(order_id)
        if order is None:
            raise LookupError("order not found")

        valid = _VALID_TRANSITIONS.get(order.state, set())
        if to_state not in valid:
            raise ValueError(f"invalid transition: {order.state.value} → {to_state.value}")

        previous = order.state
        order.state = to_state
        now = datetime.now(UTC)
        if to_state == OrderState.CONFIRMED:
            order.confirmed_at = now
        elif to_state == OrderState.FULFILLED:
            order.fulfilled_at = now
        elif to_state == OrderState.COMPLETED:
            order.completed_at = now
        elif to_state == OrderState.CANCELLED:
            order.cancelled_at = now

        await self._repo.record_event(
            OrderEvent(
                order_id=order.id,
                event_type=event_type,
                previous_state=previous,
                new_state=to_state,
                actor_type=actor_type,
                actor_id=actor_id,
            )
        )
        return _order_dict(order)


def _order_dict(o: Any) -> dict[str, Any]:
    return {
        "id": str(o.id),
        "number": o.number,
        "state": o.state.value if hasattr(o.state, "value") else str(o.state),
        "payment_state": o.payment_state.value
        if hasattr(o.payment_state, "value")
        else str(o.payment_state),
        "source": o.source.value if hasattr(o.source, "value") else str(o.source),
        "total_minor": o.total_minor,
        "subtotal_minor": o.subtotal_minor,
        "currency": o.currency,
    }

"""Privacy-safe order data for the exact-order guest access view."""

from collections.abc import Sequence
from typing import TypedDict

from modest_chic_backend.modules.orders.models import OrderEvent

_CUSTOMER_EVENT_LABELS = {
    "order.placed": "Order placed",
    "order.claimed": "Order saved to your account",
    "cod.confirmed": "Order confirmed",
    "cod.declined": "Order cancelled",
    "order.processing_started": "Your order is being prepared",
    "order.delivery_handed_off": "Order handed to courier",
    "order.cancelled": "Order cancelled",
}


class CustomerOrderEvent(TypedDict):
    label: str
    occurred_at: str


def customer_order_timeline(events: Sequence[OrderEvent]) -> list[CustomerOrderEvent]:
    """Map allow-listed lifecycle events to buyer-safe labels and timestamps.

    Free-form metadata, actor identity, and unknown event types are intentionally omitted
    because order events can contain internal notes or operational identifiers.
    """
    return [
        {
            "label": _CUSTOMER_EVENT_LABELS[event.event_type],
            "occurred_at": event.effective_at.isoformat(),
        }
        for event in events
        if event.event_type in _CUSTOMER_EVENT_LABELS
    ]


__all__ = ["CustomerOrderEvent", "customer_order_timeline"]

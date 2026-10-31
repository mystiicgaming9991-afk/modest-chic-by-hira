"""Buyer order timelines must omit private event metadata and unknown event types."""

from datetime import UTC, datetime

from modest_chic_backend.modules.orders.customer_view import customer_order_timeline
from modest_chic_backend.modules.orders.models import OrderEvent


def test_customer_order_timeline_is_allow_listed_and_redacts_event_metadata() -> None:
    occurred_at = datetime(2026, 10, 25, 9, 30, tzinfo=UTC)
    events = [
        OrderEvent(
            event_type="order.placed",
            actor_type="system",
            effective_at=occurred_at,
            event_metadata={"customer_email": "private@example.test"},
        ),
        OrderEvent(
            event_type="cod.contact_attempt",
            actor_type="staff",
            effective_at=occurred_at,
            event_metadata={"notes": "Buyer asked us to call after 6pm."},
        ),
    ]

    assert customer_order_timeline(events) == [
        {"label": "Order placed", "occurred_at": occurred_at.isoformat()}
    ]

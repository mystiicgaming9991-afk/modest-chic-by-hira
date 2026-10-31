"""Unit tests for order service. TDD RED."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def test_create_order_produces_order_with_snapshots() -> None:
    from modest_chic_backend.modules.orders.service import OrderService

    mock_session = AsyncMock()
    svc = OrderService(mock_session)

    async def _create_side_effect(order):
        order.id = uuid.uuid4()
        order.number = "MC-20261028-0001"
        return order

    with patch.object(svc._repo, "next_order_number", new_callable=AsyncMock) as non:
        non.return_value = "MC-20261028-0001"
        with patch.object(svc._repo, "create_order", new_callable=AsyncMock) as co:
            co.side_effect = _create_side_effect
            with patch.object(svc._repo, "add_item", new_callable=AsyncMock):
                with patch.object(svc._repo, "record_event", new_callable=AsyncMock):
                    result = await svc.create_order(
                        customer_name="Test Buyer",
                        customer_phone="+923001234567",
                        fulfillment_method="DELIVERY",
                        payment_method="COD",
                        items=[
                            {
                                "variant_id": uuid.uuid4(),
                                "sku": "SKU1",
                                "product_title": "Test",
                                "variant_name": "Red",
                                "quantity": 2,
                                "unit_price_minor": 150000,
                                "line_total_minor": 300000,
                            }
                        ],
                        subtotal_minor=300000,
                        total_minor=300000,
                        checkout_idempotency_key=str(uuid.uuid4()),
                        actor_id=uuid.uuid4(),
                    )
    assert result["number"] == "MC-20261028-0001"
    assert result["state"] == "PENDING_CONFIRMATION"


async def test_transition_valid_state_succeeds() -> None:
    from modest_chic_backend.modules.orders.enums import OrderState
    from modest_chic_backend.modules.orders.service import OrderService

    mock_session = AsyncMock()
    svc = OrderService(mock_session)
    order = MagicMock()
    order.state = OrderState.PENDING_CONFIRMATION
    order.id = uuid.uuid4()

    with patch.object(svc._repo, "get_order", new_callable=AsyncMock) as go:
        go.return_value = order
        with patch.object(svc._repo, "record_event", new_callable=AsyncMock):
            result = await svc.transition(
                order_id=order.id,
                to_state=OrderState.CONFIRMED,
                event_type="order.confirmed",
                actor_type="staff",
                actor_id=uuid.uuid4(),
            )
    assert result["state"] == "CONFIRMED"


async def test_transition_invalid_state_rejected() -> None:
    from modest_chic_backend.modules.orders.enums import OrderState
    from modest_chic_backend.modules.orders.service import OrderService

    mock_session = AsyncMock()
    svc = OrderService(mock_session)
    order = MagicMock()
    order.state = OrderState.COMPLETED
    order.id = uuid.uuid4()

    with patch.object(svc._repo, "get_order", new_callable=AsyncMock) as go:
        go.return_value = order
        with pytest.raises(ValueError, match="transition"):
            await svc.transition(
                order_id=order.id,
                to_state=OrderState.CONFIRMED,
                event_type="order.confirmed",
                actor_type="staff",
                actor_id=uuid.uuid4(),
            )

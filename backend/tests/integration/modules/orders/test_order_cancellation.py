"""PostgreSQL coverage for replay-safe cancellation before external fulfillment."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.auth.models import StaffUser
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.models import Product, ProductVariant
from modest_chic_backend.modules.coupons.enums import CouponRedemptionStatus, CouponType
from modest_chic_backend.modules.coupons.models import Coupon, CouponRedemption
from modest_chic_backend.modules.fulfillment.models import Shipment, ShipmentEvent, ShipmentItem
from modest_chic_backend.modules.inventory.enums import MovementReason, ReservationStatus
from modest_chic_backend.modules.inventory.models import (
    InventoryBalance,
    InventoryLocation,
    InventoryMovement,
    InventoryReservation,
)
from modest_chic_backend.modules.orders.admin_service import OrderAdminService
from modest_chic_backend.modules.orders.enums import OrderState
from modest_chic_backend.modules.orders.models import Order, OrderEvent, OrderItem
from modest_chic_backend.modules.orders.service import OrderService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_cancellation_releases_stock_coupon_and_packed_shipment_once() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    suffix = uuid.uuid4().hex
    idempotency_key = "cancel-order-" + suffix
    try:
        async with database.session() as session:
            async with session.begin():
                actor = StaffUser(email=f"cancel-{suffix}@test.local", display_name="Test")
                product = Product(
                    slug=f"cancel-{suffix}",
                    title="Cancellation test product",
                    status=ProductStatus.PUBLISHED,
                )
                location = InventoryLocation(key=f"cancel-{suffix}", name="Test")
                coupon = Coupon(
                    code=f"CANCEL{suffix[:12]}",
                    type=CouponType.FIXED,
                    value_minor=100,
                )
                session.add_all([actor, product, location, coupon])
                await session.flush()
                variant = ProductVariant(
                    product_id=product.id,
                    sku=f"CANCEL-{suffix}",
                    color_name="Rose",
                    price_minor=1000,
                    is_active=True,
                )
                session.add(variant)
                await session.flush()
                balance = InventoryBalance(
                    variant_id=variant.id,
                    location_id=location.id,
                    on_hand=3,
                    reserved=1,
                )
                session.add(balance)
                await session.flush()
                order_data = await OrderService(session).create_order(
                    customer_name="Cancellation Buyer",
                    customer_phone="03000000000",
                    fulfillment_method="DELIVERY",
                    payment_method="COD",
                    items=[
                        {
                            "variant_id": str(variant.id),
                            "sku": variant.sku,
                            "product_title": product.title,
                            "variant_name": variant.color_name,
                            "quantity": 1,
                            "unit_price_minor": 1000,
                            "line_total_minor": 1000,
                        }
                    ],
                    subtotal_minor=1000,
                    total_minor=1000,
                    checkout_idempotency_key="cancel-checkout-" + suffix,
                    actor_id=actor.id,
                )
                order_id = uuid.UUID(order_data["id"])
                order = await session.get(Order, order_id)
                assert order is not None
                order.state = OrderState.CONFIRMED
                order.confirmed_at = datetime.now(UTC)
                item = await session.scalar(select(OrderItem).where(OrderItem.order_id == order_id))
                assert item is not None
                session.add_all(
                    [
                        InventoryReservation(
                            balance_id=balance.id,
                            order_item_id=item.id,
                            quantity=1,
                            status=ReservationStatus.ACTIVE,
                            expires_at=datetime.now(UTC) + timedelta(days=1),
                        ),
                        CouponRedemption(
                            coupon_id=coupon.id,
                            order_id=order_id,
                            status=CouponRedemptionStatus.CONSUMED,
                            discount_minor=100,
                            idempotency_key="cancel-redemption-" + suffix,
                        ),
                    ]
                )
                shipment = Shipment(
                    order_id=order_id,
                    status="PACKED",
                    idempotency_key="cancel-shipment-" + suffix,
                    merchant_reference="cancel-" + suffix[:12],
                )
                session.add(shipment)
                await session.flush()
                session.add(
                    ShipmentItem(
                        shipment_id=shipment.id,
                        order_item_id=item.id,
                        quantity=1,
                    )
                )

                service = OrderAdminService(session)
                result = await service.cancel_order(
                    order_id, actor.id, idempotency_key, "Buyer requested cancellation"
                )
                replay = await service.cancel_order(
                    order_id, actor.id, idempotency_key, "Buyer requested cancellation"
                )
                assert result["state"] == OrderState.CANCELLED.value
                assert replay == result
                assert balance.on_hand == 3
                assert balance.reserved == 0
                assert order.state == OrderState.CANCELLED
                assert shipment.status == "CANCELLED"

                redemption = await session.scalar(
                    select(CouponRedemption).where(CouponRedemption.order_id == order_id)
                )
                assert redemption is not None
                assert redemption.status == CouponRedemptionStatus.RELEASED
                movement = await session.scalar(
                    select(InventoryMovement).where(
                        InventoryMovement.order_id == order_id,
                        InventoryMovement.reason == MovementReason.RELEASE,
                    )
                )
                assert movement is not None
                assert movement.actor_id == actor.id
                event_count = await session.scalar(
                    select(func.count())
                    .select_from(OrderEvent)
                    .where(OrderEvent.idempotency_key == idempotency_key)
                )
                assert event_count == 1
                shipment_event = await session.scalar(
                    select(ShipmentEvent).where(
                        ShipmentEvent.shipment_id == shipment.id,
                        ShipmentEvent.event_type == "CANCELLED",
                    )
                )
                assert shipment_event is not None

                with pytest.raises(ApplicationError) as changed_replay:
                    await service.cancel_order(
                        order_id, actor.id, idempotency_key, "Changed reason"
                    )
                assert changed_replay.value.code == "ORDER_COMMAND_REPLAY_CONFLICT"

                order.state = OrderState.PROCESSING
                shipment.status = "HANDED_OFF"
                with pytest.raises(ApplicationError) as after_handoff:
                    await service.cancel_order(
                        order_id,
                        actor.id,
                        "cancel-after-handoff-" + suffix,
                        "Buyer requested cancellation",
                    )
                assert after_handoff.value.code == "SHIPMENT_REQUIRES_RESOLUTION"
                assert balance.reserved == 0
                await session.rollback()
    finally:
        await database.dispose()

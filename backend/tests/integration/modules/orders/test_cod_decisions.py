"""COD confirmation keeps stock; decline releases it exactly once."""

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
from modest_chic_backend.modules.inventory.enums import MovementReason, ReservationStatus
from modest_chic_backend.modules.inventory.models import (
    InventoryBalance,
    InventoryLocation,
    InventoryMovement,
    InventoryReservation,
)
from modest_chic_backend.modules.inventory.service import InventoryService
from modest_chic_backend.modules.orders.cod_service import CodConfirmationService
from modest_chic_backend.modules.orders.models import OrderEvent, OrderItem
from modest_chic_backend.modules.orders.service import OrderService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_cod_confirm_and_decline_preserve_reservation_invariants() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    suffix = uuid.uuid4().hex
    try:
        async with database.session() as session:
            async with session.begin():
                actor = StaffUser(email=f"cod-{suffix}@test.local", display_name="Test")
                product = Product(
                    slug=f"cod-{suffix}", title="Test scarf", status=ProductStatus.PUBLISHED
                )
                location = InventoryLocation(key=f"cod-{suffix}", name="Test")
                session.add_all([actor, product, location])
                await session.flush()
                variant = ProductVariant(
                    product_id=product.id,
                    sku=f"COD-{suffix}",
                    color_name="Rose",
                    price_minor=100000,
                    is_active=True,
                )
                session.add(variant)
                await session.flush()
                balance = InventoryBalance(
                    variant_id=variant.id,
                    location_id=location.id,
                    on_hand=3,
                    reserved=0,
                )
                session.add(balance)
                await session.flush()
                orders = OrderService(session)
                inventory = InventoryService(session)
                cod = CodConfirmationService(session)

                async def make_reserved_order() -> tuple[uuid.UUID, InventoryReservation]:
                    created = await orders.create_order(
                        customer_name="Buyer",
                        customer_phone="03001234567",
                        fulfillment_method="DELIVERY",
                        payment_method="COD",
                        items=[
                            {
                                "variant_id": str(variant.id),
                                "sku": variant.sku,
                                "product_title": product.title,
                                "variant_name": "Rose",
                                "quantity": 1,
                                "unit_price_minor": 100000,
                                "line_total_minor": 100000,
                            }
                        ],
                        subtotal_minor=100000,
                        total_minor=100000,
                        checkout_idempotency_key=f"cod-{uuid.uuid4().hex}",
                    )
                    order_id = uuid.UUID(created["id"])
                    item = await session.scalar(
                        select(OrderItem).where(OrderItem.order_id == order_id)
                    )
                    assert item is not None
                    await inventory.reserve(
                        balance.id,
                        item.id,
                        1,
                        datetime.now(UTC) + timedelta(hours=1),
                        order_id=order_id,
                    )
                    reservation = await session.scalar(
                        select(InventoryReservation).where(
                            InventoryReservation.order_item_id == item.id
                        )
                    )
                    assert reservation is not None
                    return order_id, reservation

                confirmed_id, confirmed_reservation = await make_reserved_order()
                contact_key = "cod-contact-" + uuid.uuid4().hex
                first_attempt = await cod.contact_attempt(
                    confirmed_id, actor.id, "PHONE", "FOLLOW_UP", "Called buyer", contact_key
                )
                assert (
                    await cod.contact_attempt(
                        confirmed_id, actor.id, "PHONE", "FOLLOW_UP", "Called buyer", contact_key
                    )
                    == first_attempt
                )
                with pytest.raises(ApplicationError) as changed_contact:
                    await cod.contact_attempt(
                        confirmed_id, actor.id, "PHONE", "NO_ANSWER", "Called buyer", contact_key
                    )
                assert changed_contact.value.code == "CONTACT_ATTEMPT_REPLAY_CONFLICT"
                contact_count = await session.scalar(
                    select(func.count())
                    .select_from(OrderEvent)
                    .where(OrderEvent.idempotency_key == contact_key)
                )
                assert contact_count == 1
                confirmed = await cod.decide(
                    confirmed_id, actor.id, True, "PHONE", "Buyer confirmed"
                )
                assert confirmed["state"] == "CONFIRMED"
                assert confirmed_reservation.status == ReservationStatus.ACTIVE
                confirmed_reservation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
                assert await inventory.expire_stale() == 0
                assert balance.reserved == 1

                declined_id, declined_reservation = await make_reserved_order()
                declined = await cod.decide(declined_id, actor.id, False, "PHONE", "Buyer declined")
                assert declined["state"] == "CANCELLED"
                assert declined_reservation.status == ReservationStatus.RELEASED
                assert balance.reserved == 1
                movement = await session.scalar(
                    select(InventoryMovement).where(
                        InventoryMovement.order_id == declined_id,
                        InventoryMovement.reason == MovementReason.RELEASE,
                    )
                )
                assert movement is not None
                with pytest.raises(ApplicationError) as duplicate:
                    await cod.decide(declined_id, actor.id, False, "PHONE", "Buyer declined")
                assert duplicate.value.code == "ORDER_NOT_PENDING"
                await session.rollback()
    finally:
        await database.dispose()

"""A real PostgreSQL transaction proves quote, order, reservation and retry replay."""

import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.analytics.service import AnalyticsService
from modest_chic_backend.modules.auth.models import StaffUser
from modest_chic_backend.modules.cart.models import Cart, CartItem
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.models import Product, ProductVariant
from modest_chic_backend.modules.catalog.schemas import (
    CategoryCreate,
    CollectionCreate,
    CollectionProductsUpdate,
    ProductCategoriesUpdate,
)
from modest_chic_backend.modules.catalog.service import CatalogService
from modest_chic_backend.modules.checkout.service import CheckoutService
from modest_chic_backend.modules.coupons.enums import CouponRedemptionStatus, CouponType
from modest_chic_backend.modules.coupons.models import Coupon, CouponRedemption
from modest_chic_backend.modules.customers.models import Customer
from modest_chic_backend.modules.inventory.enums import MovementReason, ReservationStatus
from modest_chic_backend.modules.inventory.models import (
    InventoryBalance,
    InventoryLocation,
    InventoryMovement,
    InventoryReservation,
)
from modest_chic_backend.modules.inventory.service import InventoryService
from modest_chic_backend.modules.orders.admin_service import OrderAdminService
from modest_chic_backend.modules.orders.cod_service import CodConfirmationService
from modest_chic_backend.modules.orders.enums import OrderSource, OrderState
from modest_chic_backend.modules.orders.manual_service import ManualOrderService
from modest_chic_backend.modules.orders.models import Order, OrderItem, OrderPolicyAcceptance
from modest_chic_backend.modules.payments.models import Payment
from modest_chic_backend.modules.policies.models import PolicyVersion
from modest_chic_backend.modules.settings.models import StoreSetting

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_cod_checkout_is_atomic_and_replays_exact_order() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    token = "integration-guest-" + uuid.uuid4().hex
    checkout_id = "checkout-" + uuid.uuid4().hex
    try:
        async with database.session() as session:
            async with session.begin():
                actor = StaffUser(email=f"checkout-{uuid.uuid4()}@test.local", display_name="Test")
                product = Product(
                    slug=f"test-{uuid.uuid4().hex}",
                    title="Test scarf",
                    status=ProductStatus.PUBLISHED,
                )
                location = InventoryLocation(key=f"test-{uuid.uuid4().hex}", name="Test")
                session.add_all([actor, product, location])
                await session.flush()
                variant = ProductVariant(
                    product_id=product.id,
                    sku=f"SKU-{uuid.uuid4().hex}",
                    color_name="Rose",
                    price_minor=100000,
                    is_active=True,
                )
                policy = PolicyVersion(
                    type="checkout_bundle",
                    version=9000000,
                    effective_from=datetime.now(UTC) - timedelta(days=1),
                    content={"terms": "test"},
                    approved_by=actor.id,
                )
                shipping_policy = PolicyVersion(
                    type="shipping",
                    version=9000000,
                    effective_from=datetime.now(UTC) - timedelta(days=1),
                    content={"delivery": "test"},
                    approved_by=actor.id,
                )
                returns_policy = PolicyVersion(
                    type="returns",
                    version=9000000,
                    effective_from=datetime.now(UTC) - timedelta(days=1),
                    content={"returns": "test"},
                    approved_by=actor.id,
                )
                cart = Cart(
                    guest_token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                )
                session.add_all([variant, policy, shipping_policy, returns_policy, cart])
                await session.flush()
                balance = InventoryBalance(
                    variant_id=variant.id, location_id=location.id, on_hand=3, reserved=0
                )
                item = CartItem(cart_id=cart.id, variant_id=variant.id, quantity=2)
                session.add_all([balance, item])
                for key, value in (
                    ("checkout.guest_allowed", True),
                    ("checkout.cod_allowed", True),
                    (
                        "fulfillment.availability",
                        {"delivery": True, "delivery_cities": ["Karachi"]},
                    ),
                    ("checkout.delivery_fee_minor", 25000),
                ):
                    session.add(StoreSetting(key=key, value=value, is_secret=False, version=1))
                coupon = Coupon(
                    code="CHECKOUT10",
                    type=CouponType.PERCENT,
                    value_minor=10,
                    per_customer_limit=1,
                    created_by=actor.id,
                )
                session.add(coupon)
                await session.flush()

                service = CheckoutService(session, b"k" * 32)
                quote = await service.quote(
                    token,
                    coupon_code="CHECKOUT10",
                    fulfillment_method="DELIVERY",
                    city="Karachi",
                )
                assert quote["discount_minor"] == 20000
                assert quote["total_minor"] == 205000
                request = dict(
                    cart_token=token,
                    checkout_id=checkout_id,
                    customer_name="Buyer",
                    customer_phone="03001234567",
                    fulfillment_method="DELIVERY",
                    payment_method="COD",
                    cart_version=quote["cart_version"],
                    accepted_total_minor=quote["total_minor"],
                    policy_version_ids=quote["policy_version_ids"],
                    accepted_policy=True,
                    coupon_code="CHECKOUT10",
                    address_line1="Street 1",
                    address_city="Karachi",
                )
                first = await service.place_order(**request)
                replay = await service.place_order(**request)
                assert replay == first
                assert first["access_token"].startswith("mc_ord_")
                assert balance.reserved == 2
                order_items = (
                    (
                        await session.execute(
                            select(OrderItem).where(
                                OrderItem.order_id == uuid.UUID(first["order_id"])
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(order_items) == 1
                assert order_items[0].line_total_minor == 200000
                assert order_items[0].discount_allocated_minor == 20000
                order = await session.get(Order, uuid.UUID(first["order_id"]))
                assert order is not None and order.discount_minor == 20000
                accepted_policies = (
                    await session.scalars(
                        select(OrderPolicyAcceptance).where(
                            OrderPolicyAcceptance.order_id == order.id
                        )
                    )
                ).all()
                assert {
                    acceptance.policy_type: str(acceptance.policy_version_id)
                    for acceptance in accepted_policies
                } == quote["policy_version_ids"]
                session.add(
                    PolicyVersion(
                        type="shipping",
                        version=9000001,
                        effective_from=datetime.now(UTC),
                        content={"delivery": "replacement terms"},
                        approved_by=actor.id,
                    )
                )
                await session.flush()
                persisted_shipping_acceptance = next(
                    entry for entry in accepted_policies if entry.policy_type == "shipping"
                )
                assert (
                    str(persisted_shipping_acceptance.policy_version_id)
                    == quote["policy_version_ids"]["shipping"]
                )
                payments = (
                    (
                        await session.execute(
                            select(Payment).where(Payment.order_id == uuid.UUID(first["order_id"]))
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(payments) == 1
                assert payments[0].amount_minor == 205000
                redemption = await session.scalar(
                    select(CouponRedemption).where(CouponRedemption.order_id == order.id)
                )
                assert redemption is not None
                assert redemption.status == CouponRedemptionStatus.RESERVED
                reservation = await session.scalar(
                    select(InventoryReservation).where(
                        InventoryReservation.order_item_id == order_items[0].id
                    )
                )
                assert reservation is not None
                reservation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
                assert order.customer_id is not None
                profile = await session.get(Customer, order.customer_id)
                assert profile is not None
                assert profile.normalized_phone == "+923001234567"
                assert profile.name == "Buyer"
                order.state = OrderState.CONFIRMED
                assert await InventoryService(session).expire_stale() == 0
                assert reservation.status == ReservationStatus.ACTIVE
                order.state = OrderState.PENDING_CONFIRMATION
                await InventoryService(session).release(reservation.id)
                release_movement = await session.scalar(
                    select(InventoryMovement).where(
                        InventoryMovement.reason == MovementReason.RELEASE,
                        InventoryMovement.variant_id == variant.id,
                    )
                )
                assert release_movement is not None
                assert release_movement.order_id == uuid.UUID(first["order_id"])
                manual_key = "staff-sale-" + uuid.uuid4().hex
                manual_service = ManualOrderService(session, service)
                manual_request = {
                    "idempotency_key": manual_key,
                    "source": "SOCIAL",
                    "customer_name": "Buyer",
                    "customer_phone": "03001234567",
                    "items": [{"variant_id": str(variant.id), "quantity": 1}],
                    "fulfillment_method": "DELIVERY",
                    "city": "Karachi",
                    "address_line1": "Street 2",
                    "attribution_source": "Instagram",
                    "attribution_campaign": "October launch",
                    "attribution_creator_code": "CREATOR7",
                    "actor_id": actor.id,
                }
                manual = await manual_service.create(**manual_request)
                manual_replay = await manual_service.create(**manual_request)
                assert manual_replay["order_id"] == manual["order_id"]
                assert manual_replay["replayed"] is True
                manual_order = await session.get(Order, uuid.UUID(manual["order_id"]))
                assert manual_order is not None
                assert manual_order.source.value == "SOCIAL"
                assert manual_order.customer_id == order.customer_id
                assert manual_order.attribution_source == "Instagram"
                assert manual_order.attribution_campaign == "October launch"
                assert manual_order.attribution_creator_code == "CREATOR7"
                assert manual_order.total_minor == 125000
                manual_policy_acceptances = (
                    await session.scalars(
                        select(OrderPolicyAcceptance).where(
                            OrderPolicyAcceptance.order_id == manual_order.id
                        )
                    )
                ).all()
                assert {entry.policy_type for entry in manual_policy_acceptances} == {
                    "checkout_bundle",
                    "shipping",
                    "returns",
                }
                order_admin = OrderAdminService(session)
                packing_count_before = (
                    await AnalyticsService(session).dashboard_counts({"fulfillment.pack"})
                )["queues"]["packing"]
                results = await order_admin.search(
                    query="Buyer", source=OrderSource.SOCIAL, limit=10
                )
                assert [row["id"] for row in results] == [manual["order_id"]]
                detail = await order_admin.detail(
                    uuid.UUID(manual["order_id"]),
                    include_customer_details=True,
                    include_payments=True,
                    include_refunds=True,
                )
                assert detail is not None
                assert detail["items"][0]["sku"] == variant.sku
                assert detail["payments"][0]["status"] == "PENDING"
                assert detail["events"]
                manual_order_id = uuid.UUID(manual["order_id"])
                manual_item_id = uuid.UUID(detail["items"][0]["id"])
                pending_reservation = await session.scalar(
                    select(InventoryReservation).where(
                        InventoryReservation.order_item_id == manual_item_id,
                        InventoryReservation.status == ReservationStatus.ACTIVE,
                    )
                )
                assert pending_reservation is not None
                pending_balance_id = pending_reservation.balance_id
                await InventoryService(session).release(pending_reservation.id, actor.id)
                cod_queue = await CodConfirmationService(session).pending()
                pending_cod_order = next(
                    row for row in cod_queue["items"] if row["id"] == manual["order_id"]
                )
                assert pending_cod_order["stock_reservation_exception"] is True
                with pytest.raises(ApplicationError) as unavailable_cod_stock:
                    await CodConfirmationService(session).decide(
                        manual_order_id, actor.id, True, "PHONE", "Buyer confirmed order"
                    )
                assert unavailable_cod_stock.value.code == "RESERVATION_UNAVAILABLE"
                pending_exception_orders = await order_admin.search(
                    stock_exception_only=True, limit=100
                )
                assert any(row["id"] == manual["order_id"] for row in pending_exception_orders)
                pending_balance = await session.get(InventoryBalance, pending_balance_id)
                assert pending_balance is not None
                await InventoryService(session).reserve(
                    pending_balance.id,
                    manual_item_id,
                    detail["items"][0]["quantity"],
                    order_id=manual_order_id,
                )
                confirmed = await CodConfirmationService(session).decide(
                    manual_order_id, actor.id, True, "PHONE", "Buyer confirmed order"
                )
                assert confirmed["state"] == OrderState.CONFIRMED.value
                confirmed_reservation = await session.scalar(
                    select(InventoryReservation).where(
                        InventoryReservation.order_item_id == manual_item_id,
                        InventoryReservation.status == ReservationStatus.ACTIVE,
                    )
                )
                assert confirmed_reservation is not None
                confirmed_balance_id = confirmed_reservation.balance_id
                await InventoryService(session).release(confirmed_reservation.id, actor.id)
                exception_detail = await order_admin.detail(
                    manual_order_id,
                    include_customer_details=True,
                    include_payments=True,
                    include_refunds=True,
                )
                assert exception_detail is not None
                assert exception_detail["stock_reservation_exception"] is True
                with pytest.raises(ApplicationError) as unavailable_processing_stock:
                    await order_admin.start_processing(
                        manual_order_id, actor.id, "processing-no-stock-" + uuid.uuid4().hex
                    )
                assert unavailable_processing_stock.value.code == "RESERVATION_UNAVAILABLE"
                confirmed_balance = await session.get(InventoryBalance, confirmed_balance_id)
                assert confirmed_balance is not None
                await InventoryService(session).reserve(
                    confirmed_balance.id,
                    manual_item_id,
                    detail["items"][0]["quantity"],
                    order_id=manual_order_id,
                )
                command_key = "processing-" + uuid.uuid4().hex
                processing = await order_admin.start_processing(
                    manual_order_id, actor.id, command_key
                )
                replayed_processing = await order_admin.start_processing(
                    manual_order_id, actor.id, command_key
                )
                assert processing["state"] == OrderState.PROCESSING.value
                assert replayed_processing["state"] == OrderState.PROCESSING.value
                packing_dashboard = await AnalyticsService(session).dashboard_counts(
                    {"fulfillment.pack"}
                )
                packing_orders = await order_admin.search(packing_only=True, limit=100)
                assert packing_dashboard["queues"]["packing"] == packing_count_before + 1
                assert packing_dashboard["queues"]["packing"] == len(packing_orders)
                assert any(row["id"] == manual["order_id"] for row in packing_orders)
                manual_reservation = await session.scalar(
                    select(InventoryReservation).where(
                        InventoryReservation.order_item_id == manual_item_id,
                        InventoryReservation.status == ReservationStatus.ACTIVE,
                    )
                )
                assert manual_reservation is not None
                reservation_balance_id = manual_reservation.balance_id
                await InventoryService(session).release(manual_reservation.id, actor.id)
                stock_exception_orders = await order_admin.search(
                    stock_exception_only=True, limit=100
                )
                stock_exception_dashboard = await AnalyticsService(session).dashboard_counts(
                    {"order.read"}
                )
                assert any(row["id"] == manual["order_id"] for row in stock_exception_orders)
                assert stock_exception_dashboard["queues"]["stock_reservation_exceptions"] == len(
                    stock_exception_orders
                )
                stock_balance = await session.get(InventoryBalance, reservation_balance_id)
                assert stock_balance is not None
                await InventoryService(session).reserve(
                    stock_balance.id,
                    manual_item_id,
                    detail["items"][0]["quantity"],
                    order_id=manual_order_id,
                )
                with pytest.raises(ApplicationError):
                    await order_admin.start_processing(
                        manual_order_id, actor.id, "different-" + uuid.uuid4().hex
                    )
                shipment_key = "shipment-pack-" + uuid.uuid4().hex
                allocation = [{"order_item_id": detail["items"][0]["id"], "quantity": 1}]
                shipment = await order_admin.pack_delivery(
                    manual_order_id, actor.id, shipment_key, allocation
                )
                shipment_replay = await order_admin.pack_delivery(
                    manual_order_id, actor.id, shipment_key, allocation
                )
                assert shipment["status"] == "PACKED"
                assert shipment["merchant_reference"].startswith(manual_order.number)
                assert shipment_replay == shipment
                packed_queue = await order_admin.search(packing_only=True, limit=100)
                assert not any(row["id"] == manual["order_id"] for row in packed_queue)
                with pytest.raises(ApplicationError) as changed_shipment_replay:
                    await order_admin.pack_delivery(
                        manual_order_id,
                        actor.id,
                        shipment_key,
                        [{"order_item_id": detail["items"][0]["id"], "quantity": 2}],
                    )
                assert changed_shipment_replay.value.code == "SHIPMENT_REPLAY_CONFLICT"
                dashboard = await AnalyticsService(session).dashboard_counts()
                assert dashboard["order_states"]["PROCESSING"] >= 1
                assert dashboard["as_of"]
                catalog = CatalogService(session)
                category = await catalog.create_category(
                    CategoryCreate(slug="category-" + uuid.uuid4().hex, name="Test range"),
                    actor.id,
                )
                catalog_product = await session.get(Product, variant.product_id)
                assert catalog_product is not None
                assert await catalog.set_product_categories(
                    variant.product_id,
                    ProductCategoriesUpdate(
                        expected_updated_at=catalog_product.updated_at,
                        category_ids=[category.id],
                    ),
                    actor.id,
                )
                assert await catalog.get_product_category_ids(variant.product_id) == [category.id]
                collection = await catalog.create_collection(
                    CollectionCreate(slug="collection-" + uuid.uuid4().hex, name="Test edit"),
                    actor.id,
                )
                assert await catalog.set_collection_products(
                    collection.id,
                    CollectionProductsUpdate(
                        expected_updated_at=collection.updated_at,
                        product_ids=[variant.product_id],
                    ),
                    actor.id,
                )
                assert await catalog.get_collection_product_ids(collection.id) == [
                    variant.product_id
                ]
                packed_detail = await order_admin.detail(
                    manual_order_id,
                    include_customer_details=True,
                    include_payments=True,
                    include_refunds=True,
                )
                assert packed_detail is not None
                assert packed_detail["shipments"][0]["items"][0]["quantity"] == 1
                assert balance.reserved == 1
                with pytest.raises(ApplicationError) as overpacked:
                    await order_admin.pack_delivery(
                        manual_order_id,
                        actor.id,
                        "shipment-pack-overflow-" + uuid.uuid4().hex,
                        allocation,
                    )
                assert overpacked.value.code == "SHIPMENT_QUANTITY_EXCEEDED"
                handoff_key = "delivery-handoff-" + uuid.uuid4().hex
                handed_off = await order_admin.handoff_delivery(
                    manual_order_id, actor.id, handoff_key
                )
                handoff_replay = await order_admin.handoff_delivery(
                    manual_order_id, actor.id, handoff_key
                )
                assert handed_off["state"] == OrderState.FULFILLED.value
                assert handoff_replay == handed_off
                assert balance.reserved == 0
                assert balance.on_hand == 2
                consumed_movement = await session.scalar(
                    select(InventoryMovement).where(
                        InventoryMovement.order_id == manual_order_id,
                        InventoryMovement.reason == MovementReason.CONSUME,
                    )
                )
                assert consumed_movement is not None
                assert consumed_movement.actor_id == actor.id
                completed_detail = await order_admin.detail(
                    manual_order_id,
                    include_customer_details=True,
                    include_payments=True,
                    include_refunds=True,
                )
                assert completed_detail is not None
                assert completed_detail["shipments"][0]["status"] == "HANDED_OFF"
                with pytest.raises(ApplicationError) as changed:
                    await service.place_order(**{**request, "customer_name": "Other Buyer"})
                assert changed.value.code == "CHECKOUT_REPLAY_CONFLICT"
                changed_policy_ids = {
                    **request,
                    "policy_version_ids": {
                        **quote["policy_version_ids"],
                        "shipping": str(uuid.uuid4()),
                    },
                }
                with pytest.raises(ApplicationError) as changed_terms:
                    await service.place_order(**changed_policy_ids)
                assert changed_terms.value.code == "CHECKOUT_REPLAY_CONFLICT"
                await session.rollback()
    finally:
        await database.dispose()

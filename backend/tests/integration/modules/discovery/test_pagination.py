"""Catalog pagination follows the displayed creation-time order."""

import json
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select

from modest_chic_backend.api.v1.discovery import (
    _after_cursor,
    _apply_product_filters,
    _base_product_query,
    _product_page,
)
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.models import (
    Category,
    Product,
    ProductVariant,
    product_categories,
)
from modest_chic_backend.modules.inventory.models import InventoryBalance, InventoryLocation
from modest_chic_backend.modules.orders.enums import OrderState
from modest_chic_backend.modules.orders.models import Order, OrderItem
from modest_chic_backend.modules.orders.service import OrderService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_cursor_does_not_skip_an_older_product_with_a_larger_id() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    prefix = f"cursor-{uuid.uuid4().hex}"
    try:
        async with database.session() as session:
            async with session.begin():
                now = datetime.now(UTC)
                newer = Product(
                    id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
                    slug=f"{prefix}-newer",
                    title="Newer",
                    status=ProductStatus.PUBLISHED,
                    created_at=now,
                )
                older = Product(
                    id=uuid.UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"),
                    slug=f"{prefix}-older",
                    title="Older",
                    status=ProductStatus.PUBLISHED,
                    created_at=now - timedelta(days=1),
                )
                session.add_all([newer, older])
                await session.flush()
                query = (
                    select(Product)
                    .where(Product.slug.like(f"{prefix}%"))
                    .order_by(Product.created_at.desc(), Product.id.desc())
                )
                page = (await session.execute(query.limit(1))).scalar_one()
                assert page.id == newer.id
                next_query = await _after_cursor(session, query, page.id)
                next_page = (await session.execute(next_query.limit(1))).scalar_one()
                assert next_page.id == older.id
                await session.rollback()
    finally:
        await database.dispose()


async def test_public_filters_price_cursor_and_popularity_sort_are_deterministic() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    suffix = uuid.uuid4().hex
    try:
        async with database.session() as session:
            async with session.begin():
                location = InventoryLocation(key=f"discovery-{suffix}", name="Test")
                first = Product(
                    slug=f"discovery-first-{suffix}",
                    title=f"{suffix} chiffon first",
                    fabric=f"Korean chiffon {suffix}",
                    status=ProductStatus.PUBLISHED,
                )
                second = Product(
                    slug=f"discovery-second-{suffix}",
                    title=f"{suffix} chiffon second",
                    fabric=f"Korean chiffon {suffix}",
                    status=ProductStatus.PUBLISHED,
                )
                hidden = Product(
                    slug=f"discovery-draft-{suffix}",
                    title=f"{suffix} chiffon draft",
                    fabric=f"Korean chiffon {suffix}",
                    status=ProductStatus.DRAFT,
                )
                session.add_all([location, first, second, hidden])
                await session.flush()
                primary_category = Category(
                    slug=f"hijabs-{suffix}",
                    name="Hijabs",
                    status=ProductStatus.PUBLISHED,
                )
                secondary_category = Category(
                    slug=f"occasion-{suffix}",
                    name="Occasion",
                    status=ProductStatus.PUBLISHED,
                )
                session.add_all([primary_category, secondary_category])
                await session.flush()
                await session.execute(
                    insert(product_categories).values(
                        [
                            {
                                "product_id": first.id,
                                "category_id": primary_category.id,
                                "sort_order": 0,
                            },
                            {
                                "product_id": first.id,
                                "category_id": secondary_category.id,
                                "sort_order": 1,
                            },
                            {
                                "product_id": second.id,
                                "category_id": primary_category.id,
                                "sort_order": 0,
                            },
                        ]
                    )
                )
                first_variant = ProductVariant(
                    product_id=first.id,
                    sku=f"DISCOVERY-FIRST-{suffix}",
                    color_name="Dusty Rose",
                    price_minor=1500,
                    is_active=True,
                )
                second_variant = ProductVariant(
                    product_id=second.id,
                    sku=f"DISCOVERY-SECOND-{suffix}",
                    color_name="Rose Quartz",
                    price_minor=1800,
                    is_active=True,
                )
                draft_variant = ProductVariant(
                    product_id=hidden.id,
                    sku=f"DISCOVERY-DRAFT-{suffix}",
                    color_name="Rose",
                    price_minor=1200,
                    is_active=True,
                )
                session.add_all([first_variant, second_variant, draft_variant])
                await session.flush()
                session.add_all(
                    [
                        InventoryBalance(
                            variant_id=first_variant.id,
                            location_id=location.id,
                            on_hand=4,
                            reserved=0,
                        ),
                        InventoryBalance(
                            variant_id=second_variant.id,
                            location_id=location.id,
                            on_hand=2,
                            reserved=0,
                        ),
                    ]
                )
                created = await OrderService(session).create_order(
                    customer_name="Popularity buyer",
                    customer_phone="03000000000",
                    fulfillment_method="DELIVERY",
                    payment_method="COD",
                    items=[
                        {
                            "variant_id": str(first_variant.id),
                            "sku": first_variant.sku,
                            "product_title": first.title,
                            "variant_name": first_variant.color_name,
                            "quantity": 3,
                            "unit_price_minor": 1500,
                            "line_total_minor": 4500,
                        }
                    ],
                    subtotal_minor=4500,
                    total_minor=4500,
                    checkout_idempotency_key=f"discovery-order-{suffix}",
                )
                order = await session.get(Order, uuid.UUID(created["id"]))
                assert order is not None
                order.state = OrderState.FULFILLED
                item = await session.scalar(select(OrderItem).where(OrderItem.order_id == order.id))
                assert item is not None
                item.fulfilled_quantity = 3

                filtered = _apply_product_filters(
                    _base_product_query(),
                    None,
                    None,
                    suffix,
                    suffix,
                    "rose",
                    1300,
                    1900,
                    True,
                    False,
                )
                first_page = await _product_page(session, filtered, "price-low", None, 1)
                first_payload = json.loads(first_page.body)
                assert first_payload["items"][0]["slug"] == first.slug
                assert first_payload["next_cursor"] == str(first.id)
                second_page = await _product_page(
                    session, filtered, "price-low", uuid.UUID(first_payload["next_cursor"]), 1
                )
                second_payload = json.loads(second_page.body)
                assert [row["slug"] for row in second_payload["items"]] == [second.slug]

                popular_filter = _apply_product_filters(
                    _base_product_query(),
                    None,
                    None,
                    suffix,
                    None,
                    None,
                    None,
                    None,
                    False,
                    False,
                )
                popular_page = await _product_page(session, popular_filter, "popular", None, 10)
                popular_payload = json.loads(popular_page.body)
                popular_slugs = [row["slug"] for row in popular_payload["items"]]
                assert popular_slugs.index(first.slug) < popular_slugs.index(second.slug)
                assert hidden.slug not in popular_slugs
                first_public_product = next(
                    row for row in popular_payload["items"] if row["slug"] == first.slug
                )
                assert first_public_product["category"] == primary_category.slug
                assert first_public_product["categories"] == [
                    primary_category.slug,
                    secondary_category.slug,
                ]

                secondary_category_filter = _apply_product_filters(
                    _base_product_query(),
                    secondary_category.slug,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    False,
                    False,
                )
                secondary_category_page = await _product_page(
                    session, secondary_category_filter, "newest", None, 10
                )
                secondary_category_payload = json.loads(secondary_category_page.body)
                assert [row["slug"] for row in secondary_category_payload["items"]] == [first.slug]
                await session.rollback()
    finally:
        await database.dispose()

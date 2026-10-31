"""PostgreSQL coverage for purchase-bound review submission and moderation."""

import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.auth.models import StaffUser
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.models import Product, ProductVariant
from modest_chic_backend.modules.checkout.models import OrderAccessToken
from modest_chic_backend.modules.orders.enums import OrderState
from modest_chic_backend.modules.orders.models import Order, OrderItem
from modest_chic_backend.modules.orders.service import OrderService
from modest_chic_backend.modules.reviews.models import Review
from modest_chic_backend.modules.reviews.service import ReviewService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_verified_purchase_review_requires_moderation_before_publication() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    suffix = uuid.uuid4().hex
    access_token = f"review-access-{suffix}"
    actor_id: uuid.UUID
    order_id: uuid.UUID
    order_item_id: uuid.UUID
    product_slug = f"review-{suffix}"
    try:
        async with database.transaction() as session:
            actor = StaffUser(email=f"review-{suffix}@test.local", display_name="Reviewer")
            product = Product(
                slug=product_slug,
                title="Review test product",
                status=ProductStatus.PUBLISHED,
            )
            session.add_all([actor, product])
            await session.flush()
            variant = ProductVariant(
                product_id=product.id,
                sku=f"REVIEW-{suffix}",
                color_name="Rose",
                price_minor=1000,
                is_active=True,
            )
            session.add(variant)
            await session.flush()
            result = await OrderService(session).create_order(
                customer_name="Review Buyer",
                customer_phone="03000000000",
                fulfillment_method="DELIVERY",
                payment_method="COD",
                items=[
                    {
                        "variant_id": str(variant.id),
                        "sku": variant.sku,
                        "product_title": product.title,
                        "variant_name": "Rose",
                        "quantity": 1,
                        "unit_price_minor": 1000,
                        "line_total_minor": 1000,
                    }
                ],
                subtotal_minor=1000,
                total_minor=1000,
                checkout_idempotency_key=f"review-checkout-{suffix}",
            )
            order_id = uuid.UUID(result["id"])
            order = await session.get(Order, order_id)
            assert order is not None
            order.state = OrderState.FULFILLED
            order_item = await session.scalar(
                select(OrderItem).where(OrderItem.order_id == order_id)
            )
            assert order_item is not None
            order_item_id = order_item.id
            order_item.fulfilled_quantity = order_item.quantity
            session.add(
                OrderAccessToken(
                    order_id=order_id,
                    token_hash=hashlib.sha256(access_token.encode()).hexdigest(),
                    scope="order.read review.create",
                    replay_ciphertext=b"{}",
                    replay_key_version=1,
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                )
            )
            actor_id = actor.id

        async with database.transaction() as session:
            service = ReviewService(session, b"unused-for-lookup")
            access = await session.scalar(
                select(OrderAccessToken).where(
                    OrderAccessToken.token_hash == hashlib.sha256(access_token.encode()).hexdigest()
                )
            )
            assert access is not None
            access.scope = "order.read"
            with pytest.raises(ApplicationError):
                await service.submit_for_order_item(
                    order_id=order_id,
                    order_item_id=order_item_id,
                    access_token=access_token,
                    rating=5,
                    title="Lovely",
                    body="Soft fabric and a good fit.",
                )
            access.scope = "order.read review.create"
            submitted = await service.submit_for_order_item(
                order_id=order_id,
                order_item_id=order_item_id,
                access_token=access_token,
                rating=5,
                title="Lovely",
                body="Soft fabric and a good fit.",
            )
            review_id = uuid.UUID(submitted["id"])
            assert submitted["status"] == "PENDING"
            assert await service.public_page(product_slug) == {
                "product_slug": product_slug,
                "review_count": 0,
                "average_rating": 0.0,
                "items": [],
                "next_cursor": None,
            }
            with pytest.raises(ApplicationError, match="already exists"):
                await service.submit_for_order_item(
                    order_id=order_id,
                    order_item_id=order_item_id,
                    access_token=access_token,
                    rating=4,
                    title=None,
                    body=None,
                )

        async with database.transaction() as session:
            moderated = await ReviewService(session, b"unused-for-lookup").moderate(
                review_id=review_id,
                status="APPROVED",
                reason="Purchase and content verified.",
                actor_id=actor_id,
            )
            assert moderated["status"] == "APPROVED"

        async with database.session() as session:
            public = await ReviewService(session, b"unused-for-lookup").public_page(product_slug)
            assert public["review_count"] == 1
            assert public["average_rating"] == 5.0
            assert public["items"][0]["verified_purchase"] is True
            assert "customer" not in public["items"][0]
            review = await session.get(Review, review_id)
            assert (
                review is not None and review.moderation_reason == "Purchase and content verified."
            )
    finally:
        await database.dispose()

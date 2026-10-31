"""Verified-purchase review submission, moderation, and public summaries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.audit.repository import AuditRepository
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.models import Product, ProductVariant
from modest_chic_backend.modules.checkout.repository import CheckoutRepository
from modest_chic_backend.modules.orders.enums import OrderState
from modest_chic_backend.modules.orders.models import Order, OrderItem
from modest_chic_backend.modules.reviews.models import Review


class ReviewService:
    """Business rules for order-scoped review submission and moderation."""

    def __init__(self, session: AsyncSession, encryption_key: bytes) -> None:
        self._session = session
        self._access = CheckoutRepository(session, encryption_key)
        self._audit = AuditRepository(session)

    async def submit_for_order_item(
        self,
        *,
        order_id: uuid.UUID,
        order_item_id: uuid.UUID,
        access_token: str,
        rating: int,
        title: str | None,
        body: str | None,
    ) -> dict[str, Any]:
        access = await self._access.find_order_access(access_token)
        if access is None or access.order_id != order_id or not access.allows("review.create"):
            raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")

        order = await self._session.scalar(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        if order is None:
            raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
        if order.state not in {OrderState.FULFILLED, OrderState.COMPLETED}:
            raise ApplicationError(
                409, "REVIEW_NOT_ELIGIBLE", "Reviews are available after fulfillment."
            )
        item = await self._session.scalar(
            select(OrderItem)
            .where(OrderItem.id == order_item_id, OrderItem.order_id == order_id)
            .with_for_update()
        )
        if item is None or item.variant_id is None or item.fulfilled_quantity < item.quantity:
            raise ApplicationError(
                409, "REVIEW_NOT_ELIGIBLE", "This purchased item is not eligible for review."
            )
        product_id = await self._session.scalar(
            select(ProductVariant.product_id).where(ProductVariant.id == item.variant_id)
        )
        if product_id is None:
            raise ApplicationError(
                409, "REVIEW_NOT_ELIGIBLE", "This purchased item is no longer reviewable."
            )
        existing = await self._session.scalar(
            select(Review.id).where(Review.order_item_id == order_item_id)
        )
        if existing is not None:
            raise ApplicationError(
                409, "REVIEW_ALREADY_SUBMITTED", "A review already exists for this item."
            )
        review = Review(
            product_id=product_id,
            customer_id=order.customer_id,
            order_item_id=order_item_id,
            rating=rating,
            title=title.strip() if title and title.strip() else None,
            body=body.strip() if body and body.strip() else None,
            status="PENDING",
        )
        self._session.add(review)
        await self._session.flush()
        return self._staff_review(review, product_title=item.product_title)

    async def moderation_queue(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        total_count = int(
            await self._session.scalar(
                select(func.count(Review.id)).where(Review.status == "PENDING")
            )
            or 0
        )
        rows = await self._session.execute(
            select(Review, Product.title, Order.number)
            .join(Product, Product.id == Review.product_id)
            .outerjoin(OrderItem, OrderItem.id == Review.order_item_id)
            .outerjoin(Order, Order.id == OrderItem.order_id)
            .where(Review.status == "PENDING")
            .order_by(Review.created_at, Review.id)
            .limit(limit)
            .offset(offset)
        )
        return {
            "items": [
                {
                    **self._staff_review(review, product_title=product_title),
                    "order_number": order_number,
                }
                for review, product_title, order_number in rows.all()
            ],
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }

    async def moderate(
        self,
        *,
        review_id: uuid.UUID,
        status: str,
        reason: str,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        if status not in {"APPROVED", "REJECTED"}:
            raise ValueError("moderation status must be APPROVED or REJECTED")
        if not reason.strip():
            raise ValueError("moderation reason is required")
        review = await self._session.scalar(
            select(Review).where(Review.id == review_id).with_for_update()
        )
        if review is None:
            raise ApplicationError(404, "REVIEW_NOT_FOUND", "Review not found.")
        if review.status != "PENDING":
            raise ApplicationError(
                409, "REVIEW_ALREADY_MODERATED", "This review has already been moderated."
            )
        review.status = status
        review.moderated_by = actor_id
        review.moderated_at = datetime.now(UTC)
        review.moderation_reason = reason.strip()
        await self._audit.record(
            action=f"review.{status.lower()}",
            entity_type="review",
            actor_id=actor_id,
            entity_id=review.id,
            metadata={"status": status},
        )
        await self._session.flush()
        return self._staff_review(review, product_title="")

    async def public_page(
        self, slug: str, *, after: uuid.UUID | None = None, limit: int = 20
    ) -> dict[str, Any]:
        product = await self._session.scalar(
            select(Product).where(
                Product.slug == slug,
                Product.status == ProductStatus.PUBLISHED,
                Product.variants.any(ProductVariant.is_active),
            )
        )
        if product is None:
            raise ApplicationError(404, "PRODUCT_NOT_FOUND", "Product not found.")

        aggregates = await self._session.execute(
            select(func.count(Review.id), func.avg(Review.rating)).where(
                Review.product_id == product.id, Review.status == "APPROVED"
            )
        )
        review_count, average_rating = aggregates.one()
        stmt = select(Review).where(Review.product_id == product.id, Review.status == "APPROVED")
        if after is not None:
            cursor = await self._session.scalar(
                select(Review).where(
                    Review.id == after,
                    Review.product_id == product.id,
                    Review.status == "APPROVED",
                )
            )
            if cursor is None:
                raise ApplicationError(422, "INVALID_CURSOR", "The review cursor is invalid.")
            stmt = stmt.where(
                or_(
                    Review.created_at < cursor.created_at,
                    and_(Review.created_at == cursor.created_at, Review.id < cursor.id),
                )
            )
        page = list(
            (
                await self._session.scalars(
                    stmt.order_by(Review.created_at.desc(), Review.id.desc()).limit(limit + 1)
                )
            ).all()
        )
        items = page[:limit]
        return {
            "product_slug": slug,
            "review_count": int(review_count or 0),
            "average_rating": round(float(average_rating or 0), 2),
            "items": [self._public_review(review) for review in items],
            "next_cursor": str(items[-1].id) if len(page) > limit and items else None,
        }

    @staticmethod
    def _public_review(review: Review) -> dict[str, Any]:
        return {
            "id": str(review.id),
            "rating": review.rating,
            "title": review.title,
            "body": review.body,
            "verified_purchase": review.order_item_id is not None,
            "created_at": review.created_at.isoformat(),
        }

    @staticmethod
    def _staff_review(review: Review, *, product_title: str) -> dict[str, Any]:
        return {
            "id": str(review.id),
            "product_id": str(review.product_id),
            "product_title": product_title,
            "order_item_id": str(review.order_item_id) if review.order_item_id else None,
            "rating": review.rating,
            "title": review.title,
            "body": review.body,
            "status": review.status,
            "moderation_reason": review.moderation_reason,
            "created_at": review.created_at.isoformat(),
            "moderated_at": review.moderated_at.isoformat() if review.moderated_at else None,
        }

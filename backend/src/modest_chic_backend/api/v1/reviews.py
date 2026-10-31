"""Public product review summaries."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from modest_chic_backend.modules.reviews.service import ReviewService

router = APIRouter(prefix="/catalog/products", tags=["product-reviews"])


@router.get("/{slug}/reviews")
async def list_product_reviews(
    slug: str,
    request: Request,
    after: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    """Return approved reviews and their public aggregate for a published product."""
    key = request.app.state.settings.outbox_encryption_key.get_secret_value().encode()
    async with request.app.state.database.session() as session:
        return await ReviewService(session, key).public_page(slug, after=after, limit=limit)

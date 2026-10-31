"""Staff review moderation routes."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from modest_chic_backend.api.v1.dependencies import require_permission
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.auth.service import StaffIdentity
from modest_chic_backend.modules.reviews.service import ReviewService

router = APIRouter(prefix="/admin/reviews", tags=["admin-reviews"])


class ModerateReviewRequest(BaseModel):
    status: Literal["APPROVED", "REJECTED"]
    reason: str = Field(min_length=3, max_length=2000)


@router.get("")
async def moderation_queue(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("review.moderate"))],
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100000),
) -> dict[str, object]:
    key = request.app.state.settings.outbox_encryption_key.get_secret_value().encode()
    async with request.app.state.database.session() as session:
        return await ReviewService(session, key).moderation_queue(limit=limit, offset=offset)


@router.post("/{review_id}/moderate")
async def moderate_review(
    review_id: UUID,
    payload: ModerateReviewRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("review.moderate"))],
) -> dict[str, object]:
    key = request.app.state.settings.outbox_encryption_key.get_secret_value().encode()
    async with request.app.state.database.transaction() as session:
        try:
            return await ReviewService(session, key).moderate(
                review_id=review_id,
                status=payload.status,
                reason=payload.reason,
                actor_id=identity.user.id,
            )
        except ValueError as error:
            raise ApplicationError(422, "REVIEW_MODERATION_INVALID", str(error)) from error

"""Permissioned COD confirmation queue and decisions."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from modest_chic_backend.api.v1.dependencies import require_permission
from modest_chic_backend.modules.auth.service import StaffIdentity
from modest_chic_backend.modules.orders.cod_service import CodConfirmationService

router = APIRouter(prefix="/admin/orders/cod", tags=["cod-confirmation"])


class ContactAttemptRequest(BaseModel):
    idempotency_key: str = Field(min_length=16, max_length=200)
    channel: str = Field(pattern="^(PHONE|SMS|WHATSAPP)$")
    outcome: str = Field(pattern="^(NO_ANSWER|FOLLOW_UP)$")
    notes: str = Field(min_length=1, max_length=2000)


class DecisionRequest(BaseModel):
    channel: str = Field(pattern="^(PHONE|SMS|WHATSAPP)$")
    notes: str = Field(min_length=1, max_length=2000)


@router.get("/pending")
async def pending_orders(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("order.read"))],
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
) -> dict[str, object]:
    async with request.app.state.database.session() as session:
        return await CodConfirmationService(session).pending(limit=limit, offset=offset)


@router.post("/{order_id}/contact-attempts")
async def contact_attempt(
    order_id: UUID,
    payload: ContactAttemptRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("order.confirm"))],
) -> dict[str, object]:
    async with request.app.state.database.transaction() as session:
        return await CodConfirmationService(session).contact_attempt(
            order_id,
            identity.user.id,
            payload.channel,
            payload.outcome,
            payload.notes,
            payload.idempotency_key,
        )


@router.post("/{order_id}/confirm")
async def confirm_order(
    order_id: UUID,
    payload: DecisionRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("order.confirm"))],
) -> dict[str, object]:
    async with request.app.state.database.transaction() as session:
        return await CodConfirmationService(session).decide(
            order_id, identity.user.id, True, payload.channel, payload.notes
        )


@router.post("/{order_id}/decline")
async def decline_order(
    order_id: UUID,
    payload: DecisionRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("order.confirm"))],
) -> dict[str, object]:
    async with request.app.state.database.transaction() as session:
        return await CodConfirmationService(session).decide(
            order_id, identity.user.id, False, payload.channel, payload.notes
        )

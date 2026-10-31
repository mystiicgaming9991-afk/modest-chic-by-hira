"""Permissioned manual social order intake."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from modest_chic_backend.api.v1.dependencies import require_permission
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.core.settings import Settings
from modest_chic_backend.modules.auth.service import StaffIdentity
from modest_chic_backend.modules.checkout.service import CheckoutService
from modest_chic_backend.modules.orders.manual_service import ManualOrderService

router = APIRouter(prefix="/admin/orders/manual", tags=["manual-orders"])


class ManualOrderItemRequest(BaseModel):
    variant_id: UUID
    quantity: int = Field(gt=0, le=1000)


class CreateManualOrderRequest(BaseModel):
    idempotency_key: str = Field(min_length=16, max_length=200)
    source: Literal["MANUAL", "SOCIAL"] = "MANUAL"
    customer_name: str = Field(min_length=1, max_length=255)
    customer_phone: str = Field(min_length=1, max_length=30)
    customer_email: str | None = Field(default=None, max_length=255)
    items: list[ManualOrderItemRequest] = Field(min_length=1, max_length=50)
    fulfillment_method: Literal["DELIVERY", "PICKUP"]
    city: str = Field(min_length=1, max_length=255)
    address_line1: str | None = Field(default=None, max_length=500)
    address_line2: str | None = Field(default=None, max_length=500)
    address_area: str | None = Field(default=None, max_length=255)
    address_postal_code: str | None = Field(default=None, max_length=20)
    delivery_notes: str | None = Field(default=None, max_length=2000)
    attribution_source: str | None = Field(default=None, max_length=100)
    attribution_campaign: str | None = Field(default=None, max_length=255)
    attribution_creator_code: str | None = Field(default=None, max_length=100)


@router.get("/options")
async def manual_order_options(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("order.create_manual"))],
) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    async with request.app.state.database.session() as session:
        checkout = CheckoutService(
            session, settings.outbox_encryption_key.get_secret_value().encode()
        )
        return await checkout.options(require_guest_checkout=False)


@router.post("", status_code=201)
async def create_manual_order(
    payload: CreateManualOrderRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("order.create_manual"))],
) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    async with request.app.state.database.transaction() as session:
        checkout = CheckoutService(
            session, settings.outbox_encryption_key.get_secret_value().encode()
        )
        try:
            return await ManualOrderService(session, checkout).create(
                **payload.model_dump(exclude={"items"}),
                items=[item.model_dump(mode="json") for item in payload.items],
                actor_id=identity.user.id,
            )
        except ValueError as exc:
            raise ApplicationError(400, "MANUAL_ORDER_ERROR", str(exc)) from exc

"""Guest quote, order placement and private order access routes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.checkout.service import CheckoutService
from modest_chic_backend.modules.customers.auth_service import CustomerAuthService
from modest_chic_backend.modules.orders.customer_view import customer_order_timeline
from modest_chic_backend.modules.orders.models import Order, OrderEvent, OrderItem

router = APIRouter(tags=["guest-checkout"])


class QuoteRequest(BaseModel):
    fulfillment_method: str = Field(pattern="^(DELIVERY|PICKUP)$")
    city: str | None = None
    coupon_code: str | None = Field(default=None, max_length=100)


class PolicyVersionIds(BaseModel):
    """The exact approved policy versions shown and accepted at checkout."""

    checkout_bundle: UUID
    shipping: UUID
    returns: UUID


class PlaceOrderRequest(BaseModel):
    checkout_id: str = Field(min_length=16, max_length=255)
    cart_version: int = Field(ge=1)
    accepted_total_minor: int = Field(ge=0)
    policy_version_ids: PolicyVersionIds
    accepted_policy: bool
    coupon_code: str | None = Field(default=None, max_length=100)
    customer_name: str = Field(min_length=1, max_length=255)
    customer_phone: str = Field(min_length=1, max_length=30)
    customer_email: str | None = None
    fulfillment_method: str = Field(pattern="^(DELIVERY|PICKUP)$")
    payment_method: str = Field(pattern="^COD$")
    address_line1: str | None = None
    address_area: str | None = None
    address_city: str | None = None
    address_postal_code: str | None = None
    delivery_notes: str | None = None


def _guest_token(request: Request) -> str:
    token = request.headers.get("X-Guest-Token", "") or request.cookies.get("mc_guest", "")
    if not token:
        raise ApplicationError(401, "GUEST_REQUIRED", "Guest identity is required.")
    return token


def _service(request: Request, session: object) -> CheckoutService:
    key = request.app.state.settings.outbox_encryption_key.get_secret_value().encode()
    return CheckoutService(session, key)  # type: ignore[arg-type]


@router.get("/checkout/options")
async def options(request: Request) -> JSONResponse:
    async with request.app.state.database.session() as session:
        result = await _service(request, session).options()
    return JSONResponse(content=result)


@router.post("/checkout/quote")
async def quote(payload: QuoteRequest, request: Request) -> JSONResponse:
    async with request.app.state.database.transaction() as session:
        customer_id = await _optional_customer_id(request, session)
        result = await _service(request, session).quote(
            _guest_token(request),
            payload.coupon_code,
            payload.fulfillment_method,
            payload.city,
            customer_id,
        )
    return JSONResponse(content=result)


@router.post("/checkout/orders", status_code=201)
async def place_order(payload: PlaceOrderRequest, request: Request) -> JSONResponse:
    async with request.app.state.database.transaction() as session:
        customer_id = await _optional_customer_id(request, session)
        result = await _service(request, session).place_order(
            cart_token=_guest_token(request),
            checkout_id=payload.checkout_id,
            customer_name=payload.customer_name,
            customer_phone=payload.customer_phone,
            fulfillment_method=payload.fulfillment_method,
            payment_method=payload.payment_method,
            cart_version=payload.cart_version,
            accepted_total_minor=payload.accepted_total_minor,
            policy_version_ids={
                policy_type: str(version_id)
                for policy_type, version_id in payload.policy_version_ids.model_dump().items()
            },
            accepted_policy=payload.accepted_policy,
            coupon_code=payload.coupon_code,
            customer_email=payload.customer_email,
            address_line1=payload.address_line1,
            address_area=payload.address_area,
            address_city=payload.address_city,
            address_postal_code=payload.address_postal_code,
            delivery_notes=payload.delivery_notes,
            customer_id=customer_id,
        )
    return JSONResponse(status_code=201, content=result)


async def _optional_customer_id(request: Request, session: object) -> UUID | None:
    customer_token = request.headers.get("X-Customer-Token")
    if not customer_token:
        return None
    settings = request.app.state.settings
    auth = CustomerAuthService(
        session,  # type: ignore[arg-type]
        settings.csrf_signing_key.get_secret_value(),
        settings.outbox_encryption_key.get_secret_value().encode(),
    )
    _, account = await auth.identity(customer_token)
    return account.customer_id


@router.get("/orders/{order_id}")
async def private_order(
    order_id: UUID, request: Request, x_order_token: str | None = Header(default=None)
) -> JSONResponse:
    if not x_order_token:
        raise ApplicationError(403, "ORDER_ACCESS_REQUIRED", "Order access is required.")
    async with request.app.state.database.session() as session:
        credential = await _service(request, session)._repo.find_order_access(x_order_token)
        if (
            credential is None
            or credential.order_id != order_id
            or not credential.allows("order.read")
        ):
            raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
        order = await session.get(Order, order_id)
        if order is None:
            raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
        result = await session.execute(select(OrderItem).where(OrderItem.order_id == order_id))
        items = result.scalars().all()
        events = await session.scalars(
            select(OrderEvent)
            .where(OrderEvent.order_id == order_id)
            .order_by(OrderEvent.effective_at, OrderEvent.id)
        )
        return JSONResponse(
            content={
                "order_id": str(order.id),
                "order_number": order.number,
                "state": order.state.value,
                "payment_state": order.payment_state.value,
                "total_minor": order.total_minor,
                "shipping_charge_minor": order.shipping_charge_minor,
                "created_at": order.created_at.isoformat()
                if order.created_at
                else datetime.now(UTC).isoformat(),
                "items": [
                    {
                        "id": str(item.id),
                        "product_title": item.product_title,
                        "variant_name": item.variant_name,
                        "quantity": item.quantity,
                        "line_total_minor": item.line_total_minor,
                        "review_eligible": order.state.value in {"FULFILLED", "COMPLETED"}
                        and item.fulfilled_quantity >= item.quantity,
                    }
                    for item in items
                ],
                "events": customer_order_timeline(events.all()),
            }
        )

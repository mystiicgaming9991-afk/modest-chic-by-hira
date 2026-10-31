"""Staff order search and accepted-snapshot inspection."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from modest_chic_backend.api.v1.dependencies import require_permission
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.auth.service import StaffIdentity
from modest_chic_backend.modules.orders.admin_service import OrderAdminService
from modest_chic_backend.modules.orders.enums import OrderSource, OrderState

router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])


class StartProcessingRequest(BaseModel):
    idempotency_key: str = Field(min_length=16, max_length=200)


class ShipmentAllocationRequest(BaseModel):
    order_item_id: UUID
    quantity: int = Field(gt=0, le=1000)


class PackShipmentRequest(BaseModel):
    idempotency_key: str = Field(min_length=16, max_length=200)
    allocations: list[ShipmentAllocationRequest] = Field(min_length=1, max_length=50)


class DeliveryHandoffRequest(BaseModel):
    idempotency_key: str = Field(min_length=16, max_length=200)


class CancelOrderRequest(BaseModel):
    idempotency_key: str = Field(min_length=16, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)


@router.get("")
async def search_orders(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("order.read"))],
    q: Annotated[str | None, Query(max_length=100)] = None,
    state: OrderState | None = None,
    source: OrderSource | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    packing_only: bool = False,
    stock_exception_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
) -> list[dict[str, object]]:
    if from_date and to_date and to_date < from_date:
        raise ApplicationError(
            422, "DATE_RANGE_INVALID", "End date must be on or after start date."
        )
    async with request.app.state.database.session() as session:
        return await OrderAdminService(session).search(
            query=q.strip() if q and q.strip() else None,
            state=state,
            source=source,
            from_date=from_date,
            to_date=to_date,
            packing_only=packing_only,
            stock_exception_only=stock_exception_only,
            limit=limit,
            offset=offset,
        )


@router.get("/{order_id}")
async def get_order_detail(
    order_id: UUID,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("order.read"))],
) -> dict[str, object]:
    permissions = set(identity.permission_keys)
    include_payments = "payment.read" in permissions
    include_refunds = include_payments or bool({"refund.request", "refund.approve"} & permissions)
    include_customer_details = "customer.read" in permissions
    async with request.app.state.database.session() as session:
        result = await OrderAdminService(session).detail(
            order_id,
            include_customer_details=include_customer_details,
            include_payments=include_payments,
            include_refunds=include_refunds,
        )
    if result is None:
        raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
    if not include_payments:
        result["payments"] = []
    if not include_refunds:
        result["refunds"] = []
    if not include_customer_details:
        result["customer_id"] = None
        result["customer_email"] = None
    return result


@router.post("/{order_id}/start-processing")
async def start_processing(
    order_id: UUID,
    payload: StartProcessingRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("fulfillment.pack"))],
) -> dict[str, object]:
    async with request.app.state.database.transaction() as session:
        return await OrderAdminService(session).start_processing(
            order_id, identity.user.id, payload.idempotency_key
        )


@router.post("/{order_id}/shipments/pack")
async def pack_shipment(
    order_id: UUID,
    payload: PackShipmentRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("fulfillment.pack"))],
) -> dict[str, object]:
    async with request.app.state.database.transaction() as session:
        return await OrderAdminService(session).pack_delivery(
            order_id,
            identity.user.id,
            payload.idempotency_key,
            [allocation.model_dump(mode="json") for allocation in payload.allocations],
        )


@router.post("/{order_id}/handoff")
async def handoff_delivery(
    order_id: UUID,
    payload: DeliveryHandoffRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("fulfillment.handoff"))],
) -> dict[str, object]:
    async with request.app.state.database.transaction() as session:
        return await OrderAdminService(session).handoff_delivery(
            order_id, identity.user.id, payload.idempotency_key
        )


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: UUID,
    payload: CancelOrderRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("order.cancel"))],
) -> dict[str, object]:
    async with request.app.state.database.transaction() as session:
        return await OrderAdminService(session).cancel_order(
            order_id, identity.user.id, payload.idempotency_key, payload.reason
        )

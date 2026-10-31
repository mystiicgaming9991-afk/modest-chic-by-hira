"""Inventory administration HTTP routes — stock management and reservations."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from modest_chic_backend.api.v1.dependencies import require_permission
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.auth.service import StaffIdentity
from modest_chic_backend.modules.inventory.enums import MovementReason
from modest_chic_backend.modules.inventory.service import InventoryService

router = APIRouter(prefix="/admin/inventory", tags=["admin-inventory"])


class ReceiveRequest(BaseModel):
    variant_id: str
    location_key: str = "main"
    quantity: int = Field(gt=0)
    idempotency_key: str | None = Field(default=None, max_length=255)


class AdjustRequest(BaseModel):
    variant_id: str
    location_id: str
    delta: int
    reason: MovementReason = MovementReason.ADJUST
    notes: str = Field(min_length=3, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=255)


class LowStockThresholdRequest(BaseModel):
    variant_id: UUID
    location_id: UUID
    threshold: int | None = Field(ge=0)


@router.get("/locations")
async def list_locations(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("inventory.read"))],
) -> list[dict[str, object]]:
    async with request.app.state.database.session() as session:
        return await InventoryService(session).list_locations()


@router.get("/variants")
async def list_variants(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("inventory.read"))],
    limit: int = Query(default=500, ge=1, le=500),
) -> list[dict[str, object]]:
    async with request.app.state.database.session() as session:
        return await InventoryService(session).list_variants(limit=limit)


@router.get("/balances")
async def list_balances(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("inventory.read"))],
    variant_id: str | None = None,
    location_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, object]]:
    from uuid import UUID

    try:
        variant_uuid = UUID(variant_id) if variant_id else None
        location_uuid = UUID(location_id) if location_id else None
    except ValueError as exc:
        raise ApplicationError(400, "INVENTORY_ERROR", "Invalid variant or location ID.") from exc
    async with request.app.state.database.session() as session:
        return await InventoryService(session).list_balances(
            variant_id=variant_uuid, location_id=location_uuid, limit=limit
        )


@router.get("/out-of-stock")
async def list_zero_available_balances(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("inventory.read"))],
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> dict[str, object]:
    async with request.app.state.database.session() as session:
        return await InventoryService(session).zero_available_balances(limit=limit, offset=offset)


@router.get("/low-stock")
async def list_low_stock_balances(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("inventory.read"))],
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> dict[str, object]:
    async with request.app.state.database.session() as session:
        return await InventoryService(session).low_stock_balances(limit=limit, offset=offset)


@router.patch("/thresholds")
async def set_low_stock_threshold(
    payload: LowStockThresholdRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("inventory.thresholds.manage"))],
) -> dict[str, object]:
    async with request.app.state.database.transaction() as session:
        try:
            return await InventoryService(session).set_low_stock_threshold(
                variant_id=payload.variant_id,
                location_id=payload.location_id,
                threshold=payload.threshold,
                actor_id=identity.user.id,
            )
        except ValueError as exc:
            raise ApplicationError(400, "INVENTORY_ERROR", str(exc)) from exc


@router.get("/movements")
async def list_movements(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("inventory.inspect"))],
    variant_id: str | None = None,
    location_id: str | None = None,
    after: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    from uuid import UUID

    try:
        variant_uuid = UUID(variant_id) if variant_id else None
        location_uuid = UUID(location_id) if location_id else None
        after_uuid = UUID(after) if after else None
    except ValueError as exc:
        raise ApplicationError(
            400, "INVENTORY_ERROR", "Invalid inventory cursor or filter."
        ) from exc
    async with request.app.state.database.session() as session:
        return await InventoryService(session).list_movements(
            variant_id=variant_uuid,
            location_id=location_uuid,
            after=after_uuid,
            limit=limit,
        )


# ── Receive ──────────────────────────────────────────────────────


@router.post("/receive")
async def receive_stock(
    payload: ReceiveRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("inventory.receive"))],
) -> dict[str, object]:
    from uuid import UUID

    database = request.app.state.database
    async with database.transaction() as session:
        svc = InventoryService(session)
        try:
            return await svc.receive_stock(
                variant_id=UUID(payload.variant_id),
                location_key=payload.location_key,
                quantity=payload.quantity,
                actor_id=identity.user.id,
                idempotency_key=payload.idempotency_key,
            )
        except ValueError as exc:
            raise ApplicationError(400, "INVENTORY_ERROR", str(exc)) from exc


# ── Adjust ───────────────────────────────────────────────────────


@router.post("/adjust")
async def adjust_stock(
    payload: AdjustRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("inventory.adjust"))],
) -> dict[str, object]:
    from uuid import UUID

    database = request.app.state.database
    async with database.transaction() as session:
        svc = InventoryService(session)
        try:
            return await svc.adjust_stock(
                variant_id=UUID(payload.variant_id),
                location_id=UUID(payload.location_id),
                delta=payload.delta,
                reason=payload.reason,
                actor_id=identity.user.id,
                idempotency_key=payload.idempotency_key,
                notes=payload.notes,
            )
        except ValueError as exc:
            raise ApplicationError(400, "INVENTORY_ERROR", str(exc)) from exc

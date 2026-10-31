"""Guest cart HTTP routes — public, no auth required, CSRF-protected."""

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.cart.service import CartService
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.models import Product, ProductVariant
from modest_chic_backend.modules.inventory.models import InventoryBalance

router = APIRouter(prefix="/cart", tags=["guest-cart"])


class AddItemRequest(BaseModel):
    variant_id: UUID
    quantity: int = Field(gt=0, le=99)


def _guest_token_hash(request: Request) -> str:
    """Read the hashed guest token from a cookie. For now, accept a header."""
    import hashlib

    token = request.headers.get("X-Guest-Token", "") or request.cookies.get("mc_guest", "")
    if not token:
        raise ApplicationError(401, "GUEST_REQUIRED", "Guest identity is required.")
    return hashlib.sha256(token.encode()).hexdigest()


async def _validate_variant(session: AsyncSession, variant_id: UUID, quantity: int) -> None:
    result = await session.execute(
        select(ProductVariant)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(
            ProductVariant.id == variant_id,
            ProductVariant.is_active.is_(True),
            Product.status == ProductStatus.PUBLISHED,
        )
    )
    if result.scalar_one_or_none() is None:
        raise ApplicationError(404, "VARIANT_NOT_FOUND", "This item is unavailable.")
    stock_result = await session.execute(
        select(
            func.coalesce(func.sum(InventoryBalance.on_hand - InventoryBalance.reserved), 0)
        ).where(InventoryBalance.variant_id == variant_id)
    )
    if int(stock_result.scalar_one()) < quantity:
        raise ApplicationError(
            409, "INSUFFICIENT_STOCK", "The requested quantity is no longer available."
        )


@router.get("")
async def get_cart(request: Request) -> JSONResponse:
    token_hash = _guest_token_hash(request)
    database = request.app.state.database
    async with database.transaction() as session:
        svc = CartService(session)
        cart = await svc.get_or_create_cart(token_hash)
    return JSONResponse(content=cart)


@router.patch("/items/{item_id}")
async def update_item(item_id: UUID, payload: AddItemRequest, request: Request) -> JSONResponse:
    token_hash = _guest_token_hash(request)
    database = request.app.state.database
    async with database.transaction() as session:
        svc = CartService(session)
        cart = await svc.get_or_create_cart(token_hash)
        existing = next((item for item in cart["items"] if item["id"] == str(item_id)), None)
        if existing is None or existing["variant_id"] != str(payload.variant_id):
            raise ApplicationError(404, "CART_ITEM_NOT_FOUND", "Cart item not found.")
        await _validate_variant(session, payload.variant_id, payload.quantity)
        result = await svc.add_item(
            cart_id=UUID(cart["id"]),
            variant_id=payload.variant_id,
            quantity=payload.quantity,
        )
    return JSONResponse(content=result)


@router.post("/items")
async def add_item(payload: AddItemRequest, request: Request) -> JSONResponse:
    token_hash = _guest_token_hash(request)
    database = request.app.state.database
    async with database.transaction() as session:
        svc = CartService(session)
        cart = await svc.get_or_create_cart(token_hash)
        await _validate_variant(session, payload.variant_id, payload.quantity)
        result = await svc.add_item(
            cart_id=UUID(cart["id"]),
            variant_id=payload.variant_id,
            quantity=payload.quantity,
        )
    return JSONResponse(content=result)


@router.delete("/items/{item_id}")
async def remove_item(item_id: UUID, request: Request) -> JSONResponse:
    token_hash = _guest_token_hash(request)
    database = request.app.state.database
    async with database.transaction() as session:
        svc = CartService(session)
        cart = await svc.get_or_create_cart(token_hash)
        try:
            result = await svc.remove_item(cart_id=UUID(cart["id"]), item_id=item_id)
        except ValueError as exc:
            raise ApplicationError(400, "CART_ERROR", str(exc)) from exc
    return JSONResponse(content=result)

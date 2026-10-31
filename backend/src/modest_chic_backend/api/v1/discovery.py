"""Public discovery API — browse published products, categories, collections, search.

No authentication required. Returns only PUBLISHED, active content.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import selectinload

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.models import (
    Category,
    Collection,
    Product,
    ProductVariant,
    collection_products,
    product_categories,
)
from modest_chic_backend.modules.inventory.models import InventoryBalance
from modest_chic_backend.modules.orders.models import OrderItem

router = APIRouter(prefix="/catalog", tags=["public-catalog"])


# ── Products ──────────────────────────────────────────────────────


def _base_product_query() -> Any:
    """Return a base SELECT for published products with eager-loaded variants and media."""
    return (
        select(Product)
        .options(selectinload(Product.variants), selectinload(Product.media))
        .where(
            Product.status == ProductStatus.PUBLISHED,
            Product.variants.any(ProductVariant.is_active),
        )
    )


@router.get("/products")
async def list_public_products(
    request: Request,
    category: str | None = Query(default=None, max_length=100),
    collection: str | None = Query(default=None, max_length=100),
    q: str | None = Query(default=None, min_length=1, max_length=100),
    fabric: str | None = Query(default=None, max_length=100),
    color: str | None = Query(default=None, max_length=100),
    min_price_minor: int | None = Query(default=None, ge=0, le=100_000_000),
    max_price_minor: int | None = Query(default=None, ge=0, le=100_000_000),
    in_stock_only: bool = False,
    on_sale_only: bool = False,
    sort: str = Query(default="newest", pattern="^(newest|price-low|price-high|popular)$"),
    after: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> JSONResponse:
    if (
        min_price_minor is not None
        and max_price_minor is not None
        and max_price_minor < min_price_minor
    ):
        raise ApplicationError(
            422, "PRICE_RANGE_INVALID", "Maximum price must be at least the minimum price."
        )
    database = request.app.state.database
    async with database.session() as session:
        stmt = _apply_product_filters(
            _base_product_query(),
            category,
            collection,
            q,
            fabric,
            color,
            min_price_minor,
            max_price_minor,
            in_stock_only,
            on_sale_only,
        )
        return await _product_page(session, stmt, sort, after, limit)


@router.get("/products/{slug}")
async def get_public_product(slug: str, request: Request) -> JSONResponse:
    database = request.app.state.database
    async with database.session() as session:
        result = await session.execute(_base_product_query().where(Product.slug == slug))
        product = result.scalar_one_or_none()
        if product is None:
            return JSONResponse(
                status_code=404,
                content={"code": "PRODUCT_NOT_FOUND", "message": "Product not found."},
            )
        stock = await _available_stock(session, [product])
        categories = await _product_categories(session, [product])
        collections = await _product_collections(session, [product])
    return JSONResponse(content=_public_product_detail(product, stock, categories, collections))


# ── Categories ────────────────────────────────────────────────────


@router.get("/categories")
async def list_public_categories(request: Request) -> JSONResponse:
    database = request.app.state.database
    async with database.session() as session:
        result = await session.execute(
            select(Category)
            .where(Category.status == ProductStatus.PUBLISHED)
            .order_by(Category.sort_order, Category.name, Category.id)
        )
        categories = result.scalars().all()
    return JSONResponse(
        content={
            "items": [
                {
                    "id": str(c.id),
                    "slug": c.slug,
                    "name": c.name,
                    "description": c.description,
                    "parent_id": str(c.parent_id) if c.parent_id else None,
                }
                for c in categories
            ]
        }
    )


# ── Collections ───────────────────────────────────────────────────


@router.get("/collections")
async def list_public_collections(request: Request) -> JSONResponse:
    database = request.app.state.database
    now = datetime.now(UTC)
    async with database.session() as session:
        result = await session.execute(
            select(Collection)
            .where(
                Collection.status == ProductStatus.PUBLISHED,
                (Collection.starts_at.is_(None) | (Collection.starts_at <= now)),
                (Collection.ends_at.is_(None) | (Collection.ends_at >= now)),
            )
            .order_by(Collection.created_at.desc(), Collection.id.desc())
        )
        collections = result.scalars().all()
    return JSONResponse(
        content={
            "items": [
                {
                    "id": str(c.id),
                    "slug": c.slug,
                    "name": c.name,
                    "description": c.description,
                    "starts_at": c.starts_at.isoformat() if c.starts_at else None,
                    "ends_at": c.ends_at.isoformat() if c.ends_at else None,
                }
                for c in collections
            ]
        }
    )


# ── Search ────────────────────────────────────────────────────────


@router.get("/search")
async def search_products(
    request: Request,
    q: str = Query(min_length=1, max_length=100),
    category: str | None = Query(default=None, max_length=100),
    collection: str | None = Query(default=None, max_length=100),
    fabric: str | None = Query(default=None, max_length=100),
    color: str | None = Query(default=None, max_length=100),
    min_price_minor: int | None = Query(default=None, ge=0, le=100_000_000),
    max_price_minor: int | None = Query(default=None, ge=0, le=100_000_000),
    in_stock_only: bool = False,
    on_sale_only: bool = False,
    sort: str = Query(default="newest", pattern="^(newest|price-low|price-high|popular)$"),
    after: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> JSONResponse:
    if (
        max_price_minor is not None
        and min_price_minor is not None
        and max_price_minor < min_price_minor
    ):
        raise ApplicationError(
            422, "PRICE_RANGE_INVALID", "Maximum price must be at least the minimum price."
        )
    database = request.app.state.database
    async with database.session() as session:
        stmt = _apply_product_filters(
            _base_product_query(),
            category,
            collection,
            q.strip(),
            fabric,
            color,
            min_price_minor,
            max_price_minor,
            in_stock_only,
            on_sale_only,
        )
        return await _product_page(session, stmt, sort, after, limit)


# ── Helpers ───────────────────────────────────────────────────────


def _effective_variant_price() -> Any:
    return case(
        (ProductVariant.sale_price_minor.is_not(None), ProductVariant.sale_price_minor),
        else_=ProductVariant.price_minor,
    )


def _price_metric(descending: bool = False) -> Any:
    aggregate = func.max if descending else func.min
    return (
        select(aggregate(_effective_variant_price()))
        .where(ProductVariant.product_id == Product.id, ProductVariant.is_active)
        .correlate(Product)
        .scalar_subquery()
    )


def _popularity_metric() -> Any:
    return (
        select(func.coalesce(func.sum(OrderItem.fulfilled_quantity), 0))
        .join(ProductVariant, ProductVariant.id == OrderItem.variant_id)
        .where(ProductVariant.product_id == Product.id)
        .correlate(Product)
        .scalar_subquery()
    )


def _apply_product_filters(
    stmt: Any,
    category: str | None,
    collection: str | None,
    query: str | None,
    fabric: str | None,
    color: str | None,
    min_price_minor: int | None,
    max_price_minor: int | None,
    in_stock_only: bool,
    on_sale_only: bool,
) -> Any:
    if query:
        pattern = f"%{query}%"
        matching_colors = select(ProductVariant.product_id).where(
            ProductVariant.is_active, ProductVariant.color_name.ilike(pattern)
        )
        stmt = stmt.where(
            or_(
                Product.title.ilike(pattern),
                Product.description.ilike(pattern),
                Product.fabric.ilike(pattern),
                Product.id.in_(matching_colors),
            )
        )
    if category:
        product_ids = (
            select(product_categories.c.product_id)
            .join(Category, Category.id == product_categories.c.category_id)
            .where(Category.slug == category, Category.status == ProductStatus.PUBLISHED)
        )
        stmt = stmt.where(Product.id.in_(product_ids))
    if collection:
        now = datetime.now(UTC)
        product_ids = (
            select(collection_products.c.product_id)
            .join(Collection, Collection.id == collection_products.c.collection_id)
            .where(
                Collection.slug == collection,
                Collection.status == ProductStatus.PUBLISHED,
                or_(Collection.starts_at.is_(None), Collection.starts_at <= now),
                or_(Collection.ends_at.is_(None), Collection.ends_at >= now),
            )
        )
        stmt = stmt.where(Product.id.in_(product_ids))
    if fabric:
        stmt = stmt.where(Product.fabric.ilike(f"%{fabric.strip()}%"))
    if color:
        product_ids = select(ProductVariant.product_id).where(
            ProductVariant.is_active,
            ProductVariant.color_name.ilike(f"%{color.strip()}%"),
        )
        stmt = stmt.where(Product.id.in_(product_ids))
    if min_price_minor is not None or max_price_minor is not None:
        price = _effective_variant_price()
        conditions = [ProductVariant.is_active]
        if min_price_minor is not None:
            conditions.append(price >= min_price_minor)
        if max_price_minor is not None:
            conditions.append(price <= max_price_minor)
        stmt = stmt.where(Product.id.in_(select(ProductVariant.product_id).where(*conditions)))
    if in_stock_only:
        stock_products = (
            select(ProductVariant.product_id)
            .join(InventoryBalance, InventoryBalance.variant_id == ProductVariant.id)
            .where(ProductVariant.is_active)
            .group_by(ProductVariant.product_id)
            .having(func.sum(InventoryBalance.on_hand - InventoryBalance.reserved) > 0)
        )
        stmt = stmt.where(Product.id.in_(stock_products))
    if on_sale_only:
        sale_products = select(ProductVariant.product_id).where(
            ProductVariant.is_active, ProductVariant.sale_price_minor.is_not(None)
        )
        stmt = stmt.where(Product.id.in_(sale_products))
    return stmt


def _sort_order(sort: str) -> tuple[Any, ...]:
    if sort == "price-low":
        return (_price_metric().asc(), Product.id.asc())
    if sort == "price-high":
        return (_price_metric(descending=True).desc(), Product.id.asc())
    if sort == "popular":
        return (_popularity_metric().desc(), Product.created_at.desc(), Product.id.desc())
    return (Product.created_at.desc(), Product.id.desc())


async def _product_page(
    session: Any, stmt: Any, sort: str, after: UUID | None, limit: int
) -> JSONResponse:
    if after is not None:
        stmt = await _after_sort_cursor(session, stmt, after, sort)
    result = await session.execute(stmt.order_by(*_sort_order(sort)).limit(limit + 1))
    products = result.scalars().unique().all()
    page = products[:limit]
    stock = await _available_stock(session, page)
    categories = await _product_categories(session, page)
    collections = await _product_collections(session, page)
    items = [_public_product(product, stock, categories, collections) for product in page]
    next_cursor = str(page[-1].id) if len(products) > limit and page else None
    return JSONResponse(content={"items": items, "next_cursor": next_cursor})


async def _after_cursor(session: Any, stmt: Any, after: UUID) -> Any:
    """Compatibility wrapper for callers using the newest-first cursor order."""
    return await _after_sort_cursor(session, stmt, after, "newest")


async def _after_sort_cursor(session: Any, stmt: Any, after: UUID, sort: str) -> Any:
    cursor = await session.scalar(select(Product).where(Product.id == after))
    if cursor is None:
        raise ApplicationError(422, "INVALID_CURSOR", "The catalog cursor is invalid.")
    if sort in {"price-low", "price-high"}:
        descending = sort == "price-high"
        metric = _price_metric(descending)
        cursor_metric = await session.scalar(
            select(metric).select_from(Product).where(Product.id == after)
        )
        if cursor_metric is None:
            raise ApplicationError(422, "INVALID_CURSOR", "The catalog cursor is invalid.")
        comparison = metric < cursor_metric if descending else metric > cursor_metric
        return stmt.where(or_(comparison, and_(metric == cursor_metric, Product.id > after)))
    if sort == "popular":
        metric = _popularity_metric()
        cursor_metric = int(
            await session.scalar(select(metric).select_from(Product).where(Product.id == after))
            or 0
        )
        return stmt.where(
            or_(
                metric < cursor_metric,
                and_(metric == cursor_metric, Product.created_at < cursor.created_at),
                and_(
                    metric == cursor_metric,
                    Product.created_at == cursor.created_at,
                    Product.id < after,
                ),
            )
        )
    return stmt.where(
        or_(
            Product.created_at < cursor.created_at,
            and_(Product.created_at == cursor.created_at, Product.id < after),
        )
    )


async def _available_stock(session: Any, products: list[Product]) -> dict[UUID, int]:
    variant_ids = [v.id for product in products for v in product.variants if v.is_active]
    if not variant_ids:
        return {}
    result = await session.execute(
        select(
            InventoryBalance.variant_id,
            func.sum(InventoryBalance.on_hand - InventoryBalance.reserved),
        )
        .where(InventoryBalance.variant_id.in_(variant_ids))
        .group_by(InventoryBalance.variant_id)
    )
    return {variant_id: max(0, int(available or 0)) for variant_id, available in result.all()}


async def _product_categories(session: Any, products: list[Product]) -> dict[UUID, list[str]]:
    if not products:
        return {}
    result = await session.execute(
        select(product_categories.c.product_id, Category.slug)
        .join(Category, Category.id == product_categories.c.category_id)
        .where(
            product_categories.c.product_id.in_([product.id for product in products]),
            Category.status == ProductStatus.PUBLISHED,
        )
        .order_by(product_categories.c.sort_order, Category.id)
    )
    categories: dict[UUID, list[str]] = {}
    for product_id, slug in result.all():
        categories.setdefault(product_id, []).append(slug)
    return categories


async def _product_collections(session: Any, products: list[Product]) -> dict[UUID, list[str]]:
    if not products:
        return {}
    now = datetime.now(UTC)
    result = await session.execute(
        select(collection_products.c.product_id, Collection.slug)
        .join(Collection, Collection.id == collection_products.c.collection_id)
        .where(
            collection_products.c.product_id.in_([product.id for product in products]),
            Collection.status == ProductStatus.PUBLISHED,
            or_(Collection.starts_at.is_(None), Collection.starts_at <= now),
            or_(Collection.ends_at.is_(None), Collection.ends_at >= now),
        )
        .order_by(collection_products.c.sort_order, Collection.id)
    )
    collections: dict[UUID, list[str]] = {}
    for product_id, slug in result.all():
        collections.setdefault(product_id, []).append(slug)
    return collections


def _public_product(
    p: Product,
    stock: dict[UUID, int] | None = None,
    categories: dict[UUID, list[str]] | None = None,
    collections: dict[UUID, list[str]] | None = None,
) -> dict[str, Any]:
    product_collections = (collections or {}).get(p.id, [])
    now = datetime.now(UTC)
    is_new = p.created_at is not None and (now - p.created_at).days < 30
    is_featured = (
        "best-sellers" in product_collections or "signature-neutrals" in product_collections
    )
    return {
        "id": str(p.id),
        "slug": p.slug,
        "title": p.title,
        "description": p.description,
        "fabric": p.fabric,
        "care": p.care,
        "dimensions": p.dimensions,
        "category": next(iter((categories or {}).get(p.id, [])), ""),
        "categories": (categories or {}).get(p.id, []),
        "collections": product_collections,
        "is_new": is_new,
        "is_featured": is_featured,
        "variants": [
            {
                "id": str(v.id),
                "sku": v.sku,
                "color_name": v.color_name,
                "color_hex": v.color_hex,
                "price_minor": v.price_minor,
                "sale_price_minor": v.sale_price_minor,
                "is_active": v.is_active,
                "available_quantity": (stock or {}).get(v.id, 0),
            }
            for v in (p.variants or [])
            if v.is_active
        ],
        "primary_image": _primary_image(p.media or []),
        "created_at": p.created_at.isoformat(),
    }


def _public_product_detail(
    p: Product,
    stock: dict[UUID, int] | None = None,
    categories: dict[UUID, list[str]] | None = None,
    collections: dict[UUID, list[str]] | None = None,
) -> dict[str, Any]:
    d = _public_product(p, stock, categories, collections)
    d["media"] = [
        {
            "id": str(m.id),
            "object_key": m.object_key,
            "media_type": m.media_type,
            "alt_text": m.alt_text,
            "width": m.width,
            "height": m.height,
            "is_primary": m.is_primary,
            "sort_order": m.sort_order,
        }
        for m in (p.media or [])
        if m.status == ProductStatus.PUBLISHED
    ]
    return d


def _primary_image(media: list[Any]) -> dict[str, Any] | None:
    for m in sorted(media, key=lambda x: (not x.is_primary, x.sort_order)):
        if m.status == ProductStatus.PUBLISHED:
            return {"object_key": m.object_key, "alt_text": m.alt_text}
    return None

"""Catalog administration HTTP routes — products, variants, categories, collections, tags, media."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from modest_chic_backend.api.v1.dependencies import require_permission
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.auth.service import StaffIdentity
from modest_chic_backend.modules.catalog.errors import CatalogStaleEditError
from modest_chic_backend.modules.catalog.schemas import (
    CategoryCreate,
    CategoryListResponse,
    CategoryRead,
    CategoryUpdate,
    CollectionCreate,
    CollectionListResponse,
    CollectionProductsUpdate,
    CollectionRead,
    CollectionUpdate,
    MediaCreate,
    MediaRead,
    ProductCategoriesUpdate,
    ProductCreate,
    ProductDetail,
    ProductListResponse,
    ProductRead,
    ProductTagsUpdate,
    ProductUpdate,
    TagCreate,
    TagListResponse,
    TagRead,
    VariantCreate,
    VariantRead,
    VariantUpdate,
)
from modest_chic_backend.modules.catalog.service import CatalogService

router = APIRouter(prefix="/admin/catalog", tags=["admin-catalog"])

_CATALOG_WRITE = "catalog.write"

# ── Products ──────────────────────────────────────────────────────


@router.get("/products", response_model=ProductListResponse)
async def list_products(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("catalog.read"))],
    status: str | None = Query(default=None),
    after: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> ProductListResponse:
    database = request.app.state.database
    async with database.session() as session:
        svc = CatalogService(session)
        return await svc.list_products(status=status, after=after, limit=limit)


@router.post("/products", response_model=ProductRead, status_code=201)
async def create_product(
    payload: ProductCreate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission(_CATALOG_WRITE))],
) -> ProductRead:
    database = request.app.state.database
    async with database.transaction() as session:
        svc = CatalogService(session)
        try:
            return await svc.create_product(payload, actor_id=identity.user.id)
        except ValueError as exc:
            raise ApplicationError(400, "CATALOG_VALIDATION_ERROR", str(exc)) from exc


@router.get("/products/{product_id}", response_model=ProductDetail)
async def get_product(
    product_id: UUID,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("catalog.read"))],
) -> JSONResponse:
    database = request.app.state.database
    async with database.session() as session:
        svc = CatalogService(session)
        detail = await svc.get_product(product_id)
        if detail is None:
            raise ApplicationError(404, "PRODUCT_NOT_FOUND", "Product not found.")
    return JSONResponse(content=detail.model_dump(mode="json"))


@router.patch("/products/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission(_CATALOG_WRITE))],
) -> ProductRead:
    database = request.app.state.database
    async with database.transaction() as session:
        svc = CatalogService(session)
        try:
            result = await svc.update_product(product_id, payload, identity.user.id)
        except CatalogStaleEditError as exc:
            raise ApplicationError(409, "CATALOG_STALE_EDIT", str(exc)) from exc
        except ValueError as exc:
            raise ApplicationError(400, "CATALOG_VALIDATION_ERROR", str(exc)) from exc
        if result is None:
            raise ApplicationError(404, "PRODUCT_NOT_FOUND", "Product not found.")
    return result


@router.post("/products/{product_id}/archive", response_model=ProductRead)
async def archive_product(
    product_id: UUID,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("catalog.archive"))],
) -> ProductRead:
    database = request.app.state.database
    async with database.transaction() as session:
        result = await CatalogService(session).archive_product(product_id, identity.user.id)
        if result is None:
            raise ApplicationError(404, "PRODUCT_NOT_FOUND", "Product not found.")
    return result


# ── Variants ─────────────────────────────────────────────────────


@router.post("/products/{product_id}/variants", response_model=VariantRead, status_code=201)
async def add_variant(
    product_id: UUID,
    payload: VariantCreate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission(_CATALOG_WRITE))],
) -> VariantRead:
    database = request.app.state.database
    async with database.transaction() as session:
        svc = CatalogService(session)
        try:
            result = await svc.add_variant(product_id, payload, identity.user.id)
        except ValueError as exc:
            raise ApplicationError(400, "CATALOG_VALIDATION_ERROR", str(exc)) from exc
        if result is None:
            raise ApplicationError(404, "PRODUCT_NOT_FOUND", "Product not found.")
    return result


@router.get("/products/{product_id}/categories", response_model=list[str])
async def list_product_categories(
    product_id: UUID,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("catalog.read"))],
) -> list[str]:
    database = request.app.state.database
    async with database.session() as session:
        category_ids = await CatalogService(session).get_product_category_ids(product_id)
        if category_ids is None:
            raise ApplicationError(404, "PRODUCT_NOT_FOUND", "Product not found.")
    return [str(category_id) for category_id in category_ids]


@router.put("/products/{product_id}/categories", status_code=204)
async def set_product_categories(
    product_id: UUID,
    payload: ProductCategoriesUpdate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission(_CATALOG_WRITE))],
) -> None:
    database = request.app.state.database
    async with database.transaction() as session:
        try:
            updated = await CatalogService(session).set_product_categories(
                product_id, payload, identity.user.id
            )
        except CatalogStaleEditError as exc:
            raise ApplicationError(409, "CATALOG_STALE_EDIT", str(exc)) from exc
        except ValueError as exc:
            raise ApplicationError(400, "CATALOG_VALIDATION_ERROR", str(exc)) from exc
        if not updated:
            raise ApplicationError(404, "PRODUCT_NOT_FOUND", "Product not found.")


@router.get("/products/{product_id}/tags", response_model=list[str])
async def list_product_tags(
    product_id: UUID,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("catalog.read"))],
) -> list[str]:
    database = request.app.state.database
    async with database.session() as session:
        tag_ids = await CatalogService(session).get_product_tag_ids(product_id)
        if tag_ids is None:
            raise ApplicationError(404, "PRODUCT_NOT_FOUND", "Product not found.")
    return [str(tag_id) for tag_id in tag_ids]


@router.put("/products/{product_id}/tags", status_code=204)
async def set_product_tags(
    product_id: UUID,
    payload: ProductTagsUpdate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission(_CATALOG_WRITE))],
) -> None:
    database = request.app.state.database
    async with database.transaction() as session:
        try:
            updated = await CatalogService(session).set_product_tags(
                product_id, payload, identity.user.id
            )
        except CatalogStaleEditError as exc:
            raise ApplicationError(409, "CATALOG_STALE_EDIT", str(exc)) from exc
        except ValueError as exc:
            raise ApplicationError(400, "CATALOG_VALIDATION_ERROR", str(exc)) from exc
        if not updated:
            raise ApplicationError(404, "PRODUCT_NOT_FOUND", "Product not found.")


@router.patch("/variants/{variant_id}", response_model=VariantRead)
async def update_variant(
    variant_id: UUID,
    payload: VariantUpdate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission(_CATALOG_WRITE))],
) -> VariantRead:
    database = request.app.state.database
    async with database.transaction() as session:
        svc = CatalogService(session)
        try:
            result = await svc.update_variant(variant_id, payload, identity.user.id)
        except CatalogStaleEditError as exc:
            raise ApplicationError(409, "CATALOG_STALE_EDIT", str(exc)) from exc
        except ValueError as exc:
            raise ApplicationError(400, "CATALOG_VALIDATION_ERROR", str(exc)) from exc
        if result is None:
            raise ApplicationError(404, "VARIANT_NOT_FOUND", "Variant not found.")
    return result


# ── Categories ───────────────────────────────────────────────────


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("catalog.read"))],
) -> CategoryListResponse:
    database = request.app.state.database
    async with database.session() as session:
        return await CatalogService(session).list_categories()


@router.post("/categories", response_model=CategoryRead, status_code=201)
async def create_category(
    payload: CategoryCreate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission(_CATALOG_WRITE))],
) -> CategoryRead:
    database = request.app.state.database
    async with database.transaction() as session:
        try:
            return await CatalogService(session).create_category(payload, identity.user.id)
        except ValueError as exc:
            raise ApplicationError(400, "CATALOG_VALIDATION_ERROR", str(exc)) from exc


@router.patch("/categories/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission(_CATALOG_WRITE))],
) -> CategoryRead:
    database = request.app.state.database
    async with database.transaction() as session:
        try:
            result = await CatalogService(session).update_category(
                category_id, payload, identity.user.id
            )
        except CatalogStaleEditError as exc:
            raise ApplicationError(409, "CATALOG_STALE_EDIT", str(exc)) from exc
        except ValueError as exc:
            raise ApplicationError(400, "CATALOG_VALIDATION_ERROR", str(exc)) from exc
        if result is None:
            raise ApplicationError(404, "CATEGORY_NOT_FOUND", "Category not found.")
    return result


# ── Collections ──────────────────────────────────────────────────


@router.get("/collections", response_model=CollectionListResponse)
async def list_collections(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("catalog.read"))],
) -> CollectionListResponse:
    database = request.app.state.database
    async with database.session() as session:
        return await CatalogService(session).list_collections()


@router.post("/collections", response_model=CollectionRead, status_code=201)
async def create_collection(
    payload: CollectionCreate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission(_CATALOG_WRITE))],
) -> CollectionRead:
    database = request.app.state.database
    async with database.transaction() as session:
        try:
            return await CatalogService(session).create_collection(payload, identity.user.id)
        except ValueError as exc:
            raise ApplicationError(400, "CATALOG_VALIDATION_ERROR", str(exc)) from exc


@router.put("/collections/{collection_id}/products", status_code=204)
async def set_collection_products(
    collection_id: UUID,
    payload: CollectionProductsUpdate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission(_CATALOG_WRITE))],
) -> None:
    database = request.app.state.database
    async with database.transaction() as session:
        try:
            updated = await CatalogService(session).set_collection_products(
                collection_id, payload, identity.user.id
            )
        except CatalogStaleEditError as exc:
            raise ApplicationError(409, "CATALOG_STALE_EDIT", str(exc)) from exc
        except ValueError as exc:
            raise ApplicationError(400, "CATALOG_VALIDATION_ERROR", str(exc)) from exc
        if not updated:
            raise ApplicationError(404, "COLLECTION_NOT_FOUND", "Collection not found.")


@router.get("/collections/{collection_id}/products", response_model=list[str])
async def list_collection_products(
    collection_id: UUID,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("catalog.read"))],
) -> list[str]:
    database = request.app.state.database
    async with database.session() as session:
        product_ids = await CatalogService(session).get_collection_product_ids(collection_id)
        if product_ids is None:
            raise ApplicationError(404, "COLLECTION_NOT_FOUND", "Collection not found.")
    return [str(product_id) for product_id in product_ids]


# ── Tags ─────────────────────────────────────────────────────────


@router.get("/tags", response_model=TagListResponse)
async def list_tags(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("catalog.read"))],
) -> TagListResponse:
    database = request.app.state.database
    async with database.session() as session:
        return await CatalogService(session).list_tags()


@router.post("/tags", response_model=TagRead, status_code=201)
async def create_tag(
    payload: TagCreate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission(_CATALOG_WRITE))],
) -> TagRead:
    database = request.app.state.database
    async with database.transaction() as session:
        try:
            return await CatalogService(session).create_tag(payload, identity.user.id)
        except ValueError as exc:
            raise ApplicationError(400, "CATALOG_VALIDATION_ERROR", str(exc)) from exc


# ── Media ────────────────────────────────────────────────────────


@router.post("/products/{product_id}/media", response_model=MediaRead, status_code=201)
async def attach_media(
    product_id: UUID,
    payload: MediaCreate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission(_CATALOG_WRITE))],
) -> MediaRead:
    database = request.app.state.database
    async with database.transaction() as session:
        try:
            result = await CatalogService(session).attach_media(
                product_id, payload, identity.user.id
            )
        except ValueError as exc:
            raise ApplicationError(400, "CATALOG_VALIDATION_ERROR", str(exc)) from exc
        if result is None:
            raise ApplicationError(404, "PRODUCT_NOT_FOUND", "Product not found.")
    return result


@router.patch("/collections/{collection_id}", response_model=CollectionRead)
async def update_collection(
    collection_id: UUID,
    payload: CollectionUpdate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission(_CATALOG_WRITE))],
) -> CollectionRead:
    database = request.app.state.database
    async with database.transaction() as session:
        try:
            result = await CatalogService(session).update_collection(
                collection_id, payload, identity.user.id
            )
        except CatalogStaleEditError as exc:
            raise ApplicationError(409, "CATALOG_STALE_EDIT", str(exc)) from exc
        except ValueError as exc:
            raise ApplicationError(400, "CATALOG_VALIDATION_ERROR", str(exc)) from exc
        if result is None:
            raise ApplicationError(404, "COLLECTION_NOT_FOUND", "Collection not found.")
    return result

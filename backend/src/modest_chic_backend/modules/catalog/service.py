"""Catalog business logic — product/variant lifecycle, categories, collections, tags, media."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.core.pagination import CursorPaginator
from modest_chic_backend.modules.audit.repository import AuditRepository
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.errors import CatalogStaleEditError
from modest_chic_backend.modules.catalog.models import (
    Category,
    Collection,
    Product,
    ProductMedia,
    ProductTag,
    ProductVariant,
)
from modest_chic_backend.modules.catalog.repository import CatalogRepository
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


def _make_product_read(p: Product) -> ProductRead:
    return ProductRead(
        id=p.id,
        slug=p.slug,
        title=p.title,
        description=p.description,
        fabric=p.fabric,
        care=p.care,
        dimensions=p.dimensions,
        status=p.status,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


class CatalogService:
    """Application service for catalog administration."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CatalogRepository(session)
        self._audit = AuditRepository(session)

    # ── Products ─────────────────────────────────────────────────

    async def create_product(self, payload: ProductCreate, actor_id: uuid.UUID) -> ProductRead:
        """Create a product in DRAFT status with optional initial variants."""
        existing = await self._repo.get_product_by_slug(payload.slug)
        if existing:
            raise ValueError(f"slug '{payload.slug}' is already taken")

        product = Product(
            slug=payload.slug,
            title=payload.title,
            description=payload.description,
            fabric=payload.fabric,
            care=payload.care,
            dimensions=payload.dimensions,
            created_by=actor_id,
        )
        for v in payload.variants:
            sku_existing = await self._repo.get_variant_by_sku(v.sku)
            if sku_existing:
                raise ValueError(f"SKU '{v.sku}' is already taken")
            variant = ProductVariant(
                sku=v.sku,
                color_name=v.color_name,
                color_hex=v.color_hex,
                dimensions=v.dimensions,
                weight_grams=v.weight_grams,
                price_minor=v.price_minor,
                sale_price_minor=v.sale_price_minor,
                created_by=actor_id,
            )
            product.variants.append(variant)

        await self._repo.create_product(product)
        await self._audit.record(
            action="catalog.product_created",
            entity_type="product",
            actor_id=actor_id,
            entity_id=product.id,
            metadata={"slug": payload.slug},
        )
        return _make_product_read(product)

    async def get_product(self, product_id: uuid.UUID) -> ProductDetail | None:
        p = await self._repo.get_product_with_variants(product_id)
        if p is None:
            return None
        return ProductDetail(
            id=p.id,
            slug=p.slug,
            title=p.title,
            description=p.description,
            fabric=p.fabric,
            care=p.care,
            dimensions=p.dimensions,
            status=p.status,
            created_at=p.created_at,
            updated_at=p.updated_at,
            variants=[VariantRead.model_validate(v) for v in (p.variants or [])],
            media=[MediaRead.model_validate(m) for m in (p.media or [])],
        )

    async def list_products(
        self, status: str | None = None, after: str | None = None, limit: int = 20
    ) -> ProductListResponse:
        after_id = CursorPaginator.decode(after) if after else None
        items = await self._repo.list_products(status=status, after=after_id, limit=limit)
        page, next_cursor = CursorPaginator.paginate(items, limit=limit)
        return ProductListResponse(
            items=[_make_product_read(p) for p in page],
            next_cursor=next_cursor,
        )

    async def update_product(
        self, product_id: uuid.UUID, payload: ProductUpdate, actor_id: uuid.UUID
    ) -> ProductRead | None:
        product = await self._repo.get_product_for_update(product_id)
        if product is None:
            return None
        if product.updated_at != payload.expected_updated_at:
            raise CatalogStaleEditError("Product changed since it was loaded. Reload and retry.")
        fields = payload.model_dump(exclude_none=True, exclude={"expected_updated_at"})
        if not fields:
            raise ValueError("no fields to update")
        if fields.get("status") == ProductStatus.ARCHIVED:
            raise ValueError("archive products through the archive action")
        if fields.get("status") == ProductStatus.PUBLISHED:
            if await self._repo.active_variant_count(product_id) == 0:
                raise ValueError("add at least one active variant before publishing")
        slug = fields.get("slug")
        if isinstance(slug, str):
            existing = await self._repo.get_product_by_slug(slug)
            if existing is not None and existing.id != product_id:
                raise ValueError(f"slug '{slug}' is already taken")
        updated = await self._repo.update_product(product_id, updated_by=actor_id, **fields)
        if updated is None:
            return None
        await self._audit.record(
            action="catalog.product_updated",
            entity_type="product",
            actor_id=actor_id,
            entity_id=product_id,
            metadata={"fields": list(fields.keys())},
        )
        return _make_product_read(updated)

    async def archive_product(
        self, product_id: uuid.UUID, actor_id: uuid.UUID
    ) -> ProductRead | None:
        """Archive a product while retaining its order snapshots and audit history."""
        updated = await self._repo.update_product(
            product_id, status=ProductStatus.ARCHIVED, updated_by=actor_id
        )
        if updated is None:
            return None
        await self._audit.record(
            action="catalog.product_archived",
            entity_type="product",
            actor_id=actor_id,
            entity_id=product_id,
        )
        return _make_product_read(updated)

    async def get_product_category_ids(self, product_id: uuid.UUID) -> list[uuid.UUID] | None:
        if await self._repo.get_product(product_id) is None:
            return None
        return await self._repo.list_product_category_ids(product_id)

    async def set_product_categories(
        self,
        product_id: uuid.UUID,
        payload: ProductCategoriesUpdate,
        actor_id: uuid.UUID,
    ) -> bool:
        product = await self._repo.get_product_for_update(product_id)
        if product is None:
            return False
        if product.updated_at != payload.expected_updated_at:
            raise CatalogStaleEditError("product changed since it was loaded; reload and retry")
        if len(set(payload.category_ids)) != len(payload.category_ids):
            raise ValueError("a category may appear only once for a product")
        for category_id in payload.category_ids:
            if await self._repo.get_category(category_id) is None:
                raise ValueError(f"category '{category_id}' does not exist")
        await self._repo.set_product_categories(product_id, payload.category_ids)
        product.updated_at = datetime.now(UTC)
        product.updated_by = actor_id
        await self._session.flush()
        await self._audit.record(
            action="catalog.product_categories_set",
            entity_type="product",
            actor_id=actor_id,
            entity_id=product_id,
            metadata={"category_ids": [str(value) for value in payload.category_ids]},
        )
        return True

    async def get_product_tag_ids(self, product_id: uuid.UUID) -> list[uuid.UUID] | None:
        if await self._repo.get_product(product_id) is None:
            return None
        return await self._repo.list_product_tag_ids(product_id)

    async def set_product_tags(
        self,
        product_id: uuid.UUID,
        payload: ProductTagsUpdate,
        actor_id: uuid.UUID,
    ) -> bool:
        product = await self._repo.get_product_for_update(product_id)
        if product is None:
            return False
        if product.updated_at != payload.expected_updated_at:
            raise CatalogStaleEditError("product changed since it was loaded; reload and retry")
        if len(set(payload.tag_ids)) != len(payload.tag_ids):
            raise ValueError("a tag may appear only once for a product")
        for tag_id in payload.tag_ids:
            if await self._repo.get_tag(tag_id) is None:
                raise ValueError(f"tag '{tag_id}' does not exist")
        await self._repo.set_product_tags(product_id, payload.tag_ids)
        product.updated_at = datetime.now(UTC)
        product.updated_by = actor_id
        await self._session.flush()
        await self._audit.record(
            action="catalog.product_tags_set",
            entity_type="product",
            actor_id=actor_id,
            entity_id=product_id,
            metadata={"tag_ids": [str(value) for value in payload.tag_ids]},
        )
        return True

    # ── Variants ─────────────────────────────────────────────────

    async def add_variant(
        self, product_id: uuid.UUID, payload: VariantCreate, actor_id: uuid.UUID
    ) -> VariantRead | None:
        """Add a variant to an existing product."""
        product = await self._repo.get_product(product_id)
        if product is None:
            return None
        existing = await self._repo.get_variant_by_sku(payload.sku)
        if existing:
            raise ValueError(f"SKU '{payload.sku}' is already taken")
        variant = ProductVariant(
            product_id=product_id,
            sku=payload.sku,
            color_name=payload.color_name,
            color_hex=payload.color_hex,
            dimensions=payload.dimensions,
            weight_grams=payload.weight_grams,
            price_minor=payload.price_minor,
            sale_price_minor=payload.sale_price_minor,
            created_by=actor_id,
        )
        await self._repo.create_variant(variant)
        await self._audit.record(
            action="catalog.variant_created",
            entity_type="product_variant",
            actor_id=actor_id,
            entity_id=variant.id,
        )
        return VariantRead.model_validate(variant)

    async def update_variant(
        self, variant_id: uuid.UUID, payload: VariantUpdate, actor_id: uuid.UUID
    ) -> VariantRead | None:
        variant = await self._repo.get_variant_for_update(variant_id)
        if variant is None:
            return None
        if variant.updated_at != payload.expected_updated_at:
            raise CatalogStaleEditError("Variant changed since it was loaded. Reload and retry.")
        fields = payload.model_dump(exclude_unset=True, exclude={"expected_updated_at"})
        if not fields:
            raise ValueError("no fields to update")
        updated = await self._repo.update_variant(variant_id, updated_by=actor_id, **fields)
        if updated is None:
            return None
        await self._audit.record(
            action="catalog.variant_updated",
            entity_type="product_variant",
            actor_id=actor_id,
            entity_id=variant_id,
            metadata={"fields": list(fields.keys())},
        )
        return VariantRead.model_validate(updated)

    # ── Categories ───────────────────────────────────────────────

    async def create_category(self, payload: CategoryCreate, actor_id: uuid.UUID) -> CategoryRead:
        existing = await self._repo.get_category_by_slug(payload.slug)
        if existing:
            raise ValueError(f"slug '{payload.slug}' is already taken")
        cat = Category(
            slug=payload.slug,
            name=payload.name,
            description=payload.description,
            parent_id=payload.parent_id,
            sort_order=payload.sort_order,
            created_by=actor_id,
        )
        await self._repo.create_category(cat)
        return CategoryRead.model_validate(cat)

    async def list_categories(self) -> CategoryListResponse:
        rows = await self._repo.list_categories()
        lookup = {c.id: CategoryRead.model_validate(c) for c in rows}
        roots: list[CategoryRead] = []
        for cat in rows:
            read = lookup[cat.id]
            if cat.parent_id and cat.parent_id in lookup:
                lookup[cat.parent_id].children.append(read)
            else:
                roots.append(read)
        return CategoryListResponse(items=roots)

    async def update_category(
        self, category_id: uuid.UUID, payload: CategoryUpdate, actor_id: uuid.UUID
    ) -> CategoryRead | None:
        category = await self._repo.get_category_for_update(category_id)
        if category is None:
            return None
        if category.updated_at != payload.expected_updated_at:
            raise CatalogStaleEditError("category changed since it was loaded; reload and retry")
        fields = payload.model_dump(exclude_none=True, exclude={"expected_updated_at"})
        if not fields:
            raise ValueError("no fields to update")
        updated = await self._repo.update_category(category_id, updated_by=actor_id, **fields)
        if updated is None:
            return None
        await self._audit.record(
            action="catalog.category_updated",
            entity_type="category",
            actor_id=actor_id,
            entity_id=category_id,
            metadata={"fields": list(fields.keys())},
        )
        return CategoryRead.model_validate(updated)

    # ── Collections ──────────────────────────────────────────────

    async def create_collection(
        self, payload: CollectionCreate, actor_id: uuid.UUID
    ) -> CollectionRead:
        existing = await self._repo.get_collection_by_slug(payload.slug)
        if existing:
            raise ValueError(f"slug '{payload.slug}' is already taken")
        coll = Collection(
            slug=payload.slug,
            name=payload.name,
            description=payload.description,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            created_by=actor_id,
        )
        await self._repo.create_collection(coll)
        return CollectionRead.model_validate(coll)

    async def list_collections(self) -> CollectionListResponse:
        rows = await self._repo.list_collections()
        return CollectionListResponse(items=[CollectionRead.model_validate(c) for c in rows])

    async def update_collection(
        self, collection_id: uuid.UUID, payload: CollectionUpdate, actor_id: uuid.UUID
    ) -> CollectionRead | None:
        collection = await self._repo.get_collection_for_update(collection_id)
        if collection is None:
            return None
        if collection.updated_at != payload.expected_updated_at:
            raise CatalogStaleEditError("collection changed since it was loaded; reload and retry")
        fields = payload.model_dump(exclude_none=True, exclude={"expected_updated_at"})
        if not fields:
            raise ValueError("no fields to update")
        updated = await self._repo.update_collection(collection_id, updated_by=actor_id, **fields)
        if updated is None:
            return None
        await self._audit.record(
            action="catalog.collection_updated",
            entity_type="collection",
            actor_id=actor_id,
            entity_id=collection_id,
            metadata={"fields": list(fields.keys())},
        )
        return CollectionRead.model_validate(updated)

    async def set_collection_products(
        self,
        collection_id: uuid.UUID,
        payload: CollectionProductsUpdate,
        actor_id: uuid.UUID,
    ) -> bool:
        collection = await self._repo.get_collection_for_update(collection_id)
        if collection is None:
            return False
        if collection.updated_at != payload.expected_updated_at:
            raise CatalogStaleEditError("collection changed since it was loaded; reload and retry")
        if len(set(payload.product_ids)) != len(payload.product_ids):
            raise ValueError("a product may appear only once in a collection")
        for product_id in payload.product_ids:
            if await self._repo.get_product(product_id) is None:
                raise ValueError(f"product '{product_id}' does not exist")
        await self._repo.set_collection_products(collection_id, payload.product_ids)
        collection.updated_at = datetime.now(UTC)
        collection.updated_by = actor_id
        await self._session.flush()
        await self._audit.record(
            action="catalog.collection_products_set",
            entity_type="collection",
            actor_id=actor_id,
            entity_id=collection_id,
        )
        return True

    async def get_collection_product_ids(self, collection_id: uuid.UUID) -> list[uuid.UUID] | None:
        if await self._repo.get_collection(collection_id) is None:
            return None
        return await self._repo.list_collection_product_ids(collection_id)

    # ── Tags ─────────────────────────────────────────────────────

    async def create_tag(self, payload: TagCreate, actor_id: uuid.UUID) -> TagRead:
        existing = await self._repo.get_tag_by_name(payload.name)
        if existing:
            raise ValueError(f"tag '{payload.name}' already exists")
        tag = ProductTag(name=payload.name, created_by=actor_id)
        await self._repo.create_tag(tag)
        return TagRead.model_validate(tag)

    async def list_tags(self) -> TagListResponse:
        rows = await self._repo.list_tags()
        return TagListResponse(items=[TagRead.model_validate(t) for t in rows])

    # ── Media ────────────────────────────────────────────────────

    async def attach_media(
        self, product_id: uuid.UUID, payload: MediaCreate, actor_id: uuid.UUID
    ) -> MediaRead | None:
        product = await self._repo.get_product_for_update(product_id)
        if product is None:
            return None
        if payload.variant_id is not None:
            variant = await self._repo.get_variant(payload.variant_id)
            if variant is None or variant.product_id != product_id:
                raise ValueError("media variant must belong to the selected product")
        replaced_primary_ids: list[uuid.UUID] = []
        if payload.is_primary:
            replaced_primary_ids = await self._repo.clear_primary_media(
                product_id,
                payload.variant_id,
                actor_id,
                datetime.now(UTC),
            )
        media = ProductMedia(
            product_id=product_id,
            variant_id=payload.variant_id,
            object_key=payload.object_key,
            media_type=payload.media_type,
            alt_text=payload.alt_text,
            width=payload.width,
            height=payload.height,
            sort_order=payload.sort_order,
            is_primary=payload.is_primary,
            created_by=actor_id,
        )
        await self._repo.create_media(media)
        await self._audit.record(
            action="catalog.media_attached",
            entity_type="product_media",
            actor_id=actor_id,
            entity_id=media.id,
            metadata={
                "product_id": str(product_id),
                "variant_id": str(payload.variant_id) if payload.variant_id else None,
                "media_type": payload.media_type,
                "sort_order": payload.sort_order,
                "is_primary": payload.is_primary,
                "replaced_primary_ids": [str(media_id) for media_id in replaced_primary_ids],
            },
        )
        return MediaRead.model_validate(media)

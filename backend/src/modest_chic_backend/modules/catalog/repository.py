"""Catalog database access — products, variants, categories, collections, tags, media."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modest_chic_backend.modules.catalog.models import (
    Category,
    Collection,
    Product,
    ProductMedia,
    ProductTag,
    ProductVariant,
    collection_products,
    product_categories,
    product_tag_links,
)


class CatalogRepository:
    """Read/write catalog entities with uniqueness enforcement."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Products ─────────────────────────────────────────────────

    async def get_product(self, product_id: uuid.UUID) -> Product | None:
        return await self._session.get(Product, product_id)

    async def get_product_for_update(self, product_id: uuid.UUID) -> Product | None:
        result = await self._session.execute(
            select(Product).where(Product.id == product_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_product_with_variants(self, product_id: uuid.UUID) -> Product | None:
        result = await self._session.execute(
            select(Product)
            .options(selectinload(Product.variants), selectinload(Product.media))
            .where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def get_product_by_slug(self, slug: str) -> Product | None:
        result = await self._session.execute(select(Product).where(Product.slug == slug))
        return result.scalar_one_or_none()

    async def list_products(
        self,
        status: str | None = None,
        after: uuid.UUID | None = None,
        limit: int = 20,
    ) -> list[Product]:
        stmt = select(Product).order_by(Product.id.desc())
        if status:
            stmt = stmt.where(Product.status == status)
        if after:
            stmt = stmt.where(Product.id < after)
        stmt = stmt.limit(limit + 1)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_product(self, product: Product) -> Product:
        self._session.add(product)
        await self._session.flush()
        return product

    async def update_product(self, product_id: uuid.UUID, **fields: object) -> Product | None:
        product = await self.get_product(product_id)
        if product is None:
            return None
        for key, value in fields.items():
            setattr(product, key, value)
        await self._session.flush()
        return product

    async def list_product_category_ids(self, product_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self._session.execute(
            select(product_categories.c.category_id)
            .where(product_categories.c.product_id == product_id)
            .order_by(product_categories.c.sort_order)
        )
        return list(result.scalars().all())

    async def set_product_categories(
        self, product_id: uuid.UUID, category_ids: list[uuid.UUID]
    ) -> None:
        await self._session.execute(
            delete(product_categories).where(product_categories.c.product_id == product_id)
        )
        for sort_order, category_id in enumerate(category_ids):
            await self._session.execute(
                product_categories.insert().values(
                    product_id=product_id, category_id=category_id, sort_order=sort_order
                )
            )

    async def list_product_tag_ids(self, product_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self._session.execute(
            select(product_tag_links.c.tag_id)
            .join(ProductTag, ProductTag.id == product_tag_links.c.tag_id)
            .where(product_tag_links.c.product_id == product_id)
            .order_by(ProductTag.name, ProductTag.id)
        )
        return list(result.scalars().all())

    async def set_product_tags(self, product_id: uuid.UUID, tag_ids: list[uuid.UUID]) -> None:
        await self._session.execute(
            delete(product_tag_links).where(product_tag_links.c.product_id == product_id)
        )
        if tag_ids:
            await self._session.execute(
                product_tag_links.insert(),
                [{"product_id": product_id, "tag_id": tag_id} for tag_id in tag_ids],
            )

    # ── Variants ─────────────────────────────────────────────────

    async def get_variant(self, variant_id: uuid.UUID) -> ProductVariant | None:
        return await self._session.get(ProductVariant, variant_id)

    async def get_variant_for_update(self, variant_id: uuid.UUID) -> ProductVariant | None:
        result = await self._session.execute(
            select(ProductVariant).where(ProductVariant.id == variant_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_variant_by_sku(self, sku: str) -> ProductVariant | None:
        result = await self._session.execute(
            select(ProductVariant).where(ProductVariant.sku == sku)
        )
        return result.scalar_one_or_none()

    async def active_variant_count(self, product_id: uuid.UUID) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(ProductVariant)
            .where(
                ProductVariant.product_id == product_id,
                ProductVariant.is_active.is_(True),
            )
        )
        return count or 0

    async def create_variant(self, variant: ProductVariant) -> ProductVariant:
        self._session.add(variant)
        await self._session.flush()
        return variant

    async def update_variant(
        self, variant_id: uuid.UUID, **fields: object
    ) -> ProductVariant | None:
        variant = await self.get_variant(variant_id)
        if variant is None:
            return None
        for key, value in fields.items():
            setattr(variant, key, value)
        await self._session.flush()
        return variant

    # ── Categories ───────────────────────────────────────────────

    async def list_categories(self) -> list[Category]:
        result = await self._session.execute(select(Category).order_by(Category.sort_order))
        return list(result.scalars().all())

    async def get_category(self, category_id: uuid.UUID) -> Category | None:
        return await self._session.get(Category, category_id)

    async def get_category_for_update(self, category_id: uuid.UUID) -> Category | None:
        result = await self._session.execute(
            select(Category).where(Category.id == category_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_category_by_slug(self, slug: str) -> Category | None:
        result = await self._session.execute(select(Category).where(Category.slug == slug))
        return result.scalar_one_or_none()

    async def create_category(self, category: Category) -> Category:
        self._session.add(category)
        await self._session.flush()
        return category

    async def update_category(self, category_id: uuid.UUID, **fields: object) -> Category | None:
        cat = await self.get_category(category_id)
        if cat is None:
            return None
        for key, value in fields.items():
            if value is not None:
                setattr(cat, key, value)
        cat.updated_at = datetime.now(UTC)
        await self._session.flush()
        return cat

    # ── Collections ──────────────────────────────────────────────

    async def list_collections(self) -> list[Collection]:
        result = await self._session.execute(select(Collection))
        return list(result.scalars().all())

    async def list_collection_product_ids(self, collection_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self._session.execute(
            select(collection_products.c.product_id)
            .where(collection_products.c.collection_id == collection_id)
            .order_by(collection_products.c.sort_order)
        )
        return list(result.scalars().all())

    async def get_collection(self, collection_id: uuid.UUID) -> Collection | None:
        return await self._session.get(Collection, collection_id)

    async def get_collection_for_update(self, collection_id: uuid.UUID) -> Collection | None:
        result = await self._session.execute(
            select(Collection).where(Collection.id == collection_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_collection_by_slug(self, slug: str) -> Collection | None:
        result = await self._session.execute(select(Collection).where(Collection.slug == slug))
        return result.scalar_one_or_none()

    async def create_collection(self, collection: Collection) -> Collection:
        self._session.add(collection)
        await self._session.flush()
        return collection

    async def update_collection(
        self, collection_id: uuid.UUID, **fields: object
    ) -> Collection | None:
        collection = await self.get_collection(collection_id)
        if collection is None:
            return None
        for key, value in fields.items():
            if value is not None:
                setattr(collection, key, value)
        collection.updated_at = datetime.now(UTC)
        await self._session.flush()
        return collection

    async def set_collection_products(
        self, collection_id: uuid.UUID, product_ids: list[uuid.UUID]
    ) -> None:
        await self._session.execute(
            delete(collection_products).where(collection_products.c.collection_id == collection_id)
        )
        for idx, pid in enumerate(product_ids):
            await self._session.execute(
                collection_products.insert().values(
                    collection_id=collection_id, product_id=pid, sort_order=idx
                )
            )

    # ── Tags ─────────────────────────────────────────────────────

    async def list_tags(self) -> list[ProductTag]:
        result = await self._session.execute(select(ProductTag).order_by(ProductTag.name))
        return list(result.scalars().all())

    async def get_tag_by_name(self, name: str) -> ProductTag | None:
        result = await self._session.execute(select(ProductTag).where(ProductTag.name == name))
        return result.scalar_one_or_none()

    async def get_tag(self, tag_id: uuid.UUID) -> ProductTag | None:
        return await self._session.get(ProductTag, tag_id)

    async def create_tag(self, tag: ProductTag) -> ProductTag:
        self._session.add(tag)
        await self._session.flush()
        return tag

    # ── Media ────────────────────────────────────────────────────

    async def create_media(self, media: ProductMedia) -> ProductMedia:
        self._session.add(media)
        await self._session.flush()
        return media

    async def clear_primary_media(
        self,
        product_id: uuid.UUID,
        variant_id: uuid.UUID | None,
        actor_id: uuid.UUID,
        updated_at: datetime,
    ) -> list[uuid.UUID]:
        statement = update(ProductMedia).where(
            ProductMedia.product_id == product_id,
            ProductMedia.variant_id.is_(None)
            if variant_id is None
            else ProductMedia.variant_id == variant_id,
            ProductMedia.is_primary.is_(True),
        )
        result = await self._session.execute(
            statement.values(
                is_primary=False, updated_at=updated_at, updated_by=actor_id
            ).returning(ProductMedia.id)
        )
        return list(result.scalars().all())

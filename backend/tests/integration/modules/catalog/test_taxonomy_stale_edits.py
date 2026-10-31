"""Category and collection edits reject stale versions on PostgreSQL."""

import os
import uuid

import pytest

from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.auth.models import StaffUser
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.errors import CatalogStaleEditError
from modest_chic_backend.modules.catalog.schemas import (
    CategoryCreate,
    CategoryUpdate,
    CollectionCreate,
    CollectionUpdate,
)
from modest_chic_backend.modules.catalog.service import CatalogService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_category_and_collection_updates_require_current_versions() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    suffix = uuid.uuid4().hex
    try:
        async with database.session() as session:
            async with session.begin():
                actor = StaffUser(email=f"taxonomy-{suffix}@test.local", display_name="Test")
                session.add(actor)
                await session.flush()
                service = CatalogService(session)
                category = await service.create_category(
                    CategoryCreate(slug=f"cat-{suffix}", name="Category"), actor.id
                )
                collection = await service.create_collection(
                    CollectionCreate(slug=f"collection-{suffix}", name="Collection"), actor.id
                )
                category_update = CategoryUpdate(
                    expected_updated_at=category.updated_at,
                    status=ProductStatus.PUBLISHED,
                )
                collection_update = CollectionUpdate(
                    expected_updated_at=collection.updated_at,
                    status=ProductStatus.PUBLISHED,
                )
                updated_category = await service.update_category(
                    category.id, category_update, actor.id
                )
                updated_collection = await service.update_collection(
                    collection.id, collection_update, actor.id
                )
                assert updated_category is not None
                assert updated_collection is not None
                assert updated_category.updated_at > category.updated_at
                assert updated_collection.updated_at > collection.updated_at
                with pytest.raises(CatalogStaleEditError):
                    await service.update_category(category.id, category_update, actor.id)
                with pytest.raises(CatalogStaleEditError):
                    await service.update_collection(collection.id, collection_update, actor.id)
                assert updated_category.status == ProductStatus.PUBLISHED
                assert updated_collection.status == ProductStatus.PUBLISHED
                await session.rollback()
    finally:
        await database.dispose()

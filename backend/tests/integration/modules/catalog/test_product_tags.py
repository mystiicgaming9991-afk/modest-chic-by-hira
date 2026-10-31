"""Product-tag memberships persist and reject invalid replacements."""

import os
import uuid

import pytest

from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.auth.models import StaffUser
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.errors import CatalogStaleEditError
from modest_chic_backend.modules.catalog.models import Product, ProductTag
from modest_chic_backend.modules.catalog.schemas import ProductTagsUpdate
from modest_chic_backend.modules.catalog.service import CatalogService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_product_tags_can_be_assigned_and_cleared() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    suffix = uuid.uuid4().hex
    try:
        async with database.session() as session:
            async with session.begin():
                actor = StaffUser(email=f"tags-{suffix}@test.local", display_name="Test")
                product = Product(
                    slug=f"tags-{suffix}", title="Tag test", status=ProductStatus.DRAFT
                )
                first = ProductTag(name=f"tag-one-{suffix}")
                second = ProductTag(name=f"tag-two-{suffix}")
                session.add_all([actor, product, first, second])
                await session.flush()

                service = CatalogService(session)
                assert await service.get_product_tag_ids(product.id) == []
                initial_version = product.updated_at
                assert await service.set_product_tags(
                    product.id,
                    ProductTagsUpdate(
                        expected_updated_at=initial_version,
                        tag_ids=[first.id, second.id],
                    ),
                    actor.id,
                )
                assert await service.get_product_tag_ids(product.id) == [first.id, second.id]
                with pytest.raises(CatalogStaleEditError):
                    await service.set_product_tags(
                        product.id,
                        ProductTagsUpdate(
                            expected_updated_at=initial_version,
                            tag_ids=[first.id],
                        ),
                        actor.id,
                    )
                with pytest.raises(ValueError, match="only once"):
                    await service.set_product_tags(
                        product.id,
                        ProductTagsUpdate(
                            expected_updated_at=product.updated_at,
                            tag_ids=[first.id, first.id],
                        ),
                        actor.id,
                    )
                with pytest.raises(ValueError, match="does not exist"):
                    await service.set_product_tags(
                        product.id,
                        ProductTagsUpdate(
                            expected_updated_at=product.updated_at,
                            tag_ids=[uuid.uuid4()],
                        ),
                        actor.id,
                    )
                assert await service.set_product_tags(
                    product.id,
                    ProductTagsUpdate(
                        expected_updated_at=product.updated_at,
                        tag_ids=[],
                    ),
                    actor.id,
                )
                assert await service.get_product_tag_ids(product.id) == []
                await session.rollback()
    finally:
        await database.dispose()

"""Existing product media metadata is attached with a traceable audit event."""

import os
import uuid

import pytest
from sqlalchemy import select

from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.audit.models import AuditLog
from modest_chic_backend.modules.auth.models import StaffUser
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.models import Product, ProductMedia, ProductVariant
from modest_chic_backend.modules.catalog.schemas import MediaCreate
from modest_chic_backend.modules.catalog.service import CatalogService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_attach_existing_media_records_metadata_and_actor_audit() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    suffix = uuid.uuid4().hex
    try:
        async with database.session() as session:
            async with session.begin():
                actor = StaffUser(email=f"media-{suffix}@test.local", display_name="Media staff")
                product = Product(
                    slug=f"media-{suffix}", title="Media test product", status=ProductStatus.DRAFT
                )
                unrelated_product = Product(
                    slug=f"other-media-{suffix}",
                    title="Other media test product",
                    status=ProductStatus.DRAFT,
                )
                session.add_all([actor, product, unrelated_product])
                await session.flush()
                unrelated_variant = ProductVariant(
                    product_id=unrelated_product.id,
                    sku=f"media-{suffix}",
                    color_name="Blue",
                    price_minor=100,
                )
                session.add(unrelated_variant)
                await session.flush()

                service = CatalogService(session)
                with pytest.raises(ValueError, match="must belong to the selected product"):
                    await service.attach_media(
                        product.id,
                        MediaCreate(
                            object_key="products/test/wrong-product.webp",
                            media_type="image/webp",
                            variant_id=unrelated_variant.id,
                        ),
                        actor.id,
                    )
                first = await service.attach_media(
                    product.id,
                    MediaCreate(
                        object_key="products/test/front-old.webp",
                        media_type="image/webp",
                        alt_text="Previous front view",
                        width=800,
                        height=1000,
                        sort_order=0,
                        is_primary=True,
                    ),
                    actor.id,
                )
                assert first is not None
                result = await service.attach_media(
                    product.id,
                    MediaCreate(
                        object_key="products/test/front.webp",
                        media_type="image/webp",
                        alt_text="Front view",
                        width=800,
                        height=1000,
                        sort_order=1,
                        is_primary=True,
                    ),
                    actor.id,
                )

                assert result is not None
                assert result.object_key == "products/test/front.webp"
                assert result.alt_text == "Front view"
                assert result.is_primary is True
                media = await session.get(ProductMedia, result.id)
                assert media is not None
                assert media.created_by == actor.id
                previous_media = await session.get(ProductMedia, first.id)
                assert previous_media is not None
                await session.refresh(previous_media)
                assert previous_media.is_primary is False
                assert previous_media.updated_by == actor.id
                audit = await session.scalar(
                    select(AuditLog).where(
                        AuditLog.action == "catalog.media_attached",
                        AuditLog.entity_id == result.id,
                    )
                )
                assert audit is not None
                assert audit.actor_id == actor.id
                assert audit.entity_type == "product_media"
                assert audit.event_metadata == {
                    "product_id": str(product.id),
                    "variant_id": None,
                    "media_type": "image/webp",
                    "sort_order": 1,
                    "is_primary": True,
                    "replaced_primary_ids": [str(first.id)],
                }
                await session.rollback()
    finally:
        await database.dispose()

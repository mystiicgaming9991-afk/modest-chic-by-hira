import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.errors import CatalogStaleEditError
from modest_chic_backend.modules.catalog.schemas import ProductUpdate, VariantUpdate
from modest_chic_backend.modules.catalog.service import CatalogService


async def test_product_update_rejects_a_stale_version() -> None:
    service = CatalogService(AsyncMock())
    current_time = datetime.now(UTC)
    service._repo.get_product_for_update = AsyncMock(
        return_value=SimpleNamespace(updated_at=current_time)
    )
    service._repo.update_product = AsyncMock()
    payload = ProductUpdate(expected_updated_at=current_time - timedelta(seconds=1), title="New")

    with pytest.raises(CatalogStaleEditError):
        await service.update_product(uuid.uuid4(), payload, uuid.uuid4())

    service._repo.update_product.assert_not_awaited()


async def test_variant_update_rejects_a_stale_version() -> None:
    service = CatalogService(AsyncMock())
    current_time = datetime.now(UTC)
    service._repo.get_variant_for_update = AsyncMock(
        return_value=SimpleNamespace(updated_at=current_time)
    )
    service._repo.update_variant = AsyncMock()
    payload = VariantUpdate(
        expected_updated_at=current_time - timedelta(seconds=1), price_minor=12000
    )

    with pytest.raises(CatalogStaleEditError):
        await service.update_variant(uuid.uuid4(), payload, uuid.uuid4())

    service._repo.update_variant.assert_not_awaited()


async def test_generic_product_update_cannot_archive() -> None:
    service = CatalogService(AsyncMock())
    current_time = datetime.now(UTC)
    service._repo.get_product_for_update = AsyncMock(
        return_value=SimpleNamespace(updated_at=current_time)
    )
    service._repo.update_product = AsyncMock()
    payload = ProductUpdate(
        expected_updated_at=current_time,
        status=ProductStatus.ARCHIVED,
    )

    with pytest.raises(ValueError, match="archive products through the archive action"):
        await service.update_product(uuid.uuid4(), payload, uuid.uuid4())

    service._repo.update_product.assert_not_awaited()


async def test_product_cannot_be_published_without_an_active_variant() -> None:
    service = CatalogService(AsyncMock())
    current_time = datetime.now(UTC)
    service._repo.get_product_for_update = AsyncMock(
        return_value=SimpleNamespace(updated_at=current_time)
    )
    service._repo.active_variant_count = AsyncMock(return_value=0)
    service._repo.update_product = AsyncMock()
    payload = ProductUpdate(expected_updated_at=current_time, status=ProductStatus.PUBLISHED)

    with pytest.raises(ValueError, match="active variant"):
        await service.update_product(uuid.uuid4(), payload, uuid.uuid4())

    service._repo.update_product.assert_not_awaited()

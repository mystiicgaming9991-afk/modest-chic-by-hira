"""PostgreSQL coverage for staff inventory reads and movement commands."""

import os
import uuid

import pytest
from sqlalchemy import func, select

from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.analytics.repository import AnalyticsRepository
from modest_chic_backend.modules.audit.models import AuditLog
from modest_chic_backend.modules.auth.models import Permission, Role, StaffUser, role_permissions
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.models import Product, ProductVariant
from modest_chic_backend.modules.inventory.enums import MovementReason
from modest_chic_backend.modules.inventory.models import InventoryLocation
from modest_chic_backend.modules.inventory.service import InventoryService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_staff_inventory_reads_and_adjustment_ledger() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    suffix = uuid.uuid4().hex
    try:
        async with database.session() as session:
            async with session.begin():
                actor = StaffUser(email=f"inventory-{suffix}@test.local", display_name="Test")
                product = Product(
                    slug=f"inventory-{suffix}",
                    title="Inventory test product",
                    status=ProductStatus.PUBLISHED,
                )
                location = InventoryLocation(key=f"inventory-{suffix}", name="Test Warehouse")
                session.add_all([actor, product, location])
                await session.flush()
                variant = ProductVariant(
                    product_id=product.id,
                    sku=f"INV-{suffix}",
                    color_name="Rose",
                    price_minor=10000,
                    is_active=True,
                )
                session.add(variant)
                await session.flush()

                service = InventoryService(session)
                threshold_grants = await session.execute(
                    select(Role.key, Permission.key)
                    .select_from(Role)
                    .join(role_permissions, role_permissions.c.role_id == Role.id)
                    .join(Permission, Permission.id == role_permissions.c.permission_id)
                    .where(
                        Role.key.in_(["owner", "warehouse"]),
                        Permission.key == "inventory.thresholds.manage",
                    )
                )
                assert set(threshold_grants.all()) == {
                    ("owner", "inventory.thresholds.manage"),
                    ("warehouse", "inventory.thresholds.manage"),
                }
                received = await service.receive_stock(
                    variant.id, location.key, 8, actor.id, f"receive-{suffix}"
                )
                adjusted = await service.adjust_stock(
                    variant.id,
                    uuid.UUID(str(received["location_id"])),
                    -2,
                    MovementReason.ADJUST,
                    actor.id,
                    f"adjust-{suffix}",
                    "Cycle count correction",
                )
                balances = await service.list_balances(variant_id=variant.id)
                movements = await service.list_movements(variant_id=variant.id)
                variants = await service.list_variants()
                locations = await service.list_locations()

                assert adjusted["on_hand"] == 6
                assert adjusted["available"] == 6
                assert balances[0]["product_title"] == product.title
                assert balances[0]["sku"] == variant.sku
                assert balances[0]["on_hand"] == 6
                assert any(row["id"] == str(variant.id) for row in variants)
                assert any(row["key"] == location.key for row in locations)
                assert [movement["delta_on_hand"] for movement in movements["items"]] == [-2, 8]
                assert movements["items"][0]["notes"] == "Cycle count correction"
                assert movements["items"][0]["actor_id"] == str(actor.id)

                location_id = uuid.UUID(str(received["location_id"]))
                await service.set_low_stock_threshold(
                    variant_id=variant.id,
                    location_id=location_id,
                    threshold=5,
                    actor_id=actor.id,
                )
                low_stock = await service.low_stock_balances(limit=100)
                assert not any(row["sku"] == variant.sku for row in low_stock["items"])

                await service.set_low_stock_threshold(
                    variant_id=variant.id,
                    location_id=location_id,
                    threshold=6,
                    actor_id=actor.id,
                )
                await service.set_low_stock_threshold(
                    variant_id=variant.id,
                    location_id=location_id,
                    threshold=6,
                    actor_id=actor.id,
                )
                low_stock = await service.low_stock_balances(limit=100)
                alert_row = next(row for row in low_stock["items"] if row["sku"] == variant.sku)
                assert alert_row["available"] == 6
                assert alert_row["low_stock_threshold"] == 6
                assert (
                    low_stock["total_count"]
                    == await AnalyticsRepository(session).low_stock_balance_count()
                )
                audit_count = await session.scalar(
                    select(func.count(AuditLog.id)).where(
                        AuditLog.action == "inventory.low_stock_threshold.updated",
                        AuditLog.entity_type == "inventory_balance",
                        AuditLog.actor_id == actor.id,
                    )
                )
                assert audit_count == 2

                await service.adjust_stock(
                    variant.id,
                    location_id,
                    -6,
                    MovementReason.ADJUST,
                    actor.id,
                    f"deplete-{suffix}",
                    "Verified empty location",
                )
                unavailable = await service.zero_available_balances(limit=100)
                assert unavailable["total_count"] >= 1
                target = next(row for row in unavailable["items"] if row["sku"] == variant.sku)
                assert target["available"] == 0
                assert (
                    unavailable["total_count"]
                    == await AnalyticsRepository(session).zero_available_balance_count()
                )
                low_stock = await service.low_stock_balances(limit=100)
                low_stock_row = next(row for row in low_stock["items"] if row["sku"] == variant.sku)
                assert low_stock_row["available"] == 0
                await session.rollback()
    finally:
        await database.dispose()

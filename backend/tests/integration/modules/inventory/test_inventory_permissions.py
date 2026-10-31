"""Staff role permissions for inventory alerts are enforced at the API boundary."""

import asyncio
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from modest_chic_backend.core.settings import Settings
from modest_chic_backend.db.database import Database
from modest_chic_backend.main import create_app
from modest_chic_backend.modules.auth.models import (
    Role,
    StaffStatus,
    StaffUser,
    staff_user_roles,
)
from modest_chic_backend.modules.auth.security import hash_password
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.models import Product, ProductVariant
from modest_chic_backend.modules.inventory.models import InventoryBalance, InventoryLocation

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


def _client() -> TestClient:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=os.environ["TEST_DATABASE_URL"],
        redis_url=os.environ.get("TEST_REDIS_URL", "redis://localhost:56379/0"),
        jwt_signing_key="j" * 32,
        csrf_signing_key="c" * 32,
        totp_encryption_key="t" * 32,
        outbox_encryption_key="o" * 32,
        trusted_origins=["http://localhost:3000"],
        admin_base_url="http://localhost:3000/admin",
        email_provider="console",
        email_from="admin@localhost",
    )
    return TestClient(create_app(settings))


async def _seed_permission_journey(suffix: str) -> tuple[dict[str, str], uuid.UUID, uuid.UUID]:
    database = Database(os.environ["TEST_DATABASE_URL"])
    password = "valid-password-value-77"
    emails = {
        role_key: f"inventory-{role_key}-{suffix}@test.local"
        for role_key in ("warehouse", "marketing")
    }
    try:
        async with database.transaction() as session:
            users: dict[str, StaffUser] = {}
            for role_key, email in emails.items():
                user = StaffUser(
                    email=email,
                    display_name=f"{role_key.title()} Test",
                    hashed_password=hash_password(password),
                    status=StaffStatus.ACTIVE,
                )
                session.add(user)
                await session.flush()
                role = await session.scalar(select(Role).where(Role.key == role_key))
                assert role is not None
                await session.execute(
                    staff_user_roles.insert().values(
                        staff_user_id=user.id,
                        role_id=role.id,
                        assigned_by=user.id,
                    )
                )
                users[role_key] = user

            product = Product(
                slug=f"permission-{suffix}",
                title="Permission inventory product",
                status=ProductStatus.PUBLISHED,
            )
            location = InventoryLocation(key=f"permission-{suffix}", name="Test warehouse")
            session.add_all([product, location])
            await session.flush()
            variant = ProductVariant(
                product_id=product.id,
                sku=f"PERM-{suffix}",
                color_name="Rose",
                price_minor=10000,
                is_active=True,
            )
            session.add(variant)
            await session.flush()
            balance = InventoryBalance(
                variant_id=variant.id,
                location_id=location.id,
                on_hand=0,
                reserved=0,
            )
            session.add(balance)
            await session.flush()
            balance_ids = (variant.id, location.id)
    finally:
        await database.dispose()
    return emails, balance_ids[0], balance_ids[1]


def _login(client: TestClient, email: str) -> dict[str, str]:
    csrf_response = client.get("/api/v1/auth/csrf")
    csrf_token = csrf_response.cookies.get("mc_csrf")
    assert csrf_token
    headers = {"Origin": "http://localhost:3000", "X-CSRF-Token": csrf_token}
    login = client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": "valid-password-value-77"},
    )
    assert login.status_code == 200
    return {**headers, "Authorization": f"Bearer {login.json()['access_token']}"}


def test_inventory_permissions_control_alert_edit_and_dashboard_visibility() -> None:
    suffix = uuid.uuid4().hex
    emails, variant_id, location_id = asyncio.run(_seed_permission_journey(suffix))

    with _client() as client:
        marketing_headers = _login(client, emails["marketing"])
        marketing_dashboard = client.get(
            "/api/v1/admin/analytics/dashboard", headers=marketing_headers
        )
        denied_list = client.get("/api/v1/admin/inventory/low-stock", headers=marketing_headers)
        denied_edit = client.patch(
            "/api/v1/admin/inventory/thresholds",
            headers=marketing_headers,
            json={
                "variant_id": str(variant_id),
                "location_id": str(location_id),
                "threshold": 5,
            },
        )

    assert marketing_dashboard.status_code == 200
    assert "low_stock_inventory" not in marketing_dashboard.json()["queues"]
    assert denied_list.status_code == 403
    assert denied_edit.status_code == 403

    with _client() as client:
        warehouse_headers = _login(client, emails["warehouse"])
        updated = client.patch(
            "/api/v1/admin/inventory/thresholds",
            headers=warehouse_headers,
            json={
                "variant_id": str(variant_id),
                "location_id": str(location_id),
                "threshold": 5,
            },
        )
        low_stock = client.get("/api/v1/admin/inventory/low-stock", headers=warehouse_headers)
        dashboard = client.get("/api/v1/admin/analytics/dashboard", headers=warehouse_headers)

    assert updated.status_code == 200
    assert updated.json()["low_stock_threshold"] == 5
    assert low_stock.status_code == 200
    assert low_stock.json()["total_count"] >= 1
    assert any(row["variant_id"] == str(variant_id) for row in low_stock.json()["items"])
    assert dashboard.status_code == 200
    assert dashboard.json()["queues"]["low_stock_inventory"] >= 1

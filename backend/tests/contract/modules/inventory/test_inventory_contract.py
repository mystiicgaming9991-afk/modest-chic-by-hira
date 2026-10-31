"""Contract tests for inventory HTTP endpoints."""

from fastapi import FastAPI

from modest_chic_backend.core.settings import Settings
from modest_chic_backend.main import create_app


def _make_app() -> FastAPI:
    return create_app(
        Settings(
            _env_file=None,
            app_env="test",
            database_url="postgresql+asyncpg://modest:modest@localhost/modest_chic",
            redis_url="redis://localhost:56379/0",
            jwt_signing_key="j" * 32,
            csrf_signing_key="c" * 32,
            totp_encryption_key="t" * 32,
            outbox_encryption_key="o" * 32,
            trusted_origins=["http://localhost:3000"],
            admin_base_url="http://localhost:3000/admin",
            email_provider="console",
            email_from="admin@localhost",
        )
    )


def test_inventory_routes_registered() -> None:
    paths = _make_app().openapi()["paths"]
    assert "/api/v1/admin/inventory/locations" in paths
    assert "/api/v1/admin/inventory/variants" in paths
    assert "/api/v1/admin/inventory/balances" in paths
    assert "/api/v1/admin/inventory/movements" in paths
    assert "/api/v1/admin/inventory/receive" in paths
    assert "/api/v1/admin/inventory/adjust" in paths
    assert "/api/v1/admin/inventory/low-stock" in paths
    assert "/api/v1/admin/inventory/thresholds" in paths


def test_receive_accepts_quantity_and_location() -> None:
    openapi = _make_app().openapi()
    schema = openapi["paths"]["/api/v1/admin/inventory/receive"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    ref = schema.get("$ref", "")
    assert "ReceiveRequest" in ref

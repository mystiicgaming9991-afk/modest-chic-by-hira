"""Contract tests for guest cart endpoints."""

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


def test_cart_routes_are_public() -> None:
    paths = _make_app().openapi()["paths"]
    assert "/api/v1/cart" in paths
    assert "/api/v1/cart/items" in paths
    assert "/api/v1/cart/items/{item_id}" in paths


def test_cart_get_returns_cart_schema() -> None:
    openapi = _make_app().openapi()
    response = openapi["paths"]["/api/v1/cart"]["get"]["responses"]["200"]
    assert response is not None

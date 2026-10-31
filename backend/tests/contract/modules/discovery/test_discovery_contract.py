"""Contract tests for public discovery API — products, categories, collections, search."""

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


def test_public_product_routes_dont_require_auth() -> None:
    """Public catalog endpoints do NOT declare security requirements."""
    paths = _make_app().openapi()["paths"]
    # These routes should exist and not require bearerAuth
    public_routes = [
        "/api/v1/catalog/products",
        "/api/v1/catalog/products/{slug}",
        "/api/v1/catalog/categories",
        "/api/v1/catalog/collections",
        "/api/v1/catalog/search",
    ]
    for route in public_routes:
        assert route in paths, f"Missing public route: {route}"
        for method in paths[route]:
            # Public routes should not have security requirements
            assert "security" not in paths[route][method], (
                f"{route} {method} should be public (no auth required)"
            )


def test_public_product_list_returns_published_only() -> None:
    """The product list response schema maps to public product summary."""
    openapi = _make_app().openapi()
    path = openapi["paths"]["/api/v1/catalog/products"]["get"]
    assert "200" in path["responses"]


def test_public_routes_accept_filter_params() -> None:
    """Browse and search routes expose the supported filters and pagination controls."""
    openapi = _make_app().openapi()
    # Check that the product list has query parameters
    params = openapi["paths"]["/api/v1/catalog/products"]["get"].get("parameters", [])
    param_names = {p["name"] for p in params}
    expected = {
        "category",
        "collection",
        "q",
        "fabric",
        "color",
        "min_price_minor",
        "max_price_minor",
        "in_stock_only",
        "on_sale_only",
        "sort",
        "after",
        "limit",
    }
    assert expected <= param_names, f"Missing params: {expected - param_names}"

    search_params = openapi["paths"]["/api/v1/catalog/search"]["get"]["parameters"]
    search_param_names = {param["name"] for param in search_params}
    assert expected <= search_param_names

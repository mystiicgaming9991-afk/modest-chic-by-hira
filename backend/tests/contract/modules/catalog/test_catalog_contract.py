"""Contract tests for catalog HTTP endpoints."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modest_chic_backend.api.v1.catalog import router as catalog_router
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


def test_catalog_routes_registered() -> None:
    paths = _make_app().openapi()["paths"]
    expected = [
        "/api/v1/admin/catalog/products",
        "/api/v1/admin/catalog/products/{product_id}",
        "/api/v1/admin/catalog/products/{product_id}/archive",
        "/api/v1/admin/catalog/products/{product_id}/variants",
        "/api/v1/admin/catalog/products/{product_id}/categories",
        "/api/v1/admin/catalog/products/{product_id}/tags",
        "/api/v1/admin/catalog/variants/{variant_id}",
        "/api/v1/admin/catalog/categories",
        "/api/v1/admin/catalog/categories/{category_id}",
        "/api/v1/admin/catalog/collections",
        "/api/v1/admin/catalog/collections/{collection_id}",
        "/api/v1/admin/catalog/collections/{collection_id}/products",
        "/api/v1/admin/catalog/tags",
        "/api/v1/admin/catalog/products/{product_id}/media",
    ]
    for path in expected:
        assert path in paths
    assert set(paths["/api/v1/admin/catalog/products/{product_id}/media"]) == {"post"}
    assert "get" in paths["/api/v1/admin/catalog/collections/{collection_id}/products"]
    assert "put" in paths["/api/v1/admin/catalog/collections/{collection_id}/products"]
    assert "get" in paths["/api/v1/admin/catalog/products/{product_id}/categories"]
    assert "put" in paths["/api/v1/admin/catalog/products/{product_id}/categories"]
    assert "get" in paths["/api/v1/admin/catalog/products/{product_id}/tags"]
    assert "put" in paths["/api/v1/admin/catalog/products/{product_id}/tags"]
    assert "201" in paths["/api/v1/admin/catalog/products/{product_id}/media"]["post"]["responses"]


def test_product_schema_has_required_fields() -> None:
    schemas = _make_app().openapi()["components"]["schemas"]
    assert "ProductRead" in schemas
    assert "ProductDetail" in schemas
    assert "ProductCreate" in schemas
    assert "VariantRead" in schemas
    assert "CategoryRead" in schemas
    assert "CollectionRead" in schemas
    assert "TagRead" in schemas
    assert "MediaRead" in schemas


def test_post_product_returns_201() -> None:
    openapi = _make_app().openapi()
    responses = openapi["paths"]["/api/v1/admin/catalog/products"]["post"]["responses"]
    assert "201" in responses


def test_patch_product_accepts_product_update() -> None:
    openapi = _make_app().openapi()
    path = openapi["paths"]["/api/v1/admin/catalog/products/{product_id}"]
    assert "patch" in path
    assert "200" in path["patch"]["responses"]
    required = openapi["components"]["schemas"]["ProductUpdate"]["required"]
    assert "expected_updated_at" in required
    variant_update_required = openapi["components"]["schemas"]["VariantUpdate"]["required"]
    assert "expected_updated_at" in variant_update_required
    schemas = openapi["components"]["schemas"]
    for schema_name in (
        "CategoryUpdate",
        "CollectionUpdate",
        "ProductCategoriesUpdate",
        "ProductTagsUpdate",
        "CollectionProductsUpdate",
    ):
        assert "expected_updated_at" in schemas[schema_name]["required"]


def test_archive_product_requires_dedicated_action() -> None:
    openapi = _make_app().openapi()
    path = openapi["paths"]["/api/v1/admin/catalog/products/{product_id}/archive"]
    assert "post" in path
    assert "201" not in path["post"]["responses"]


def test_catalog_resource_paths_reject_malformed_uuids_as_validation_errors() -> None:
    application = _make_app()
    products_route = next(
        route
        for route in catalog_router.routes
        if route.path == "/admin/catalog/products/{product_id}" and "GET" in route.methods
    )
    permission_dependency = products_route.dependant.dependencies[0].call
    application.dependency_overrides[permission_dependency] = lambda: None

    with TestClient(application) as client:
        response = client.get("/api/v1/admin/catalog/products/not-a-uuid")

    assert response.status_code == 422

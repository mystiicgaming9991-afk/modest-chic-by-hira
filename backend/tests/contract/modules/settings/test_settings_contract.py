"""Contract tests for store settings HTTP endpoints."""

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


def test_settings_routes_are_registered_in_openapi() -> None:
    """The settings endpoints appear in the OpenAPI schema."""
    paths = _make_app().openapi()["paths"]
    assert "/api/v1/admin/settings" in paths
    assert "/api/v1/admin/settings/secrets" in paths
    assert "/api/v1/admin/settings/secrets/{key}" in paths


def test_get_settings_returns_a_list_response() -> None:
    """GET /admin/settings returns a response with items array."""
    openapi = _make_app().openapi()
    response = openapi["paths"]["/api/v1/admin/settings"]["get"]["responses"]["200"]
    schema = response["content"]["application/json"]["schema"]
    # The response wraps items; the schema is a $ref to StoreSettingListResponse
    assert "$ref" in schema or "properties" in schema


def test_put_settings_accepts_store_setting_update() -> None:
    """PUT /admin/settings accepts StoreSettingUpdate body."""
    openapi = _make_app().openapi()
    schema = openapi["paths"]["/api/v1/admin/settings"]["put"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    # Schema is a $ref to StoreSettingUpdate
    assert "$ref" in schema
    assert "StoreSettingUpdate" in schema["$ref"]


def test_put_secrets_accepts_store_setting_secret_update() -> None:
    """PUT /admin/settings/secrets accepts StoreSettingSecretUpdate body."""
    openapi = _make_app().openapi()
    schema = openapi["paths"]["/api/v1/admin/settings/secrets"]["put"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert "$ref" in schema
    assert "StoreSettingSecretUpdate" in schema["$ref"]


def test_setting_read_schema_exists() -> None:
    """The StoreSettingRead schema is present in component schemas."""
    openapi = _make_app().openapi()
    schemas = openapi["components"]["schemas"]
    assert "StoreSettingRead" in schemas
    props = schemas["StoreSettingRead"]["properties"]
    assert props["key"]["type"] == "string"
    assert props["version"]["type"] == "integer"


def test_secret_setting_read_response_schema_exists() -> None:
    """SecretSettingReadResponse has key and value fields."""
    openapi = _make_app().openapi()
    schemas = openapi["components"]["schemas"]
    assert "SecretSettingReadResponse" in schemas
    props = schemas["SecretSettingReadResponse"]["properties"]
    assert "key" in props
    assert "value" in props

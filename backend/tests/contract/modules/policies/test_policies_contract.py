"""Contract tests for policy version HTTP endpoints."""

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


def test_policies_routes_are_registered_in_openapi() -> None:
    """The policies endpoints appear in the OpenAPI schema."""
    paths = _make_app().openapi()["paths"]
    assert "/api/v1/admin/policies" in paths
    assert "/api/v1/admin/policies/{type}/effective" in paths
    assert "/api/v1/policies/{policy_type}" in paths


def test_post_policies_returns_201() -> None:
    """POST /admin/policies returns 201 on success."""
    openapi = _make_app().openapi()
    responses = openapi["paths"]["/api/v1/admin/policies"]["post"]["responses"]
    assert "201" in responses
    schema = responses["201"]["content"]["application/json"]["schema"]
    assert "$ref" in schema
    assert "PolicyVersionRead" in schema["$ref"]


def test_get_policies_returns_list() -> None:
    """GET /admin/policies returns a PolicyVersionListResponse."""
    openapi = _make_app().openapi()
    response = openapi["paths"]["/api/v1/admin/policies"]["get"]["responses"]["200"]
    schema = response["content"]["application/json"]["schema"]
    assert "$ref" in schema
    assert "PolicyVersionListResponse" in schema["$ref"]


def test_get_effective_returns_policy_version_read() -> None:
    """GET /admin/policies/{type}/effective returns a PolicyVersionRead."""
    openapi = _make_app().openapi()
    responses = openapi["paths"]["/api/v1/admin/policies/{type}/effective"]["get"]["responses"]
    assert "200" in responses
    schema = responses["200"]["content"]["application/json"]["schema"]
    assert "$ref" in schema
    assert "PolicyVersionRead" in schema["$ref"]
    # 404 is raised dynamically via ApplicationError; it goes through the exception handler


def test_policy_version_read_schema_exists() -> None:
    """The PolicyVersionRead schema is present with required fields."""
    openapi = _make_app().openapi()
    schemas = openapi["components"]["schemas"]
    assert "PolicyVersionRead" in schemas
    props = schemas["PolicyVersionRead"]["properties"]
    required_fields = {
        "id",
        "type",
        "version",
        "effective_from",
        "content",
        "approved_by",
        "created_at",
    }
    assert set(props.keys()) == required_fields


def test_post_policies_accepts_policy_version_publish_schema() -> None:
    """POST /admin/policies accepts PolicyVersionPublish body."""
    openapi = _make_app().openapi()
    schema = openapi["paths"]["/api/v1/admin/policies"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert "$ref" in schema
    assert "PolicyVersionPublish" in schema["$ref"]

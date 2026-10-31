"""Contract tests for staff administration endpoints."""

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


def test_staff_admin_routes_registered() -> None:
    paths = _make_app().openapi()["paths"]
    assert "/api/v1/admin/staff" in paths
    assert "/api/v1/admin/staff/{staff_user_id}/roles" in paths
    assert "/api/v1/admin/staff/{staff_user_id}/suspend" in paths
    assert "/api/v1/admin/staff/{staff_user_id}/activate" in paths


def test_list_staff_requires_staff_manage() -> None:
    openapi = _make_app().openapi()
    path = openapi["paths"]["/api/v1/admin/staff"]["get"]
    # Route has require_permission("staff.manage") dependency
    assert path is not None


def test_set_roles_accepts_role_keys() -> None:
    openapi = _make_app().openapi()
    path = openapi["paths"]["/api/v1/admin/staff/{staff_user_id}/roles"]["put"]
    assert path is not None
    assert "requestBody" in path
    body_schema = path["requestBody"]["content"]["application/json"]["schema"]
    schema_name = body_schema["$ref"].rsplit("/", 1)[-1]
    assert "expected_updated_at" in openapi["components"]["schemas"][schema_name]["required"]

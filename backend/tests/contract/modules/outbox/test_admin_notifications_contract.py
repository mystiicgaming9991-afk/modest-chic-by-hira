"""Contract coverage for staff notification status inspection."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modest_chic_backend.api.v1.dependencies import require_staff_identity
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


def test_staff_outbox_status_route_is_registered_with_bounded_pagination() -> None:
    operation = _make_app().openapi()["paths"]["/api/v1/admin/notifications/outbox"]["get"]

    assert {parameter["name"] for parameter in operation["parameters"]} == {
        "status",
        "limit",
        "offset",
    }


def test_outbox_status_route_requires_notification_read_permission() -> None:
    application = _make_app()
    application.dependency_overrides[require_staff_identity] = lambda: SimpleNamespace(
        permission_keys=["order.read"]
    )

    with TestClient(application) as client:
        response = client.get("/api/v1/admin/notifications/outbox")

    assert response.status_code == 403

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from modest_chic_backend.core.settings import Settings
from modest_chic_backend.main import create_app


def settings() -> Settings:
    return Settings(
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


def test_csrf_bootstrap_sets_signed_readable_cookie_without_body() -> None:
    with TestClient(create_app(settings())) as client:
        response = client.get("/api/v1/auth/csrf")

    assert response.status_code == 204
    assert response.content == b""
    cookie = response.cookies.get("mc_csrf")
    assert cookie
    assert "HttpOnly" not in response.headers["set-cookie"]
    assert "Path=/" in response.headers["set-cookie"]


def test_auth_mutation_rejects_missing_csrf_proof() -> None:
    with TestClient(create_app(settings())) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers={"Origin": "http://localhost:3000"},
            json={"email": "staff@example.com", "password": "correct-horse-battery"},
        )

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_ORIGIN_REJECTED"


def test_auth_mutation_rejects_untrusted_origin_even_with_csrf_cookie() -> None:
    with TestClient(create_app(settings())) as client:
        csrf_response = client.get("/api/v1/auth/csrf")
        csrf_token = csrf_response.cookies.get("mc_csrf")
        response = client.post(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://attacker.example",
                "X-CSRF-Token": csrf_token or "",
            },
            json={"email": "staff@example.com", "password": "correct-horse-battery"},
        )

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_ORIGIN_REJECTED"


def test_live_health_does_not_require_database_connection() -> None:
    with TestClient(create_app(settings())) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_reports_unavailable_dependencies_without_failing_liveness() -> None:
    application = create_app(settings())

    @asynccontextmanager
    async def unavailable_database_session():
        yield SimpleNamespace(connection=AsyncMock(side_effect=OSError("database down")))

    with TestClient(application) as client:
        application.state.database = SimpleNamespace(session=unavailable_database_session)
        application.state.redis = SimpleNamespace(ping=AsyncMock(side_effect=OSError("redis down")))

        readiness = client.get("/health/ready")
        liveness = client.get("/health")

    assert readiness.status_code == 503
    assert readiness.json() == {
        "status": "not_ready",
        "database": "unavailable",
        "redis": "unavailable",
    }
    assert liveness.status_code == 200

from modest_chic_backend.core.settings import Settings
from modest_chic_backend.main import create_app


def test_openapi_exposes_reviewed_staff_invitation_and_login_paths() -> None:
    application = create_app(
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
    paths = application.openapi()["paths"]

    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/accept-invitation" in paths
    assert "/api/v1/admin/staff/invitations" in paths
    assert "/api/v1/auth/invitations" not in paths


def test_login_contract_never_returns_refresh_token_in_json() -> None:
    application = create_app(
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
    openapi = application.openapi()
    response_schema = openapi["paths"]["/api/v1/auth/login"]["post"]["responses"]["200"]
    session_schema = response_schema["content"]["application/json"]["schema"]["$ref"]

    assert session_schema == "#/components/schemas/SessionResponse"
    session_properties = openapi["components"]["schemas"]["SessionResponse"]["properties"]
    assert "refresh_token" not in session_properties

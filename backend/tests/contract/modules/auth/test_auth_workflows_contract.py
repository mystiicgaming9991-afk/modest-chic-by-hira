from modest_chic_backend.core.settings import Settings
from modest_chic_backend.main import create_app


def test_session_recovery_totp_and_invitation_routes_match_contract() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+asyncpg://modest:modest@localhost:55532/modest_chic_test",
        redis_url="redis://localhost:56379/0",
        jwt_signing_key="j" * 32,
        csrf_signing_key="c" * 32,
        totp_encryption_key="t" * 32,
        outbox_encryption_key="o" * 32,
        trusted_origins=["http://localhost:3000"],
        admin_base_url="http://localhost:3000/admin",
        email_from="admin@localhost",
    )
    paths = create_app(settings).openapi()["paths"]
    expected_statuses = {
        ("/api/v1/auth/me", "get"): "200",
        ("/api/v1/auth/refresh", "post"): "200",
        ("/api/v1/auth/logout", "post"): "204",
        ("/api/v1/auth/password/forgot", "post"): "202",
        ("/api/v1/auth/password/reset", "post"): "204",
        ("/api/v1/auth/password/change", "post"): "204",
        ("/api/v1/auth/setup-totp", "post"): "200",
        ("/api/v1/auth/verify-totp", "post"): "204",
        ("/api/v1/admin/staff/invitations", "post"): "202",
    }

    for (path, method), status in expected_statuses.items():
        assert status in paths[path][method]["responses"]

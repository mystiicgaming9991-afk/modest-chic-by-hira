"""Customer account management and self-service consent route contracts."""

from modest_chic_backend.core.settings import Settings
from modest_chic_backend.main import create_app


def test_customer_account_status_and_marketing_withdrawal_routes_are_exposed() -> None:
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
    assert "post" in paths["/api/v1/admin/customers/{customer_id}/account-status"]
    consent = paths["/api/v1/customer-auth/consents/marketing-email"]
    assert {"get", "post"} <= consent.keys()
    assert set(paths["/api/v1/admin/customers/{customer_id}/consents/marketing-email"]) == {"get"}
    address_edit = paths["/api/v1/admin/customers/{customer_id}/addresses/{address_id}"]
    assert set(address_edit) == {"patch"}
    schema = address_edit["patch"]["requestBody"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("/UpdateAddressRequest")

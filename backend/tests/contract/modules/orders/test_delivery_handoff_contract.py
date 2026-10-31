"""Contract for the permissioned, idempotent delivery handoff command."""

from modest_chic_backend.core.settings import Settings
from modest_chic_backend.main import create_app


def test_delivery_handoff_route_requires_an_idempotency_key() -> None:
    app = create_app(
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
    openapi = app.openapi()
    path = openapi["paths"]["/api/v1/admin/orders/{order_id}/handoff"]["post"]
    schema_ref = path["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema_name = schema_ref.rsplit("/", 1)[-1]
    schema = openapi["components"]["schemas"][schema_name]

    assert "idempotency_key" in schema["required"]


def test_order_cancellation_requires_a_reason_and_idempotency_key() -> None:
    app = create_app(
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
    operation = app.openapi()["paths"]["/api/v1/admin/orders/{order_id}/cancel"]["post"]
    schema_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema = app.openapi()["components"]["schemas"][schema_ref.rsplit("/", 1)[-1]]

    assert set(schema["required"]) == {"idempotency_key", "reason"}


def test_cod_contact_attempt_requires_an_idempotency_key() -> None:
    app = create_app(
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
    operation = app.openapi()["paths"]["/api/v1/admin/orders/cod/{order_id}/contact-attempts"][
        "post"
    ]
    schema_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema = app.openapi()["components"]["schemas"][schema_ref.rsplit("/", 1)[-1]]

    assert "idempotency_key" in schema["required"]

"""Public checkout and private order routes are registered."""

from modest_chic_backend.core.settings import Settings
from modest_chic_backend.main import create_app


def test_checkout_routes_are_exposed() -> None:
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
    paths = app.openapi()["paths"]
    assert "post" in paths["/api/v1/checkout/quote"]
    assert "post" in paths["/api/v1/checkout/orders"]
    assert "get" in paths["/api/v1/orders/{order_id}"]
    schemas = app.openapi()["components"]["schemas"]
    order_request = schemas["PlaceOrderRequest"]
    assert "policy_version_ids" in order_request["required"]
    assert "policy_version_id" not in order_request["properties"]
    assert set(schemas["PolicyVersionIds"]["required"]) == {
        "checkout_bundle",
        "shipping",
        "returns",
    }

"""Order credentials cannot exceed their explicit action scopes."""

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import Request
from pydantic import SecretStr

from modest_chic_backend.api.v1.checkout import private_order
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.checkout.models import OrderAccessToken
from modest_chic_backend.modules.orders.service import OrderService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_private_order_requires_order_read_scope() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    raw_token = "review-only-" + uuid.uuid4().hex
    try:
        async with database.transaction() as session:
            order = await OrderService(session).create_order(
                customer_name="Scope Buyer",
                customer_phone="03000000000",
                fulfillment_method="PICKUP",
                payment_method="COD",
                items=[],
                subtotal_minor=0,
                total_minor=0,
                checkout_idempotency_key="scope-test-" + uuid.uuid4().hex,
            )
            order_id = uuid.UUID(order["id"])
            credential = OrderAccessToken(
                order_id=order_id,
                token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
                scope="review.create",
                replay_ciphertext=b"{}",
                replay_key_version=1,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
            session.add(credential)

        app = SimpleNamespace(
            state=SimpleNamespace(
                database=database,
                settings=SimpleNamespace(outbox_encryption_key=SecretStr("k" * 32)),
            )
        )
        request = Request(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": f"/api/v1/orders/{order_id}",
                "raw_path": f"/api/v1/orders/{order_id}".encode(),
                "query_string": b"",
                "headers": [],
                "server": ("test", 80),
                "client": ("test", 1234),
                "root_path": "",
                "app": app,
            }
        )

        with pytest.raises(ApplicationError) as denied:
            await private_order(order_id, request, raw_token)
        assert denied.value.status_code == 404
        assert denied.value.code == "ORDER_NOT_FOUND"

        async with database.transaction() as session:
            stored = await session.get(OrderAccessToken, credential.id)
            assert stored is not None
            stored.scope = "order.read"

        response = await private_order(order_id, request, raw_token)
        assert response.status_code == 200
        assert json.loads(response.body)["order_id"] == str(order_id)
    finally:
        await database.dispose()

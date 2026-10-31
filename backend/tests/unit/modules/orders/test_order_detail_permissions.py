"""Permission-scoped payment and refund detail returned by staff order APIs."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from modest_chic_backend.api.v1.orders import get_order_detail
from modest_chic_backend.modules.orders.admin_service import OrderAdminService


class _Database:
    @asynccontextmanager
    async def session(self) -> AsyncIterator[object]:
        yield object()


@pytest.mark.parametrize(
    (
        "permissions",
        "expected_customer_email",
        "expected_payment_count",
        "expected_refund_count",
    ),
    [
        (["order.read"], None, 0, 0),
        (["order.read", "refund.request"], None, 0, 1),
        (["order.read", "payment.read"], None, 1, 1),
        (["order.read", "customer.read"], "buyer@example.test", 0, 0),
    ],
)
def test_order_detail_scopes_financial_records_to_permissions(
    monkeypatch: pytest.MonkeyPatch,
    permissions: list[str],
    expected_customer_email: str | None,
    expected_payment_count: int,
    expected_refund_count: int,
) -> None:
    order_id = uuid.uuid4()
    include_flags: list[tuple[bool, bool]] = []
    include_customer_flags: list[bool] = []

    async def detail(
        service: OrderAdminService,
        requested_order_id: uuid.UUID,
        *,
        include_customer_details: bool,
        include_payments: bool,
        include_refunds: bool,
    ) -> dict[str, Any]:
        assert requested_order_id == order_id
        include_flags.append((include_payments, include_refunds))
        include_customer_flags.append(include_customer_details)
        return {
            "customer_id": "customer-1",
            "customer_email": "buyer@example.test",
            "payments": [{"provider_txn_id": "payment-secret"}],
            "refunds": [{"provider_reference": "refund-reference"}],
        }

    monkeypatch.setattr(OrderAdminService, "detail", detail)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(database=_Database())))
    identity = SimpleNamespace(permission_keys=permissions)

    result = asyncio.run(get_order_detail(order_id, request, identity))

    assert len(result["payments"]) == expected_payment_count  # type: ignore[arg-type]
    assert len(result["refunds"]) == expected_refund_count  # type: ignore[arg-type]
    assert result["customer_email"] == expected_customer_email
    assert include_flags == [(expected_payment_count > 0, expected_refund_count > 0)]
    assert include_customer_flags == [expected_customer_email is not None]

"""Checkout guards that prevent unsupported and stale orders."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.checkout.service import CheckoutService


def _service() -> CheckoutService:
    return CheckoutService(AsyncMock(), encryption_key=b"k" * 32)


def _policy_terms() -> dict[str, object]:
    policies = {
        policy_type: {
            "policy_version_id": str(uuid.uuid4()),
            "version": 1,
            "content": {policy_type: "Approved"},
        }
        for policy_type in ("checkout_bundle", "shipping", "returns")
    }
    return {
        "shipping_charge_minor": 25000,
        "policy_version_ids": {
            policy_type: policy["policy_version_id"] for policy_type, policy in policies.items()
        },
        "policies": policies,
    }


async def test_quote_uses_current_cart_and_approved_shipping() -> None:
    service = _service()
    cart = {
        "id": str(uuid.uuid4()),
        "version": 7,
        "items": [{"variant_id": str(uuid.uuid4()), "quantity": 2, "line_total_minor": 300000}],
    }
    with (
        patch.object(service, "_get_cart", new_callable=AsyncMock, return_value=cart),
        patch.object(service, "_lock_stock", new_callable=AsyncMock),
        patch.object(
            service,
            "_approved_terms",
            new_callable=AsyncMock,
            return_value=_policy_terms(),
        ),
    ):
        quote = await service.quote("guest", fulfillment_method="DELIVERY")
    assert quote["cart_version"] == 7
    assert quote["subtotal_minor"] == 300000
    assert quote["shipping_charge_minor"] == 25000
    assert quote["total_minor"] == 325000
    assert set(quote["policy_version_ids"]) == {"checkout_bundle", "shipping", "returns"}
    assert quote["policies"]["shipping"]["content"] == {"shipping": "Approved"}
    assert len(quote["idempotency_key"]) >= 16


async def test_quote_applies_valid_coupon_discount() -> None:
    service = _service()
    variant_id = str(uuid.uuid4())
    cart = {
        "id": str(uuid.uuid4()),
        "version": 7,
        "items": [{"variant_id": variant_id, "quantity": 2, "line_total_minor": 300000}],
    }
    coupon = {"code": "WELCOME", "discount_minor": 30000, "allocations": {variant_id: 30000}}
    with (
        patch.object(service, "_get_cart", new_callable=AsyncMock, return_value=cart),
        patch.object(service, "_lock_stock", new_callable=AsyncMock),
        patch.object(
            service,
            "_approved_terms",
            new_callable=AsyncMock,
            return_value=_policy_terms(),
        ),
        patch("modest_chic_backend.modules.checkout.service.CouponService") as coupon_service,
    ):
        coupon_service.return_value.validate_coupon = AsyncMock(return_value=coupon)
        quote = await service.quote("guest", coupon_code="WELCOME")
    assert quote["discount_minor"] == 30000
    assert quote["total_minor"] == 295000
    assert quote["applied_coupon"]["code"] == "WELCOME"


async def test_place_order_rejects_stale_cart_version() -> None:
    service = _service()
    no_order = MagicMock()
    no_order.scalar_one_or_none.return_value = None
    service._session.execute = AsyncMock(side_effect=[MagicMock(), no_order])
    with patch.object(
        service,
        "_get_cart",
        new_callable=AsyncMock,
        return_value={"id": str(uuid.uuid4()), "version": 2, "items": []},
    ):
        with pytest.raises(ApplicationError) as raised:
            await service.place_order(
                cart_token="guest",
                checkout_id="checkout-request-123",
                customer_name="Buyer",
                customer_phone="+923001234567",
                fulfillment_method="PICKUP",
                payment_method="COD",
                cart_version=1,
                accepted_total_minor=100,
                policy_version_ids={
                    "checkout_bundle": str(uuid.uuid4()),
                    "shipping": str(uuid.uuid4()),
                    "returns": str(uuid.uuid4()),
                },
                accepted_policy=True,
            )
    assert raised.value.code == "CART_CHANGED"


async def test_place_order_requires_policy_acceptance() -> None:
    service = _service()
    with pytest.raises(ApplicationError) as raised:
        await service.place_order(
            cart_token="guest",
            checkout_id="checkout-request-123",
            customer_name="Buyer",
            customer_phone="+923001234567",
            fulfillment_method="PICKUP",
            payment_method="COD",
            cart_version=1,
            accepted_total_minor=100,
            policy_version_ids={
                "checkout_bundle": str(uuid.uuid4()),
                "shipping": str(uuid.uuid4()),
                "returns": str(uuid.uuid4()),
            },
            accepted_policy=False,
        )
    assert raised.value.code == "POLICY_REQUIRED"


async def test_place_order_requires_each_policy_version() -> None:
    service = _service()
    with pytest.raises(ApplicationError) as raised:
        await service.place_order(
            cart_token="guest",
            checkout_id="checkout-request-123",
            customer_name="Buyer",
            customer_phone="+923001234567",
            fulfillment_method="PICKUP",
            payment_method="COD",
            cart_version=1,
            accepted_total_minor=100,
            policy_version_ids={"checkout_bundle": str(uuid.uuid4())},
            accepted_policy=True,
        )
    assert raised.value.code == "POLICY_REQUIRED"

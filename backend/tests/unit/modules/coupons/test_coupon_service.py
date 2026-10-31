"""Unit tests for coupon service. TDD RED → GREEN."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modest_chic_backend.modules.coupons.enums import (
    CouponRedemptionStatus,
    CouponState,
    CouponType,
)
from modest_chic_backend.modules.coupons.models import Coupon, CouponRedemption


def _items() -> list[dict[str, object]]:
    return [
        {
            "variant_id": str(uuid.uuid4()),
            "product_id": str(uuid.uuid4()),
            "category_ids": [],
            "line_total_minor": 200000,
        }
    ]


def _coupon(**kw: object) -> MagicMock:
    c = MagicMock(spec=Coupon)
    c.id = uuid.uuid4()
    c.code = "WELCOME10"
    c.type = CouponType.PERCENT
    c.value_minor = 10
    c.currency = "PKR"
    c.min_order_minor = 100000
    c.max_discount_minor = 50000
    c.usage_limit = 100
    c.per_customer_limit = 1
    c.starts_at = None
    c.ends_at = None
    c.is_active = True
    c.state = CouponState.ACTIVE
    for k, v in kw.items():
        if v is not None:
            setattr(c, k, v)
    return c


async def test_create_coupon_succeeds() -> None:
    from modest_chic_backend.modules.coupons.service import CouponService

    mock_session = AsyncMock()
    svc = CouponService(mock_session)
    with patch.object(svc._repo, "find_by_code", new_callable=AsyncMock) as fc:
        fc.return_value = None
        with patch.object(svc._repo, "create_coupon", new_callable=AsyncMock) as cc:

            async def _create(coupon):
                coupon.id = uuid.uuid4()
                coupon.state = CouponState.ACTIVE
                coupon.type = CouponType.PERCENT
                return coupon

            cc.side_effect = _create
            with patch.object(svc._repo, "scopes_for", new_callable=AsyncMock, return_value=[]):
                result = await svc.create_coupon(
                    code="WELCOME10",
                    type=CouponType.PERCENT,
                    value_minor=10,
                    actor_id=uuid.uuid4(),
                )
    assert result["code"] == "WELCOME10"


async def test_create_coupon_rejects_duplicate_code() -> None:
    from modest_chic_backend.modules.coupons.service import CouponService

    mock_session = AsyncMock()
    svc = CouponService(mock_session)
    with patch.object(svc._repo, "find_by_code", new_callable=AsyncMock) as fc:
        fc.return_value = _coupon()
        with pytest.raises(ValueError, match="already exists"):
            await svc.create_coupon(
                code="WELCOME10",
                type=CouponType.FIXED,
                value_minor=50000,
                actor_id=uuid.uuid4(),
            )


async def test_update_coupon_rejects_invalid_percent_and_preserves_coupon() -> None:
    from modest_chic_backend.modules.coupons.service import CouponService

    svc = CouponService(AsyncMock())
    coupon = _coupon()
    with patch.object(svc._repo, "find_by_id", new_callable=AsyncMock, return_value=coupon):
        with pytest.raises(ValueError, match="cannot exceed"):
            await svc.update_coupon(coupon.id, {"value_minor": 101})
    assert coupon.value_minor == 10


async def test_update_coupon_rejects_window_that_conflicts_with_existing_end() -> None:
    from datetime import UTC, datetime

    from modest_chic_backend.modules.coupons.service import CouponService

    svc = CouponService(AsyncMock())
    coupon = _coupon(ends_at=datetime(2026, 11, 1, tzinfo=UTC))
    with patch.object(svc._repo, "find_by_id", new_callable=AsyncMock, return_value=coupon):
        with pytest.raises(ValueError, match="end must be after"):
            await svc.update_coupon(coupon.id, {"starts_at": datetime(2026, 12, 1, tzinfo=UTC)})


async def test_validate_coupon_returns_discount() -> None:
    from modest_chic_backend.modules.coupons.service import CouponService

    mock_session = AsyncMock()
    svc = CouponService(mock_session)
    coupon = _coupon()
    with patch.object(svc._repo, "find_active_by_code", new_callable=AsyncMock) as fc:
        fc.return_value = coupon
        with patch.object(svc._repo, "count_redemptions", new_callable=AsyncMock, return_value=0):
            with patch.object(svc._repo, "scopes_for", new_callable=AsyncMock, return_value=[]):
                result = await svc.validate_coupon(
                    code="WELCOME10",
                    items=_items(),
                    customer_id=None,
                )
    assert result is not None
    assert result["discount_minor"] == 20000


async def test_validate_coupon_respects_max_discount() -> None:
    from modest_chic_backend.modules.coupons.service import CouponService

    mock_session = AsyncMock()
    svc = CouponService(mock_session)
    coupon = _coupon(max_discount_minor=50000)
    with patch.object(svc._repo, "find_active_by_code", new_callable=AsyncMock) as fc:
        fc.return_value = coupon
        items = _items()
        items[0]["line_total_minor"] = 1000000
        with patch.object(svc._repo, "count_redemptions", new_callable=AsyncMock, return_value=0):
            with patch.object(svc._repo, "scopes_for", new_callable=AsyncMock, return_value=[]):
                result = await svc.validate_coupon(
                    code="WELCOME10",
                    items=items,
                    customer_id=None,
                )
    assert result["discount_minor"] == 50000


async def test_validate_coupon_fails_below_min_order() -> None:
    from modest_chic_backend.modules.coupons.service import CouponService

    mock_session = AsyncMock()
    svc = CouponService(mock_session)
    with patch.object(svc._repo, "find_active_by_code", new_callable=AsyncMock) as fc:
        fc.return_value = _coupon(min_order_minor=500000)
        with patch.object(svc._repo, "count_redemptions", new_callable=AsyncMock, return_value=0):
            result = await svc.validate_coupon(
                code="WELCOME10",
                items=[{**_items()[0], "line_total_minor": 50000}],
                customer_id=None,
            )
    assert result is None


async def test_reserve_redemption_increments_usage() -> None:
    from modest_chic_backend.modules.coupons.service import CouponService

    mock_session = AsyncMock()
    svc = CouponService(mock_session)
    coupon = _coupon()
    redemption = MagicMock(
        spec=CouponRedemption,
        id=uuid.uuid4(),
        status=CouponRedemptionStatus.RESERVED,
        discount_minor=20000,
        idempotency_key="ik1",
    )
    with patch.object(svc._repo, "find_active_by_code", new_callable=AsyncMock) as fc:
        fc.return_value = coupon
        with patch.object(svc._repo, "count_redemptions", new_callable=AsyncMock) as cr:
            cr.side_effect = [0, 0]
            with patch.object(svc._repo, "scopes_for", new_callable=AsyncMock, return_value=[]):
                with patch.object(svc._repo, "create_redemption", new_callable=AsyncMock) as cd:
                    cd.return_value = redemption
                    result = await svc.reserve_redemption(
                        code="WELCOME10",
                        items=_items(),
                        customer_id=uuid.uuid4(),
                        order_id=uuid.uuid4(),
                        discount_minor=20000,
                        idempotency_key="ik1",
                    )
    assert result["status"] == "RESERVED"

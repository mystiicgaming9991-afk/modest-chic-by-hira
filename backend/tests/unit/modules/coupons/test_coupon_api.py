"""Coupon API input guards for campaign values and validity windows."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from modest_chic_backend.api.v1.coupons import CreateCouponRequest


def test_coupon_request_accepts_ordered_timezone_aware_window() -> None:
    request = CreateCouponRequest(
        code="spring",
        type="PERCENT",
        value_minor=15,
        starts_at=datetime(2026, 10, 25, tzinfo=UTC),
        ends_at=datetime(2026, 11, 25, tzinfo=UTC),
    )
    assert request.code == "spring"


@pytest.mark.parametrize(
    "window",
    [
        {"starts_at": datetime(2026, 10, 25), "ends_at": datetime(2026, 11, 25)},
        {
            "starts_at": datetime(2026, 11, 25, tzinfo=UTC),
            "ends_at": datetime(2026, 10, 25, tzinfo=UTC),
        },
    ],
)
def test_coupon_request_rejects_invalid_validity_window(window: dict[str, datetime]) -> None:
    with pytest.raises(ValidationError):
        CreateCouponRequest(code="spring", type="FIXED", value_minor=5000, **window)

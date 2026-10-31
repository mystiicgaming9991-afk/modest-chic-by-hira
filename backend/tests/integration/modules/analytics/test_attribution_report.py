"""Attribution aggregates use accepted order snapshots and keep revenue claims separate."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.analytics.service import AnalyticsService
from modest_chic_backend.modules.auth.models import StaffUser
from modest_chic_backend.modules.orders.enums import OrderState
from modest_chic_backend.modules.orders.models import Order
from modest_chic_backend.modules.orders.service import OrderService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_attribution_report_groups_snapshots_and_separates_discount_from_intake() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    suffix = uuid.uuid4().hex
    today = datetime.now(UTC).date()
    try:
        async with database.session() as session:
            async with session.begin():
                actor = StaffUser(email=f"report-{suffix}@test.local", display_name="Test")
                session.add(actor)
                await session.flush()
                orders = OrderService(session)
                for index in range(3):
                    attributed = index < 2
                    order_data = await orders.create_order(
                        customer_name=f"Buyer {index}",
                        customer_phone=f"0300000{index:04d}",
                        fulfillment_method="DELIVERY",
                        payment_method="COD",
                        items=[
                            {
                                "sku": f"REPORT-{suffix}-{index}",
                                "product_title": "Snapshot item",
                                "variant_name": "Rose",
                                "quantity": 1,
                                "unit_price_minor": 1000,
                                "line_total_minor": 1000,
                            }
                        ],
                        subtotal_minor=1000,
                        discount_minor=100 if attributed else 0,
                        total_minor=900 if attributed else 1000,
                        checkout_idempotency_key=f"report-order-{suffix}-{index}",
                        source="SOCIAL",
                        actor_id=actor.id,
                        attribution_source="instagram" if attributed else None,
                        attribution_campaign=f"winter-{suffix}" if attributed else None,
                        attribution_creator_code="MAYA10" if attributed else None,
                    )
                    if index == 1:
                        order = await session.get(Order, uuid.UUID(order_data["id"]))
                        assert order is not None
                        order.state = OrderState.CANCELLED
                report = await AnalyticsService(session).attribution_report(today, today)
                assert report["measurement"].startswith("Accepted order intake")
                assert report["totals"] == {
                    "order_count": 2,
                    "subtotal_minor": 2000,
                    "discount_minor": 200,
                    "shipping_charge_minor": 0,
                    "accepted_total_minor": 1800,
                    "current_order_states": {
                        "PENDING_CONFIRMATION": 1,
                        "CONFIRMED": 0,
                        "PROCESSING": 0,
                        "FULFILLED": 0,
                        "COMPLETED": 0,
                        "CANCELLED": 1,
                    },
                }
                assert len(report["rows"]) == 1
                assert report["rows"][0]["creator_code"] == "MAYA10"
                assert report["rows"][0]["order_source"] == "SOCIAL"
                assert report["rows"][0]["discount_minor"] == 200
                with pytest.raises(ApplicationError) as invalid_range:
                    await AnalyticsService(session).attribution_report(
                        today, today - timedelta(days=1)
                    )
                assert invalid_range.value.code == "DATE_RANGE_INVALID"
                await session.rollback()
    finally:
        await database.dispose()

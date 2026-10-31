"""Analytics service — dashboard counts and sales summaries."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.analytics.repository import AnalyticsRepository
from modest_chic_backend.modules.orders.enums import OrderSource, OrderState


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AnalyticsRepository(session)

    async def dashboard_counts(self, permission_keys: set[str] | None = None) -> dict[str, Any]:
        order_states = await self._repo.order_state_counts()
        permissions = permission_keys or set()
        queues: dict[str, int] = {}
        if "order.read" in permissions:
            queues["cod_confirmation"] = await self._repo.pending_cod_count()
            queues[
                "stock_reservation_exceptions"
            ] = await self._repo.stock_reservation_exception_count()
        if "fulfillment.pack" in permissions:
            queues["packing"] = await self._repo.packing_queue_count()
        if "review.moderate" in permissions:
            queues["product_reviews"] = await self._repo.pending_review_count()
        if "inventory.read" in permissions:
            queues["zero_available_inventory"] = await self._repo.zero_available_balance_count()
            queues["low_stock_inventory"] = await self._repo.low_stock_balance_count()
        return {
            "as_of": datetime.now(UTC).isoformat(),
            "order_states": {state.value: order_states.get(state, 0) for state in OrderState},
            "queues": queues,
        }

    async def attribution_report(self, start_date: date, end_date: date) -> dict[str, Any]:
        if end_date < start_date:
            raise ApplicationError(
                422, "DATE_RANGE_INVALID", "End date must be on or after start date."
            )
        start_at = datetime.combine(start_date, time.min, tzinfo=UTC)
        end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
        rows = await self._repo.attributed_order_totals(start_at, end_at)
        totals = {
            field: sum(int(row.get(field) or 0) for row in rows)
            for field in (
                "order_count",
                "subtotal_minor",
                "discount_minor",
                "shipping_charge_minor",
                "accepted_total_minor",
            )
        }
        state_counts = {
            state.value: sum(int(row.get(f"state_{state.value.lower()}") or 0) for row in rows)
            for state in OrderState
        }
        for row in rows:
            source = row.get("order_source")
            if isinstance(source, OrderSource):
                row["order_source"] = source.value
        return {
            "period": {
                "from_date": start_date.isoformat(),
                "to_date": end_date.isoformat(),
                "time_zone": "UTC",
            },
            "measurement": "Accepted order intake; not collected or settled revenue.",
            "totals": {**totals, "current_order_states": state_counts},
            "rows": rows,
        }

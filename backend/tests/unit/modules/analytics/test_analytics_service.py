"""Unit tests for analytics dashboard service. TDD RED."""

from unittest.mock import AsyncMock, patch


async def test_dashboard_counts_returns_queue_sizes() -> None:
    from modest_chic_backend.modules.analytics.service import AnalyticsService

    mock_session = AsyncMock()
    svc = AnalyticsService(mock_session)

    from modest_chic_backend.modules.orders.enums import OrderState

    with patch.object(svc._repo, "order_state_counts", new_callable=AsyncMock) as cs:
        cs.return_value = {
            OrderState.PENDING_CONFIRMATION: 5,
            OrderState.CONFIRMED: 10,
            OrderState.PROCESSING: 3,
        }
        result = await svc.dashboard_counts()

    assert result["order_states"]["PENDING_CONFIRMATION"] == 5
    assert result["order_states"]["CONFIRMED"] == 10
    assert result["order_states"]["PROCESSING"] == 3
    assert result["order_states"]["CANCELLED"] == 0
    assert result["queues"] == {}
    assert "total_revenue_today" not in result


async def test_dashboard_counts_adds_only_permissioned_actionable_queues() -> None:
    from modest_chic_backend.modules.analytics.service import AnalyticsService

    svc = AnalyticsService(AsyncMock())
    with (
        patch.object(svc._repo, "order_state_counts", new_callable=AsyncMock, return_value={}),
        patch.object(svc._repo, "pending_cod_count", new_callable=AsyncMock, return_value=3),
        patch.object(
            svc._repo, "stock_reservation_exception_count", new_callable=AsyncMock, return_value=6
        ),
        patch.object(svc._repo, "pending_review_count", new_callable=AsyncMock, return_value=2),
        patch.object(svc._repo, "packing_queue_count", new_callable=AsyncMock, return_value=5),
        patch.object(
            svc._repo, "zero_available_balance_count", new_callable=AsyncMock, return_value=7
        ),
        patch.object(svc._repo, "low_stock_balance_count", new_callable=AsyncMock, return_value=4),
    ):
        result = await svc.dashboard_counts(
            {"order.read", "review.moderate", "inventory.read", "fulfillment.pack"}
        )

    assert result["queues"] == {
        "cod_confirmation": 3,
        "stock_reservation_exceptions": 6,
        "product_reviews": 2,
        "packing": 5,
        "zero_available_inventory": 7,
        "low_stock_inventory": 4,
    }


async def test_dashboard_counts_hides_queues_without_domain_permissions() -> None:
    from modest_chic_backend.modules.analytics.service import AnalyticsService

    svc = AnalyticsService(AsyncMock())
    with (
        patch.object(svc._repo, "order_state_counts", new_callable=AsyncMock, return_value={}),
        patch.object(svc._repo, "pending_cod_count", new_callable=AsyncMock) as cod_count,
        patch.object(
            svc._repo, "stock_reservation_exception_count", new_callable=AsyncMock
        ) as stock_exceptions_count,
        patch.object(svc._repo, "pending_review_count", new_callable=AsyncMock) as review_count,
        patch.object(svc._repo, "packing_queue_count", new_callable=AsyncMock) as packing_count,
        patch.object(
            svc._repo, "zero_available_balance_count", new_callable=AsyncMock
        ) as inventory_count,
        patch.object(
            svc._repo, "low_stock_balance_count", new_callable=AsyncMock
        ) as low_stock_count,
    ):
        result = await svc.dashboard_counts({"dashboard.read"})

    assert result["queues"] == {}
    cod_count.assert_not_awaited()
    stock_exceptions_count.assert_not_awaited()
    review_count.assert_not_awaited()
    packing_count.assert_not_awaited()
    inventory_count.assert_not_awaited()
    low_stock_count.assert_not_awaited()


async def test_sales_summary_is_unavailable_until_financial_data_is_reconciled() -> None:
    import pytest

    from modest_chic_backend.api.v1.analytics import sales_summary
    from modest_chic_backend.core.errors import ApplicationError

    with pytest.raises(ApplicationError) as error:
        await sales_summary(request=None, identity=None, days=7)  # type: ignore[arg-type]

    assert error.value.status_code == 501
    assert error.value.code == "ANALYTICS_NOT_RECONCILED"

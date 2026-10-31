"""Analytics dashboard routes — staff-only read operations."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from modest_chic_backend.api.v1.dependencies import require_permission
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.analytics.service import AnalyticsService
from modest_chic_backend.modules.auth.service import StaffIdentity

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])


@router.get("/dashboard")
async def dashboard(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("dashboard.read"))],
) -> JSONResponse:
    database = request.app.state.database
    async with database.session() as session:
        result = await AnalyticsService(session).dashboard_counts(set(identity.permission_keys))
    return JSONResponse(content=result)


@router.get("/sales")
async def sales_summary(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("analytics.read"))],
    days: int = Query(default=7, ge=1, le=365),
) -> JSONResponse:
    raise ApplicationError(
        501,
        "ANALYTICS_NOT_RECONCILED",
        "Financial summaries are unavailable until payment and refund records are reconciled.",
    )


@router.get("/attribution")
async def attribution_report(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("analytics.read"))],
    from_date: Annotated[date | None, Query()] = None,
    to_date: Annotated[date | None, Query()] = None,
) -> JSONResponse:
    end_date = to_date or datetime.now(UTC).date()
    start_date = from_date or end_date - timedelta(days=29)
    async with request.app.state.database.session() as session:
        result = await AnalyticsService(session).attribution_report(start_date, end_date)
    return JSONResponse(content=result)

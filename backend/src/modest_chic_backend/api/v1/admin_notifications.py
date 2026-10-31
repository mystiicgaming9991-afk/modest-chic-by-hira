"""Staff-only notification delivery status routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from modest_chic_backend.api.v1.dependencies import require_permission
from modest_chic_backend.modules.auth.service import StaffIdentity
from modest_chic_backend.modules.outbox.admin_service import OutboxAdminService, OutboxStatus

router = APIRouter(prefix="/admin/notifications", tags=["admin-notifications"])


@router.get("/outbox")
async def list_outbox_events(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("notification.read"))],
    status: OutboxStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
) -> dict[str, object]:
    """List bounded email delivery status without exposing message contents."""
    async with request.app.state.database.session() as session:
        return await OutboxAdminService(session).list_events(
            status=status,
            limit=limit,
            offset=offset,
        )

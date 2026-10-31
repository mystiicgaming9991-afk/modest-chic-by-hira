"""Staff administration routes — listing, role changes, suspend/activate."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from modest_chic_backend.api.v1.dependencies import require_permission
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.auth.admin_service import StaffAdminService, StaffStaleEditError
from modest_chic_backend.modules.auth.service import StaffIdentity

router = APIRouter(prefix="/admin/staff", tags=["staff-admin"])


class SetRolesRequest(BaseModel):
    role_keys: list[str] = Field(min_length=1)
    expected_updated_at: datetime


# ── List ──────────────────────────────────────────────────────────


@router.get("")
async def list_staff(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("staff.manage"))],
) -> list[dict[str, Any]]:
    database = request.app.state.database
    async with database.session() as session:
        return await StaffAdminService(session).list_staff()


# ── Set Roles ─────────────────────────────────────────────────────


@router.put("/{staff_user_id}/roles")
async def set_roles(
    staff_user_id: str,
    payload: SetRolesRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("staff.manage"))],
) -> dict[str, Any]:
    from uuid import UUID

    database = request.app.state.database
    async with database.transaction() as session:
        svc = StaffAdminService(session)
        try:
            return await svc.set_roles(
                UUID(staff_user_id),
                payload.role_keys,
                identity.user.id,
                payload.expected_updated_at,
            )
        except LookupError as exc:
            raise ApplicationError(404, "STAFF_NOT_FOUND", str(exc)) from exc
        except StaffStaleEditError as exc:
            raise ApplicationError(409, "STAFF_STALE_EDIT", str(exc)) from exc
        except ValueError as exc:
            raise ApplicationError(400, "STAFF_ADMIN_ERROR", str(exc)) from exc


# ── Suspend ───────────────────────────────────────────────────────


@router.post("/{staff_user_id}/suspend")
async def suspend_staff(
    staff_user_id: str,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("staff.manage"))],
) -> dict[str, Any]:
    from uuid import UUID

    database = request.app.state.database
    async with database.transaction() as session:
        svc = StaffAdminService(session)
        try:
            return await svc.suspend(UUID(staff_user_id), identity.user.id)
        except LookupError as exc:
            raise ApplicationError(404, "STAFF_NOT_FOUND", str(exc)) from exc
        except ValueError as exc:
            raise ApplicationError(400, "STAFF_ADMIN_ERROR", str(exc)) from exc


# ── Activate ──────────────────────────────────────────────────────


@router.post("/{staff_user_id}/activate")
async def activate_staff(
    staff_user_id: str,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("staff.manage"))],
) -> dict[str, Any]:
    from uuid import UUID

    database = request.app.state.database
    async with database.transaction() as session:
        svc = StaffAdminService(session)
        try:
            return await svc.activate(UUID(staff_user_id), identity.user.id)
        except LookupError as exc:
            raise ApplicationError(404, "STAFF_NOT_FOUND", str(exc)) from exc
        except ValueError as exc:
            raise ApplicationError(400, "STAFF_ADMIN_ERROR", str(exc)) from exc

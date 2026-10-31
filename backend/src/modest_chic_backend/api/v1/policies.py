"""Policy version HTTP routes for authenticated staff."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from modest_chic_backend.api.v1.dependencies import require_permission
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.auth.service import StaffIdentity
from modest_chic_backend.modules.policies.schemas import (
    PolicyVersionListResponse,
    PolicyVersionPublish,
    PolicyVersionRead,
)
from modest_chic_backend.modules.policies.service import PoliciesService

router = APIRouter(prefix="/admin/policies", tags=["admin-policies"])
public_router = APIRouter(prefix="/policies", tags=["public-policies"])


@public_router.get("/{policy_type}")
async def public_effective_policy(policy_type: str, request: Request) -> JSONResponse:
    if policy_type not in {"shipping", "returns"}:
        raise ApplicationError(404, "POLICY_NOT_FOUND", "Policy not found.")
    async with request.app.state.database.session() as session:
        policy = await PoliciesService(session).get_effective(policy_type)
        if policy is None or not policy.approved_by or not policy.content:
            raise ApplicationError(404, "POLICY_NOT_FOUND", "Policy not found.")
        return JSONResponse(
            content={
                "type": policy_type,
                "version": policy.version,
                "content": policy.content,
            }
        )


@router.get("", response_model=PolicyVersionListResponse)
async def list_policies(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("settings.manage"))],
    type: str | None = Query(default=None, description="Filter by policy type"),
    active_only: bool = Query(
        default=False, description="When true, return only currently effective versions"
    ),
) -> PolicyVersionListResponse:
    """List policy versions, optionally filtered by type."""
    database = request.app.state.database
    async with database.session() as session:
        service = PoliciesService(session)
        if active_only and type:
            effective = await service.get_effective(type)
            items = [effective] if effective else []
            return PolicyVersionListResponse(items=items)
        return await service.list_versions(type=type)


@router.post("", response_model=PolicyVersionRead, status_code=201)
async def publish_policy(
    payload: PolicyVersionPublish,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("settings.manage"))],
) -> PolicyVersionRead:
    """Publish a new immutable policy version."""
    database = request.app.state.database
    async with database.transaction() as session:
        service = PoliciesService(session)
        try:
            result = await service.publish_version(
                type=payload.type,
                effective_from=payload.effective_from,
                content=payload.content,
                approved_by=identity.user.id,
            )
        except ValueError as exc:
            raise ApplicationError(400, "INVALID_POLICY", str(exc)) from exc
    return result


@router.get("/{type}/effective", response_model=PolicyVersionRead)
async def get_effective_policy(
    type: str,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("settings.manage"))],
) -> JSONResponse:
    """Return the currently effective policy version for a type."""
    database = request.app.state.database
    async with database.session() as session:
        service = PoliciesService(session)
        try:
            effective = await service.get_effective(type)
        except ValueError as exc:
            raise ApplicationError(400, "INVALID_POLICY_TYPE", str(exc)) from exc
        if effective is None:
            raise ApplicationError(404, "POLICY_NOT_FOUND", f"No effective policy for type: {type}")
    return JSONResponse(content=effective.model_dump(mode="json"))

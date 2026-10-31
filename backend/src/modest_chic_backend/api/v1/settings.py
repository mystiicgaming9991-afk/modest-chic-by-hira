"""Store settings HTTP routes for authenticated staff."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from modest_chic_backend.api.v1.dependencies import require_permission
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.core.settings import Settings
from modest_chic_backend.modules.auth.service import StaffIdentity
from modest_chic_backend.modules.settings.schemas import (
    SecretSettingReadResponse,
    StoreSettingListResponse,
    StoreSettingRead,
    StoreSettingSecretUpdate,
    StoreSettingUpdate,
)
from modest_chic_backend.modules.settings.service import SettingsService

router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])


def _get_settings_service(request: Request) -> SettingsService:
    """Build a settings service from the request-scoped session and encryption key."""
    # Reserved for future session-scoped pattern; routes currently create their own session.
    return SettingsService.__new__(SettingsService)


@router.get("", response_model=StoreSettingListResponse)
async def list_settings(
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("settings.manage"))],
) -> StoreSettingListResponse:
    """Return all non-secret store settings with their current version."""
    settings: Settings = request.app.state.settings
    encryption_key = settings.outbox_encryption_key.get_secret_value().encode("utf-8")
    database = request.app.state.database
    async with database.session() as session:
        service = SettingsService(session, encryption_key)
        items = await service.get_all_visible()
    return StoreSettingListResponse(items=items)


@router.put("", response_model=StoreSettingRead)
async def update_setting(
    payload: StoreSettingUpdate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("settings.manage"))],
) -> StoreSettingRead:
    """Update a non-secret setting with optimistic concurrency control."""
    settings: Settings = request.app.state.settings
    encryption_key = settings.outbox_encryption_key.get_secret_value().encode("utf-8")
    database = request.app.state.database
    async with database.transaction() as session:
        service = SettingsService(session, encryption_key)
        try:
            result = await service.update_setting(
                key=payload.key,
                value=payload.value,
                version=payload.version,
                actor_id=identity.user.id,
            )
        except ValueError as exc:
            msg = str(exc)
            if "version conflict" in msg:
                raise ApplicationError(409, "SETTING_VERSION_CONFLICT", msg) from exc
            raise ApplicationError(400, "INVALID_SETTING", msg) from exc
    return result


@router.put("/secrets", response_model=StoreSettingRead)
async def update_secret_setting(
    payload: StoreSettingSecretUpdate,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("settings.manage"))],
) -> StoreSettingRead:
    """Write a secret setting value — plaintext is encrypted before storage."""
    settings: Settings = request.app.state.settings
    encryption_key = settings.outbox_encryption_key.get_secret_value().encode("utf-8")
    database = request.app.state.database
    async with database.transaction() as session:
        service = SettingsService(session, encryption_key)
        try:
            result = await service.update_secret(
                key=payload.key,
                value=payload.value,
                version=payload.version,
                actor_id=identity.user.id,
            )
        except ValueError as exc:
            msg = str(exc)
            if "version conflict" in msg:
                raise ApplicationError(409, "SETTING_VERSION_CONFLICT", msg) from exc
            raise ApplicationError(400, "INVALID_SETTING", msg) from exc
    return result


@router.get("/secrets/{key}", response_model=SecretSettingReadResponse)
async def get_secret_value(
    key: str,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("settings.manage"))],
) -> JSONResponse:
    """Decrypt and return a single secret setting value."""
    settings: Settings = request.app.state.settings
    encryption_key = settings.outbox_encryption_key.get_secret_value().encode("utf-8")
    database = request.app.state.database
    async with database.session() as session:
        service = SettingsService(session, encryption_key)
        try:
            result = await service.get_decrypted_secret(
                key=key,
                actor_id=identity.user.id,
            )
        except ValueError as exc:
            raise ApplicationError(400, "INVALID_SETTING", str(exc)) from exc
        except LookupError as exc:
            raise ApplicationError(404, "SETTING_NOT_FOUND", str(exc)) from exc
    return JSONResponse(content=result)

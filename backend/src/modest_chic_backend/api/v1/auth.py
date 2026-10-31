"""Staff authentication route registration."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from modest_chic_backend.api.v1.dependencies import (
    get_authentication_service,
    require_permission,
    require_staff_identity,
)
from modest_chic_backend.core.csrf import create_csrf_token
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.core.settings import Settings
from modest_chic_backend.modules.auth.invitations import InvitationService
from modest_chic_backend.modules.auth.passwords import PasswordService
from modest_chic_backend.modules.auth.schemas import (
    AcceptInvitationRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    InviteStaffRequest,
    LoginRequest,
    ResetPasswordRequest,
    SessionResponse,
    StaffIdentityResponse,
    StaffSummary,
    TotpSetupResponse,
    VerifyTotpRequest,
)
from modest_chic_backend.modules.auth.service import (
    AuthenticationService,
    LoginResult,
    StaffIdentity,
)
from modest_chic_backend.modules.auth.sessions import SessionService
from modest_chic_backend.modules.auth.totp_service import TotpEnrollmentService

router = APIRouter(prefix="/auth", tags=["staff-auth"])
staff_router = APIRouter(prefix="/admin/staff", tags=["staff"])


@router.get("/csrf", status_code=204)
async def issue_csrf_token(request: Request, response: Response) -> None:
    """Set a readable signed double-submit token before browser authentication."""
    settings: Settings = request.app.state.settings
    response.set_cookie(
        "mc_csrf",
        create_csrf_token(settings.csrf_signing_key.get_secret_value()),
        secure=settings.app_env in {"staging", "production"},
        httponly=False,
        samesite="lax",
        path="/",
    )


@router.post("/accept-invitation", status_code=204)
async def accept_invitation(
    payload: AcceptInvitationRequest,
    request: Request,
) -> Response:
    """Consume a valid invitation and activate the invited staff identity."""
    settings: Settings = request.app.state.settings
    service = InvitationService(request.app.state.database, request.app.state.redis, settings)
    accepted = await service.accept_invitation(
        token=payload.token,
        password=payload.password,
        display_name=payload.display_name,
        source_network=_source_network(request),
    )
    if not accepted:
        raise ApplicationError(400, "INVALID_INVITATION", "Invitation is invalid or expired.")
    return Response(status_code=204)


@router.post("/login", response_model=SessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    authentication_service: Annotated[AuthenticationService, Depends(get_authentication_service)],
) -> SessionResponse:
    """Authenticate staff and set the opaque refresh credential as an HttpOnly cookie."""
    result = await authentication_service.login(
        email=payload.email,
        password=payload.password,
        totp_code=payload.totp_code,
        source_network=_source_network(request),
    )
    if result is None:
        raise ApplicationError(401, "AUTHENTICATION_FAILED", "Email or password is incorrect.")
    settings: Settings = request.app.state.settings
    _set_refresh_cookie(response, settings, result.refresh_token)
    return _session_response(result)


@router.get("/me", response_model=StaffIdentityResponse)
async def current_staff(
    identity: Annotated[StaffIdentity, Depends(require_staff_identity)],
) -> StaffIdentityResponse:
    """Return current staff identity and database-resolved permissions."""
    return StaffIdentityResponse(
        id=identity.user.id,
        email=identity.user.email,
        name=identity.user.display_name,
        permission_keys=identity.permission_keys,
        totp_enabled=identity.user.totp_enabled,
    )


@router.post("/refresh", response_model=SessionResponse)
async def refresh_session(request: Request, response: Response) -> SessionResponse:
    """Rotate the HttpOnly refresh credential and return a new access token."""
    settings: Settings = request.app.state.settings
    service = SessionService(request.app.state.database, request.app.state.redis, settings)
    result = await service.refresh(
        refresh_token=request.cookies.get("mc_staff_refresh", ""),
        source_network=_source_network(request),
    )
    if result is None:
        raise ApplicationError(401, "UNAUTHORIZED", "Authentication is required.")
    _set_refresh_cookie(response, settings, result.refresh_token)
    return _session_response(result)


@router.post("/logout", status_code=204)
async def logout(request: Request) -> Response:
    """Revoke the current refresh family and clear the browser cookie."""
    settings: Settings = request.app.state.settings
    service = SessionService(request.app.state.database, request.app.state.redis, settings)
    await service.logout(request.cookies.get("mc_staff_refresh"))
    response = Response(status_code=204)
    response.delete_cookie(
        "mc_staff_refresh",
        secure=settings.app_env in {"staging", "production"},
        httponly=True,
        samesite="strict",
        path="/api/v1/auth",
    )
    return response


@router.post("/password/forgot", status_code=202)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
) -> dict[str, str]:
    """Queue a reset link when eligible while keeping responses account-neutral."""
    settings: Settings = request.app.state.settings
    service = PasswordService(request.app.state.database, request.app.state.redis, settings)
    await service.request_reset(
        email=payload.email,
        source_network=_source_network(request),
    )
    return {"message": "If the account exists, reset instructions will be sent."}


@router.post("/password/reset", status_code=204)
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
) -> Response:
    """Consume one reset link and revoke all staff refresh sessions."""
    settings: Settings = request.app.state.settings
    service = PasswordService(request.app.state.database, request.app.state.redis, settings)
    reset = await service.consume_reset(
        token=payload.token,
        new_password=payload.new_password,
        source_network=_source_network(request),
    )
    if not reset:
        raise ApplicationError(
            400,
            "INVALID_RESET_TOKEN",
            "Password reset link is invalid or expired.",
        )
    return Response(status_code=204)


@router.post("/password/change", status_code=204)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_staff_identity)],
) -> Response:
    """Change the authenticated staff password after checking its current value."""
    settings: Settings = request.app.state.settings
    service = PasswordService(request.app.state.database, request.app.state.redis, settings)
    changed = await service.change_password(
        staff_user_id=identity.user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    if not changed:
        raise ApplicationError(401, "AUTHENTICATION_FAILED", "Current password is incorrect.")
    return Response(status_code=204)


@router.post("/setup-totp", response_model=TotpSetupResponse)
async def setup_totp(
    request: Request,
    response: Response,
    identity: Annotated[StaffIdentity, Depends(require_staff_identity)],
) -> TotpSetupResponse:
    """Generate a pending TOTP seed and prevent intermediaries caching it."""
    settings: Settings = request.app.state.settings
    service = TotpEnrollmentService(request.app.state.database, request.app.state.redis, settings)
    secret, provisioning_uri = await service.begin(identity.user.id)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TotpSetupResponse(secret=secret, qr_code_url=provisioning_uri)


@router.post("/verify-totp", status_code=204)
async def verify_totp(
    payload: VerifyTotpRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_staff_identity)],
) -> Response:
    """Enable TOTP only after the pending secret produces a fresh valid code."""
    settings: Settings = request.app.state.settings
    service = TotpEnrollmentService(request.app.state.database, request.app.state.redis, settings)
    verified = await service.verify(
        staff_user_id=identity.user.id,
        code=payload.totp_code,
        source_network=_source_network(request),
    )
    if not verified:
        raise ApplicationError(400, "INVALID_TOTP_CODE", "TOTP code is invalid or already used.")
    return Response(status_code=204)


@staff_router.post("/invitations", status_code=202)
async def invite_staff(
    payload: InviteStaffRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("staff.manage"))],
) -> Response:
    """Invite a staff member with owner-assigned roles and transactional email."""
    settings: Settings = request.app.state.settings
    service = InvitationService(request.app.state.database, request.app.state.redis, settings)
    await service.invite_staff(
        inviter_id=identity.user.id,
        email=payload.email,
        role_keys=payload.roles,
    )
    return Response(status_code=202)


def _source_network(request: Request) -> str:
    """Use the connected peer address; only trusted proxy configuration may override it."""
    if request.client is None:
        return "unknown"
    return request.client.host


def _set_refresh_cookie(response: Response, settings: Settings, token: str) -> None:
    """Set the opaque refresh token only in its protected browser cookie."""
    response.set_cookie(
        "mc_staff_refresh",
        token,
        max_age=settings.refresh_token_ttl_seconds,
        httponly=True,
        secure=settings.app_env in {"staging", "production"},
        samesite="strict",
        path="/api/v1/auth",
    )


def _session_response(result: LoginResult) -> SessionResponse:
    """Translate login values into the stable non-secret response schema."""
    return SessionResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        auth_state=result.auth_state,
        staff_user=StaffSummary(
            id=result.staff_user_id,
            name=result.display_name,
            roles=result.role_keys,
        ),
    )

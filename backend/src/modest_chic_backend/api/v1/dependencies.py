"""Authentication dependencies for staff-only routes."""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.auth.service import AuthenticationService, StaffIdentity

bearer_scheme = HTTPBearer(auto_error=False)


def get_authentication_service(request: Request) -> AuthenticationService:
    """Build a feature service from application-scoped infrastructure."""
    return AuthenticationService(
        request.app.state.database,
        request.app.state.redis,
        request.app.state.settings,
    )


async def require_staff_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    authentication_service: Annotated[AuthenticationService, Depends(get_authentication_service)],
) -> StaffIdentity:
    """Resolve the bearer token against active staff, session, and current permissions."""
    if credentials is None:
        raise ApplicationError(401, "UNAUTHORIZED", "Authentication is required.")
    identity = await authentication_service.authenticate_access(credentials.credentials)
    if identity is None:
        raise ApplicationError(401, "UNAUTHORIZED", "Authentication is required.")
    return identity


def require_permission(
    permission_key: str,
) -> Callable[..., Awaitable[StaffIdentity]]:
    """Create a dependency that requires a current permission key."""

    async def permission_dependency(
        identity: Annotated[StaffIdentity, Depends(require_staff_identity)],
    ) -> StaffIdentity:
        """Reject an active staff member who lacks the requested permission."""
        if permission_key not in identity.permission_keys:
            raise ApplicationError(403, "FORBIDDEN", "Permission is required.")
        return identity

    return permission_dependency

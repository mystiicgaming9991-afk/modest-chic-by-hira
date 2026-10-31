"""Email/password login and current staff authentication services."""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
from redis.asyncio import Redis

from modest_chic_backend.core.errors import (
    RateLimitExceeded,
    RateLimitServiceUnavailable,
)
from modest_chic_backend.core.rate_limit import RateLimiter, RateLimiterUnavailable
from modest_chic_backend.core.settings import Settings
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.audit.repository import AuditRepository
from modest_chic_backend.modules.auth.models import StaffSession, StaffStatus, StaffUser
from modest_chic_backend.modules.auth.repository import AuthRepository
from modest_chic_backend.modules.auth.security import (
    create_access_token,
    create_opaque_token,
    hash_token,
    normalize_email,
    verify_access_token,
    verify_password,
)
from modest_chic_backend.modules.auth.totp import decrypt_totp_secret, verify_totp_code

DUMMY_PASSWORD_HASH = bcrypt.hashpw(
    b"nonexistent-staff-account-dummy-password", bcrypt.gensalt(rounds=12)
).decode("ascii")


@dataclass(frozen=True)
class LoginResult:
    """Access response values and raw refresh secret for a cookie-only transport."""

    access_token: str
    refresh_token: str
    expires_in: int
    auth_state: str
    staff_user_id: uuid.UUID
    display_name: str
    role_keys: list[str]


@dataclass(frozen=True)
class StaffIdentity:
    """Current persisted staff state used by protected routes."""

    user: StaffUser
    session: StaffSession
    permission_keys: list[str]


class AuthenticationService:
    """Authenticate staff and resolve each access token against current database state."""

    def __init__(self, database: Database, redis: Redis, settings: Settings) -> None:
        self._database = database
        self._redis = redis
        self._settings = settings

    async def login(
        self,
        *,
        email: str,
        password: str,
        totp_code: str | None,
        source_network: str,
    ) -> LoginResult | None:
        """Verify email/password/TOTP, audit the outcome, and create a refresh family."""
        normalized_email = normalize_email(email)
        try:
            allowed = await RateLimiter(self._redis).consume(
                "login", normalized_email, source_network, limit=5, window_seconds=60
            )
        except RateLimiterUnavailable as error:
            raise RateLimitServiceUnavailable() from error
        if not allowed:
            raise RateLimitExceeded()

        now = datetime.now(UTC)
        refresh_token = create_opaque_token()
        async with self._database.transaction() as session:
            repository = AuthRepository(session)
            staff_user = await repository.find_user_by_email(normalized_email, lock=True)
            candidate_hash = (
                staff_user.hashed_password
                if staff_user is not None and staff_user.hashed_password is not None
                else DUMMY_PASSWORD_HASH
            )
            password_matches = await asyncio.to_thread(verify_password, password, candidate_hash)
            eligible_for_totp = (
                staff_user is not None
                and staff_user.status == StaffStatus.ACTIVE
                and password_matches
            )
            totp_matches = (
                self._verify_login_totp(staff_user, totp_code, now) if eligible_for_totp else False
            )
            if (
                staff_user is None
                or staff_user.status != StaffStatus.ACTIVE
                or not password_matches
                or not totp_matches
            ):
                await AuditRepository(session).record(
                    action="staff.login.failed",
                    entity_type="staff_user",
                    actor_id=staff_user.id if staff_user is not None else None,
                    entity_id=staff_user.id if staff_user is not None else None,
                    metadata={"outcome": "denied"},
                )
                return None

            session_id = uuid.uuid4()
            family_id = uuid.uuid4()
            refresh_expiry = now + timedelta(
                seconds=min(self._settings.refresh_token_ttl_seconds, 604800)
            )
            auth_session = StaffSession(
                id=session_id,
                staff_user_id=staff_user.id,
                token_hash=hash_token(refresh_token),
                family_id=family_id,
                expires_at=refresh_expiry,
            )
            await repository.create_session(auth_session)
            staff_user.last_login_at = now
            await AuditRepository(session).record(
                action="staff.login.succeeded",
                entity_type="staff_user",
                actor_id=staff_user.id,
                entity_id=staff_user.id,
                metadata={"totp_enabled": staff_user.totp_enabled},
            )
            access_token = create_access_token(
                subject=str(staff_user.id),
                session_id=str(session_id),
                signing_key=self._settings.jwt_signing_key.get_secret_value(),
                now=now,
                expires_at=now + timedelta(seconds=self._settings.access_token_ttl_seconds),
            )
            roles = await repository.get_roles(staff_user.id)
            enrollment_required = (
                self._settings.app_env == "production" and not staff_user.totp_enabled
            )
            return LoginResult(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=self._settings.access_token_ttl_seconds,
                auth_state="TOTP_ENROLLMENT_REQUIRED" if enrollment_required else "ACTIVE",
                staff_user_id=staff_user.id,
                display_name=staff_user.display_name,
                role_keys=roles,
            )

    async def authenticate_access(self, token: str) -> StaffIdentity | None:
        """Check JWT, session, staff status, and current permissions on every request."""
        try:
            claims = verify_access_token(
                token,
                self._settings.jwt_signing_key.get_secret_value(),
                now=datetime.now(UTC),
            )
            staff_user_id = uuid.UUID(str(claims["sub"]))
            session_id = uuid.UUID(str(claims["session_id"]))
        except (ValueError, KeyError, TypeError):
            return None
        async with self._database.session() as session:
            repository = AuthRepository(session)
            staff_user = await session.get(StaffUser, staff_user_id)
            staff_session = await session.get(StaffSession, session_id)
            now = datetime.now(UTC)
            if (
                staff_user is None
                or staff_user.status != StaffStatus.ACTIVE
                or staff_session is None
                or staff_session.staff_user_id != staff_user.id
                or staff_session.revoked_at is not None
                or staff_session.expires_at <= now
            ):
                return None
            permissions = await repository.get_permissions(staff_user.id)
            if self._settings.app_env == "production" and not staff_user.totp_enabled:
                permissions = []
            return StaffIdentity(staff_user, staff_session, permissions)

    def _verify_login_totp(
        self, staff_user: StaffUser | None, totp_code: str | None, now: datetime
    ) -> bool:
        """Require and consume a fresh TOTP counter only for enrolled accounts."""
        if staff_user is None or not staff_user.totp_enabled:
            return True
        if totp_code is None or staff_user.totp_secret is None:
            return False
        secret = decrypt_totp_secret(
            staff_user.totp_secret,
            self._settings.totp_encryption_key.get_secret_value().encode("utf-8"),
        )
        matched_counter = verify_totp_code(
            secret, totp_code, now=now, last_counter=staff_user.totp_last_counter
        )
        if matched_counter is None:
            return False
        staff_user.totp_last_counter = matched_counter
        return True

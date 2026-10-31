"""Refresh credential rotation, replay detection, and family logout."""

import uuid
from datetime import UTC, datetime, timedelta

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
)
from modest_chic_backend.modules.auth.service import LoginResult


class SessionService:
    """Own refresh and logout transitions within one database transaction."""

    def __init__(self, database: Database, redis: Redis, settings: Settings) -> None:
        self._database = database
        self._redis = redis
        self._settings = settings

    async def refresh(self, *, refresh_token: str, source_network: str) -> LoginResult | None:
        """Rotate a refresh credential or revoke its entire family when replayed."""
        token_digest = hash_token(refresh_token)
        await self._enforce_refresh_limit(token_digest, source_network)
        now = datetime.now(UTC)
        async with self._database.transaction() as session:
            repository = AuthRepository(session)
            old_session = await repository.find_session_by_hash(token_digest, lock=True)
            if old_session is None:
                return None
            if old_session.rotated_at is not None:
                await repository.revoke_family(old_session.family_id, now)
                await AuditRepository(session).record(
                    action="staff.session.refresh_reuse",
                    entity_type="staff_session",
                    actor_id=old_session.staff_user_id,
                    entity_id=old_session.id,
                    metadata={"outcome": "family_revoked"},
                )
                return None
            if old_session.revoked_at is not None or old_session.expires_at <= now:
                return None
            staff_user = await session.get(StaffUser, old_session.staff_user_id)
            if staff_user is None or staff_user.status != StaffStatus.ACTIVE:
                await repository.revoke_family(old_session.family_id, now)
                return None

            old_session.rotated_at = now
            refresh_secret = create_opaque_token()
            session_id = uuid.uuid4()
            family_expiry = now + timedelta(
                seconds=min(self._settings.refresh_token_ttl_seconds, 604800)
            )
            await repository.create_session(
                StaffSession(
                    id=session_id,
                    staff_user_id=staff_user.id,
                    token_hash=hash_token(refresh_secret),
                    family_id=old_session.family_id,
                    expires_at=family_expiry,
                )
            )
            await AuditRepository(session).record(
                action="staff.session.refreshed",
                entity_type="staff_session",
                actor_id=staff_user.id,
                entity_id=session_id,
            )
            access_token = create_access_token(
                subject=str(staff_user.id),
                session_id=str(session_id),
                signing_key=self._settings.jwt_signing_key.get_secret_value(),
                now=now,
                expires_at=now + timedelta(seconds=self._settings.access_token_ttl_seconds),
            )
            role_keys = await repository.get_roles(staff_user.id)
            enrollment_required = (
                self._settings.app_env == "production" and not staff_user.totp_enabled
            )
            return LoginResult(
                access_token=access_token,
                refresh_token=refresh_secret,
                expires_in=self._settings.access_token_ttl_seconds,
                auth_state="TOTP_ENROLLMENT_REQUIRED" if enrollment_required else "ACTIVE",
                staff_user_id=staff_user.id,
                display_name=staff_user.display_name,
                role_keys=role_keys,
            )

    async def logout(self, refresh_token: str | None) -> None:
        """Revoke all rows in the family named by the presented refresh credential."""
        if not refresh_token:
            return
        now = datetime.now(UTC)
        async with self._database.transaction() as session:
            repository = AuthRepository(session)
            staff_session = await repository.find_session_by_hash(
                hash_token(refresh_token), lock=True
            )
            if staff_session is None:
                return
            await repository.revoke_family(staff_session.family_id, now)
            await AuditRepository(session).record(
                action="staff.session.logged_out",
                entity_type="staff_session",
                actor_id=staff_session.staff_user_id,
                entity_id=staff_session.id,
            )

    async def _enforce_refresh_limit(self, token_digest: str, source_network: str) -> None:
        """Enforce the documented refresh limit without exposing raw secrets in Redis."""
        try:
            allowed = await RateLimiter(self._redis).consume(
                "refresh", token_digest, source_network, limit=10, window_seconds=60
            )
        except RateLimiterUnavailable as error:
            raise RateLimitServiceUnavailable() from error
        if not allowed:
            raise RateLimitExceeded()

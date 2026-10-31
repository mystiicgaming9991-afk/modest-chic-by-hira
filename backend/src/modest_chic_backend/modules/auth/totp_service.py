"""TOTP enrollment state transitions for staff authentication."""

import uuid
from datetime import UTC, datetime

import pyotp
from redis.asyncio import Redis
from sqlalchemy import select

from modest_chic_backend.core.errors import (
    ApplicationError,
    RateLimitExceeded,
    RateLimitServiceUnavailable,
)
from modest_chic_backend.core.rate_limit import RateLimiter, RateLimiterUnavailable
from modest_chic_backend.core.settings import Settings
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.audit.repository import AuditRepository
from modest_chic_backend.modules.auth.models import StaffStatus, StaffUser
from modest_chic_backend.modules.auth.totp import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    verify_totp_code,
)


class TotpEnrollmentService:
    """Create and verify staff TOTP enrollment without exposing stored seeds."""

    def __init__(self, database: Database, redis: Redis, settings: Settings) -> None:
        self._database = database
        self._redis = redis
        self._settings = settings

    async def begin(self, staff_user_id: uuid.UUID) -> tuple[str, str]:
        """Store an encrypted pending seed and return its one-time provisioning material."""
        secret = pyotp.random_base32()
        async with self._database.transaction() as session:
            staff_user = await session.scalar(
                select(StaffUser).where(StaffUser.id == staff_user_id).with_for_update()
            )
            if staff_user is None or staff_user.status != StaffStatus.ACTIVE:
                raise ApplicationError(401, "UNAUTHORIZED", "Authentication is required.")
            if staff_user.totp_enabled:
                raise ApplicationError(409, "TOTP_ALREADY_ENABLED", "TOTP is already enabled.")
            staff_user.totp_secret = encrypt_totp_secret(
                secret, self._settings.totp_encryption_key.get_secret_value().encode("utf-8")
            )
            staff_user.totp_last_counter = None
            await AuditRepository(session).record(
                action="staff.totp.enrollment_started",
                entity_type="staff_user",
                actor_id=staff_user.id,
                entity_id=staff_user.id,
            )
            provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
                name=staff_user.email,
                issuer_name="Modest Chic",
            )
            return secret, provisioning_uri

    async def verify(self, *, staff_user_id: uuid.UUID, code: str, source_network: str) -> bool:
        """Enable TOTP only after accepting a fresh code from the pending seed."""
        await self._enforce_limit(staff_user_id, source_network)
        now = datetime.now(UTC)
        async with self._database.transaction() as session:
            staff_user = await session.scalar(
                select(StaffUser).where(StaffUser.id == staff_user_id).with_for_update()
            )
            if (
                staff_user is None
                or staff_user.status != StaffStatus.ACTIVE
                or staff_user.totp_enabled
                or staff_user.totp_secret is None
            ):
                return False
            secret = decrypt_totp_secret(
                staff_user.totp_secret,
                self._settings.totp_encryption_key.get_secret_value().encode("utf-8"),
            )
            counter = verify_totp_code(
                secret,
                code,
                now=now,
                last_counter=staff_user.totp_last_counter,
            )
            if counter is None:
                await AuditRepository(session).record(
                    action="staff.totp.enrollment_failed",
                    entity_type="staff_user",
                    actor_id=staff_user.id,
                    entity_id=staff_user.id,
                    metadata={"outcome": "denied"},
                )
                return False
            staff_user.totp_enabled = True
            staff_user.totp_last_counter = counter
            await AuditRepository(session).record(
                action="staff.totp.enrollment_completed",
                entity_type="staff_user",
                actor_id=staff_user.id,
                entity_id=staff_user.id,
            )
            return True

    async def _enforce_limit(self, staff_user_id: uuid.UUID, source_network: str) -> None:
        """Limit repeated second-factor guesses by staff identity and network."""
        try:
            allowed = await RateLimiter(self._redis).consume(
                "totp-verify",
                str(staff_user_id),
                source_network,
                limit=5,
                window_seconds=60,
            )
        except RateLimiterUnavailable as error:
            raise RateLimitServiceUnavailable() from error
        if not allowed:
            raise RateLimitExceeded()

"""Staff password reset and authenticated password change transactions."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from html import escape

from redis.asyncio import Redis
from sqlalchemy import select

from modest_chic_backend.core.errors import (
    RateLimitExceeded,
    RateLimitServiceUnavailable,
)
from modest_chic_backend.core.rate_limit import RateLimiter, RateLimiterUnavailable
from modest_chic_backend.core.settings import Settings
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.audit.repository import AuditRepository
from modest_chic_backend.modules.auth.models import (
    StaffPasswordReset,
    StaffStatus,
    StaffUser,
)
from modest_chic_backend.modules.auth.repository import AuthRepository
from modest_chic_backend.modules.auth.security import (
    create_opaque_token,
    hash_password,
    hash_token,
    normalize_email,
    validate_password,
    verify_password,
)
from modest_chic_backend.modules.outbox.service import OutboxService


class PasswordService:
    """Own one-time staff password recovery and credential replacement."""

    def __init__(self, database: Database, redis: Redis, settings: Settings) -> None:
        self._database = database
        self._redis = redis
        self._settings = settings

    async def request_reset(self, *, email: str, source_network: str) -> None:
        """Queue a reset message for active accounts and return identically otherwise."""
        normalized_email = normalize_email(email)
        await self._enforce_limit("password-forgot", normalized_email, source_network)
        now = datetime.now(UTC)
        async with self._database.transaction() as session:
            repository = AuthRepository(session)
            staff_user = await repository.find_user_by_email(normalized_email, lock=True)
            if staff_user is None or staff_user.status != StaffStatus.ACTIVE:
                await AuditRepository(session).record(
                    action="staff.password_reset.requested",
                    entity_type="staff_user",
                    actor_id=None,
                    metadata={"outcome": "accepted"},
                )
                return
            previous_resets = await session.scalars(
                select(StaffPasswordReset)
                .where(
                    StaffPasswordReset.staff_user_id == staff_user.id,
                    StaffPasswordReset.consumed_at.is_(None),
                    StaffPasswordReset.expires_at > now,
                )
                .order_by(StaffPasswordReset.id)
                .with_for_update()
            )
            for previous_reset in previous_resets:
                previous_reset.consumed_at = now
            token = create_opaque_token()
            reset_request = StaffPasswordReset(
                id=uuid.uuid4(),
                staff_user_id=staff_user.id,
                token_hash=hash_token(token),
                expires_at=now + timedelta(minutes=30),
            )
            session.add(reset_request)
            link = f"{str(self._settings.admin_base_url).rstrip('/')}/reset-password?token={token}"
            html_body = (
                "<p>A password reset was requested for your Modest Chic staff account.</p>"
                f'<p><a href="{escape(link, quote=True)}">Reset password</a></p>'
            )
            outbox = OutboxService(
                session, self._settings.outbox_encryption_key.get_secret_value().encode("utf-8")
            )
            await outbox.enqueue_email(
                aggregate_type="staff_password_reset",
                aggregate_id=reset_request.id,
                recipient=normalized_email,
                subject="Reset your Modest Chic staff password",
                html_body=html_body,
            )
            await AuditRepository(session).record(
                action="staff.password_reset.requested",
                entity_type="staff_user",
                actor_id=staff_user.id,
                entity_id=staff_user.id,
                metadata={"outcome": "accepted"},
            )

    async def consume_reset(self, *, token: str, new_password: str, source_network: str) -> bool:
        """Consume an unexpired reset token once and revoke every existing session."""
        validate_password(new_password)
        token_digest = hash_token(token)
        await self._enforce_limit("password-reset", token_digest, source_network)
        password_digest = await asyncio.to_thread(hash_password, new_password)
        now = datetime.now(UTC)
        async with self._database.transaction() as session:
            reset_user_id = await session.scalar(
                select(StaffPasswordReset.staff_user_id).where(
                    StaffPasswordReset.token_hash == token_digest
                )
            )
            if reset_user_id is None:
                return False
            staff_user = await session.scalar(
                select(StaffUser).where(StaffUser.id == reset_user_id).with_for_update()
            )
            if staff_user is None or staff_user.status != StaffStatus.ACTIVE:
                return False
            reset_request = await session.scalar(
                select(StaffPasswordReset)
                .where(
                    StaffPasswordReset.token_hash == token_digest,
                    StaffPasswordReset.staff_user_id == staff_user.id,
                )
                .with_for_update()
            )
            if (
                reset_request is None
                or reset_request.consumed_at is not None
                or reset_request.expires_at <= now
            ):
                return False
            reset_request.consumed_at = now
            staff_user.hashed_password = password_digest
            await AuthRepository(session).revoke_user_sessions(staff_user.id, now)
            await AuditRepository(session).record(
                action="staff.password_reset.completed",
                entity_type="staff_user",
                actor_id=staff_user.id,
                entity_id=staff_user.id,
            )
            return True

    async def change_password(
        self,
        *,
        staff_user_id: uuid.UUID,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Replace the current password only after verifying the existing secret."""
        validate_password(new_password)
        new_digest = await asyncio.to_thread(hash_password, new_password)
        now = datetime.now(UTC)
        async with self._database.transaction() as session:
            staff_user = await session.scalar(
                select(StaffUser).where(StaffUser.id == staff_user_id).with_for_update()
            )
            if staff_user is None or staff_user.status != StaffStatus.ACTIVE:
                return False
            current_hash = staff_user.hashed_password or ""
            current_matches = await asyncio.to_thread(
                verify_password, current_password, current_hash
            )
            if not current_matches:
                await AuditRepository(session).record(
                    action="staff.password_change.failed",
                    entity_type="staff_user",
                    actor_id=staff_user.id,
                    entity_id=staff_user.id,
                    metadata={"outcome": "denied"},
                )
                return False
            staff_user.hashed_password = new_digest
            await AuthRepository(session).revoke_user_sessions(staff_user.id, now)
            await AuditRepository(session).record(
                action="staff.password_changed",
                entity_type="staff_user",
                actor_id=staff_user.id,
                entity_id=staff_user.id,
            )
            return True

    async def _enforce_limit(
        self, operation: str, email_or_token: str, source_network: str
    ) -> None:
        """Rate-limit password operations by a normalized identity and network pair."""
        try:
            allowed = await RateLimiter(self._redis).consume(
                operation,
                email_or_token,
                source_network,
                limit=5,
                window_seconds=3600,
            )
        except RateLimiterUnavailable as error:
            raise RateLimitServiceUnavailable() from error
        if not allowed:
            raise RateLimitExceeded()

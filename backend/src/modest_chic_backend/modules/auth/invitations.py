"""Staff invitation issue, bootstrap, and single-use acceptance flows."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from html import escape

from redis.asyncio import Redis
from sqlalchemy import delete

from modest_chic_backend.core.errors import (
    ApplicationError,
    RateLimitExceeded,
    RateLimitServiceUnavailable,
)
from modest_chic_backend.core.rate_limit import RateLimiter, RateLimiterUnavailable
from modest_chic_backend.core.settings import Settings
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.audit.repository import AuditRepository
from modest_chic_backend.modules.auth.models import (
    StaffInvitation,
    StaffStatus,
    staff_user_roles,
)
from modest_chic_backend.modules.auth.repository import AuthRepository
from modest_chic_backend.modules.auth.security import (
    create_opaque_token,
    hash_password,
    hash_token,
    normalize_email,
    validate_password,
)
from modest_chic_backend.modules.outbox.service import OutboxService


class InvitationService:
    """Own the transactional lifecycle of staff invitations."""

    def __init__(self, database: Database, redis: Redis, settings: Settings) -> None:
        self._database = database
        self._redis = redis
        self._settings = settings

    async def invite_staff(
        self,
        *,
        inviter_id: uuid.UUID,
        email: str,
        role_keys: list[str],
    ) -> None:
        """Create or supersede an invited staff identity and queue its email atomically."""
        normalized_email = normalize_email(email)
        now = datetime.now(UTC)
        token = create_opaque_token()
        async with self._database.transaction() as session:
            repository = AuthRepository(session)
            existing_user = await repository.find_user_by_email(normalized_email, lock=True)
            if existing_user is not None and existing_user.status != StaffStatus.INVITED:
                raise ApplicationError(409, "STAFF_ALREADY_EXISTS", "Staff account already exists.")
            for role_key in role_keys:
                if await repository.get_role(role_key) is None:
                    raise ApplicationError(422, "UNKNOWN_ROLE", "One or more roles are invalid.")
            if existing_user is None:
                user = await repository.create_staff_user(
                    email=normalized_email,
                    display_name=normalized_email,
                    status=StaffStatus.INVITED,
                )
            else:
                user = existing_user
                await repository.expire_pending_invitations(normalized_email, now)
                await session.execute(
                    delete(staff_user_roles).where(staff_user_roles.c.staff_user_id == user.id)
                )
            for role_key in role_keys:
                role = await repository.get_role(role_key)
                if role is not None:
                    await repository.assign_role(user.id, role.id, inviter_id)
            invitation = StaffInvitation(
                id=uuid.uuid4(),
                email=normalized_email,
                token_hash=hash_token(token),
                invited_by=inviter_id,
                expires_at=now + timedelta(hours=24),
            )
            await repository.create_invitation(invitation)
            link = (
                f"{str(self._settings.admin_base_url).rstrip('/')}/accept-invitation?token={token}"
            )
            html_body = (
                "<p>You have been invited to Modest Chic staff.</p>"
                f'<p><a href="{escape(link, quote=True)}">Accept invitation</a></p>'
            )
            outbox = OutboxService(
                session, self._settings.outbox_encryption_key.get_secret_value().encode("utf-8")
            )
            await outbox.enqueue_email(
                aggregate_type="staff_invitation",
                aggregate_id=invitation.id,
                recipient=normalized_email,
                subject="Your Modest Chic staff invitation",
                html_body=html_body,
            )
            await AuditRepository(session).record(
                action="staff.invitation.created",
                entity_type="staff_invitation",
                actor_id=inviter_id,
                entity_id=invitation.id,
                metadata={"role_count": len(role_keys)},
            )

    async def accept_invitation(
        self, *, token: str, password: str, display_name: str, source_network: str
    ) -> bool:
        """Consume a valid invitation once and activate the matching staff account."""
        validate_password(password)
        await self._enforce_acceptance_limit(hash_token(token), source_network)
        password_digest = await asyncio.to_thread(hash_password, password)
        now = datetime.now(UTC)
        async with self._database.transaction() as session:
            repository = AuthRepository(session)
            invitation = await repository.find_invitation_by_hash(hash_token(token), lock=True)
            if (
                invitation is None
                or invitation.accepted_at is not None
                or invitation.expires_at <= now
            ):
                return False
            staff_user = await repository.find_user_by_email(invitation.email, lock=True)
            if staff_user is None or staff_user.status != StaffStatus.INVITED:
                return False
            staff_user.hashed_password = password_digest
            staff_user.display_name = display_name
            staff_user.status = StaffStatus.ACTIVE
            invitation.accepted_at = now
            await AuditRepository(session).record(
                action="staff.invitation.accepted",
                entity_type="staff_user",
                actor_id=staff_user.id,
                entity_id=staff_user.id,
            )
            return True

    async def _enforce_acceptance_limit(self, token_digest: str, source_network: str) -> None:
        """Rate-limit one-time token guesses by token digest and source network."""
        try:
            allowed = await RateLimiter(self._redis).consume(
                "invitation-accept",
                token_digest,
                source_network,
                limit=5,
                window_seconds=3600,
            )
        except RateLimiterUnavailable as error:
            raise RateLimitServiceUnavailable() from error
        if not allowed:
            raise RateLimitExceeded()

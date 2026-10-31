"""Restricted one-time creation path for the first invited owner."""

import uuid
from datetime import UTC, datetime, timedelta
from html import escape

from sqlalchemy import func, select, text

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.core.settings import Settings
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.audit.repository import AuditRepository
from modest_chic_backend.modules.auth.models import StaffInvitation, StaffStatus, StaffUser
from modest_chic_backend.modules.auth.repository import AuthRepository
from modest_chic_backend.modules.auth.security import (
    create_opaque_token,
    hash_token,
    normalize_email,
)
from modest_chic_backend.modules.outbox.service import OutboxService


async def bootstrap_owner(*, email: str, settings: Settings) -> uuid.UUID:
    """Create the first invited owner, self-referencing invitation, and email outbox item."""
    normalized_email = normalize_email(email)
    token = create_opaque_token()
    now = datetime.now(UTC)
    database = Database(str(settings.database_url))
    try:
        async with database.transaction() as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": "modest-chic-bootstrap-owner"},
            )
            user_count = await session.scalar(select(func.count()).select_from(StaffUser))
            if user_count:
                raise ApplicationError(
                    409,
                    "BOOTSTRAP_ALREADY_COMPLETED",
                    "A staff account already exists.",
                )
            repository = AuthRepository(session)
            owner = StaffUser(
                id=uuid.uuid4(),
                email=normalized_email,
                display_name=normalized_email,
                hashed_password=None,
                status=StaffStatus.INVITED,
            )
            session.add(owner)
            await session.flush()
            owner_role = await repository.get_role("owner")
            if owner_role is None:
                raise RuntimeError("owner role was not seeded by the authentication migration")
            await repository.assign_role(owner.id, owner_role.id, owner.id)
            invitation = StaffInvitation(
                id=uuid.uuid4(),
                email=normalized_email,
                token_hash=hash_token(token),
                invited_by=owner.id,
                expires_at=now + timedelta(hours=24),
            )
            await repository.create_invitation(invitation)
            link = f"{str(settings.admin_base_url).rstrip('/')}/accept-invitation?token={token}"
            html_body = (
                "<p>Your Modest Chic owner account is ready to activate.</p>"
                f'<p><a href="{escape(link, quote=True)}">Accept invitation</a></p>'
            )
            outbox = OutboxService(
                session, settings.outbox_encryption_key.get_secret_value().encode("utf-8")
            )
            await outbox.enqueue_email(
                aggregate_type="staff_invitation",
                aggregate_id=invitation.id,
                recipient=normalized_email,
                subject="Activate your Modest Chic owner account",
                html_body=html_body,
            )
            await AuditRepository(session).record(
                action="staff.bootstrap.owner_created",
                entity_type="staff_user",
                actor_id=owner.id,
                entity_id=owner.id,
            )
            return owner.id
    finally:
        await database.dispose()

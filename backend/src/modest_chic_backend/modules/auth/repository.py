"""Database queries for staff identities, invitations, roles, and sessions."""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modest_chic_backend.modules.auth.models import (
    Permission,
    Role,
    StaffInvitation,
    StaffSession,
    StaffStatus,
    StaffUser,
    role_permissions,
    staff_user_roles,
)


class AuthRepository:
    """Keep auth persistence queries within the staff identity module."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_user_by_email(self, email: str, *, lock: bool = False) -> StaffUser | None:
        """Find a staff identity using the database's case-insensitive email key."""
        statement = select(StaffUser).where(
            func.lower(func.trim(StaffUser.email)) == email.strip().lower()
        )
        if lock:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def find_invitation_by_hash(
        self, token_hash: str, *, lock: bool = False
    ) -> StaffInvitation | None:
        """Find a one-time invitation and lock it for a state transition when requested."""
        statement = select(StaffInvitation).where(StaffInvitation.token_hash == token_hash)
        if lock:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def find_session_by_hash(
        self, token_hash: str, *, lock: bool = False
    ) -> StaffSession | None:
        """Find a hashed refresh credential and optionally acquire its row lock."""
        statement = select(StaffSession).where(StaffSession.token_hash == token_hash)
        if lock:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_role(self, role_key: str) -> Role | None:
        """Look up a seeded staff role by its stable key."""
        return await self._session.scalar(select(Role).where(Role.key == role_key))

    async def get_role_for_update(self, role_key: str) -> Role | None:
        """Lock a role row to serialize last-owner membership changes."""
        return await self._session.scalar(
            select(Role).where(Role.key == role_key).with_for_update()
        )

    async def get_roles(self, staff_user_id: uuid.UUID) -> list[str]:
        """Return current assigned role keys in deterministic order."""
        statement = (
            select(Role.key)
            .join(staff_user_roles, staff_user_roles.c.role_id == Role.id)
            .where(staff_user_roles.c.staff_user_id == staff_user_id)
            .order_by(Role.key)
        )
        return list((await self._session.scalars(statement)).all())

    async def get_permissions(self, staff_user_id: uuid.UUID) -> list[str]:
        """Load current permissions from role assignment tables, never JWT claims."""
        statement = (
            select(Permission.key)
            .join(role_permissions, role_permissions.c.permission_id == Permission.id)
            .join(staff_user_roles, staff_user_roles.c.role_id == role_permissions.c.role_id)
            .where(staff_user_roles.c.staff_user_id == staff_user_id)
            .distinct()
            .order_by(Permission.key)
        )
        return list((await self._session.scalars(statement)).all())

    async def expire_pending_invitations(self, email: str, now: datetime) -> None:
        """Supersede all unaccepted invitations for an email without deleting audit history."""
        await self._session.execute(
            update(StaffInvitation)
            .where(
                func.lower(func.trim(StaffInvitation.email)) == email.strip().lower(),
                StaffInvitation.accepted_at.is_(None),
                StaffInvitation.expires_at > now,
            )
            .values(expires_at=now)
        )

    async def revoke_family(self, family_id: uuid.UUID, now: datetime) -> None:
        """Revoke every refresh row in a session family at one timestamp."""
        await self._session.execute(
            update(StaffSession)
            .where(StaffSession.family_id == family_id, StaffSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    async def revoke_user_sessions(self, staff_user_id: uuid.UUID, now: datetime) -> None:
        """Revoke all active refresh rows for a staff identity."""
        await self._session.execute(
            update(StaffSession)
            .where(
                StaffSession.staff_user_id == staff_user_id,
                StaffSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

    async def create_staff_user(
        self,
        *,
        email: str,
        display_name: str,
        status: StaffStatus,
        hashed_password: str | None = None,
        staff_user_id: uuid.UUID | None = None,
    ) -> StaffUser:
        """Add and flush a staff row inside the caller's transaction."""
        user = StaffUser(
            id=staff_user_id or uuid.uuid4(),
            email=email.strip(),
            display_name=display_name,
            status=status,
            hashed_password=hashed_password,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def assign_role(
        self, staff_user_id: uuid.UUID, role_id: uuid.UUID, assigned_by: uuid.UUID | None
    ) -> None:
        """Assign one role, idempotently, within the caller's transaction."""
        await self._session.execute(
            insert(staff_user_roles)
            .values(staff_user_id=staff_user_id, role_id=role_id, assigned_by=assigned_by)
            .on_conflict_do_nothing(index_elements=["staff_user_id", "role_id"])
        )

    async def create_session(self, session: StaffSession) -> None:
        """Insert one hashed refresh credential inside the active transaction."""
        self._session.add(session)
        await self._session.flush()

    async def create_invitation(self, invitation: StaffInvitation) -> None:
        """Insert one hashed invitation inside the active transaction."""
        self._session.add(invitation)
        await self._session.flush()

    async def list_all_staff_with_roles(self) -> list[StaffUser]:
        """Return all staff users with their role assignments eagerly loaded."""
        result = await self._session.execute(
            select(StaffUser).options(selectinload(StaffUser.roles)).order_by(StaffUser.created_at)
        )
        return list(result.scalars().unique().all())

    async def get_staff_user(
        self, staff_user_id: uuid.UUID, *, refresh_roles: bool = False
    ) -> StaffUser | None:
        """Get a staff user by ID with roles loaded."""
        statement = (
            select(StaffUser)
            .options(selectinload(StaffUser.roles))
            .where(StaffUser.id == staff_user_id)
        )
        if refresh_roles:
            statement = statement.execution_options(populate_existing=True)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_staff_user_for_update(self, staff_user_id: uuid.UUID) -> StaffUser | None:
        """Load a staff member and lock it before changing the assigned roles."""
        result = await self._session.execute(
            select(StaffUser)
            .options(selectinload(StaffUser.roles))
            .where(StaffUser.id == staff_user_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def remove_staff_role(self, staff_user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        """Remove a single role assignment."""
        await self._session.execute(
            delete(staff_user_roles).where(
                staff_user_roles.c.staff_user_id == staff_user_id,
                staff_user_roles.c.role_id == role_id,
            )
        )

    async def remove_all_roles(self, staff_user_id: uuid.UUID) -> None:
        """Remove every role assignment for a staff user."""
        await self._session.execute(
            delete(staff_user_roles).where(staff_user_roles.c.staff_user_id == staff_user_id)
        )

    async def count_active_owners(self, *, exclude_user_id: uuid.UUID | None = None) -> int:
        """Count staff with owner role who are ACTIVE and not the excluded ID."""
        stmt = (
            select(func.count())
            .select_from(StaffUser)
            .join(staff_user_roles, staff_user_roles.c.staff_user_id == StaffUser.id)
            .join(Role, Role.id == staff_user_roles.c.role_id)
            .where(
                StaffUser.status == StaffStatus.ACTIVE,
                Role.key == "owner",
            )
        )
        if exclude_user_id is not None:
            stmt = stmt.where(StaffUser.id != exclude_user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

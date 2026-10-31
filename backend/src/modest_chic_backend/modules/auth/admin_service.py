"""Staff access administration — listing, role management, suspend/activate."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.audit.repository import AuditRepository
from modest_chic_backend.modules.auth.models import StaffStatus, StaffUser
from modest_chic_backend.modules.auth.repository import AuthRepository


class StaffStaleEditError(ValueError):
    """A staff role update was based on an outdated user version."""


class StaffAdminService:
    """Owner-facing staff administration with last-owner guard."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AuthRepository(session)
        self._audit = AuditRepository(session)

    async def list_staff(self) -> list[dict[str, Any]]:
        """Return all staff: identity, status, roles, TOTP state — no secrets."""
        users = await self._repo.list_all_staff_with_roles()
        return [
            {
                "id": str(u.id),
                "email": u.email,
                "display_name": u.display_name,
                "status": u.status.value,
                "totp_enabled": u.totp_enabled,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                "roles": [r.key for r in (u.roles or [])],
                "created_at": u.created_at.isoformat(),
                "updated_at": u.updated_at.isoformat(),
            }
            for u in users
        ]

    async def set_roles(
        self,
        staff_user_id: uuid.UUID,
        role_keys: list[str],
        actor_id: uuid.UUID,
        expected_updated_at: datetime,
    ) -> dict[str, Any]:
        """Replace all roles for a staff member atomically.

        Rejects if removing 'owner' from the last active owner.
        """
        user = await self._repo.get_staff_user_for_update(staff_user_id)
        if user is None:
            raise LookupError(f"staff user not found: {staff_user_id}")
        if user.updated_at != expected_updated_at:
            raise StaffStaleEditError("staff member changed since it was loaded; reload and retry")

        current_roles = {r.key for r in (user.roles or [])}
        requested = set(role_keys)

        # Validate all roles exist
        for rk in role_keys:
            role = await self._repo.get_role(rk)
            if role is None:
                raise ValueError(f"unknown role: {rk}")

        # If removing owner, enforce quorum
        if "owner" in current_roles and "owner" not in requested:
            await self._repo.get_role_for_update("owner")
            active_owners = await self._repo.count_active_owners(exclude_user_id=staff_user_id)
            if active_owners == 0:
                raise ValueError("cannot remove the last active owner")

        # Atomically replace: remove all, then assign
        await self._repo.remove_all_roles(staff_user_id)
        for rk in role_keys:
            role = await self._repo.get_role(rk)
            assert role is not None
            await self._repo.assign_role(staff_user_id, role.id, assigned_by=actor_id)

        user.updated_at = datetime.now(UTC)
        user.updated_by = actor_id
        await self._session.flush()

        await self._audit.record(
            action="staff.roles_changed",
            entity_type="staff_user",
            actor_id=actor_id,
            entity_id=staff_user_id,
            metadata={"previous": sorted(current_roles), "new": sorted(requested)},
        )

        # Reload and return
        user = await self._repo.get_staff_user(staff_user_id, refresh_roles=True)
        assert user is not None
        return _make_staff_dict(user)

    async def suspend(self, staff_user_id: uuid.UUID, actor_id: uuid.UUID) -> dict[str, Any]:
        """Suspend a staff member, revoking all sessions immediately.

        Rejects if the target is the last active owner.
        """
        user = await self._repo.get_staff_user(staff_user_id)
        if user is None:
            raise LookupError(f"staff user not found: {staff_user_id}")

        if user.status == StaffStatus.SUSPENDED:
            raise ValueError("staff member is already suspended")

        current_roles = {r.key for r in (user.roles or [])}
        if "owner" in current_roles:
            active_owners = await self._repo.count_active_owners(exclude_user_id=staff_user_id)
            if active_owners == 0:
                raise ValueError("cannot suspend the last active owner")

        from datetime import UTC, datetime

        now = datetime.now(UTC)
        user.status = StaffStatus.SUSPENDED
        user.updated_at = now
        user.updated_by = actor_id
        await self._repo.revoke_user_sessions(staff_user_id, now)

        await self._audit.record(
            action="staff.suspended",
            entity_type="staff_user",
            actor_id=actor_id,
            entity_id=staff_user_id,
            metadata={"previous_status": "ACTIVE"},
        )
        return _make_staff_dict(user)

    async def activate(self, staff_user_id: uuid.UUID, actor_id: uuid.UUID) -> dict[str, Any]:
        """Re-activate a suspended staff member."""
        user = await self._repo.get_staff_user(staff_user_id)
        if user is None:
            raise LookupError(f"staff user not found: {staff_user_id}")

        if user.status != StaffStatus.SUSPENDED:
            raise ValueError("staff member is not suspended")

        user.status = StaffStatus.ACTIVE
        user.updated_at = datetime.now(UTC)
        user.updated_by = actor_id

        await self._audit.record(
            action="staff.activated",
            entity_type="staff_user",
            actor_id=actor_id,
            entity_id=staff_user_id,
            metadata={"previous_status": "SUSPENDED"},
        )
        return _make_staff_dict(user)


def _make_staff_dict(u: StaffUser) -> dict[str, Any]:
    return {
        "id": str(u.id),
        "email": u.email,
        "display_name": u.display_name,
        "status": u.status.value,
        "totp_enabled": u.totp_enabled,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "roles": [r.key for r in (u.roles or [])],
        "created_at": u.created_at.isoformat(),
        "updated_at": u.updated_at.isoformat(),
    }

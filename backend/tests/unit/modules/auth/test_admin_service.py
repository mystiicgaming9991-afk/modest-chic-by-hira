"""Unit tests for staff admin service — last-owner guard, role changes, suspend/activate."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modest_chic_backend.modules.auth.admin_service import (
    StaffAdminService,
    StaffStaleEditError,
    _make_staff_dict,
)
from modest_chic_backend.modules.auth.models import Role, StaffStatus, StaffUser


def _mock_user(
    *,
    user_id: uuid.UUID | None = None,
    status: StaffStatus = StaffStatus.ACTIVE,
    role_keys: tuple[str, ...] = (),
    totp_enabled: bool = False,
) -> StaffUser:
    """Create a mock StaffUser with eager-loaded roles."""
    user = MagicMock(spec=StaffUser)
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.status = status
    user.totp_enabled = totp_enabled
    user.last_login_at = None
    user.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    user.updated_at = datetime(2026, 1, 2, tzinfo=UTC)
    roles = []
    for rk in role_keys:
        role = MagicMock(spec=Role)
        role.key = rk
        role.id = uuid.uuid4()
        roles.append(role)
    user.roles = roles
    return user


# ── list_staff ────────────────────────────────────────────────────


async def test_list_staff_returns_identity_without_secrets() -> None:
    """Staff list shows email, name, status, roles — never password or TOTP secret."""
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)

    user = _mock_user(role_keys=("owner",))

    with patch.object(
        service._repo, "list_all_staff_with_roles", new_callable=AsyncMock
    ) as mock_list:
        mock_list.return_value = [user]
        result = await service.list_staff()

    assert len(result) == 1
    entry = result[0]
    assert entry["email"] == "test@example.com"
    assert entry["status"] == "ACTIVE"
    assert "owner" in entry["roles"]
    # Secrets must never appear
    assert "hashed_password" not in entry
    assert "totp_secret" not in entry
    assert "token_hash" not in entry


async def test_list_staff_shows_totp_enrollment_state() -> None:
    """TOTP enabled flag is exposed but the secret itself is never leaked."""
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)

    enrolled = _mock_user(totp_enabled=True)
    not_enrolled = _mock_user(totp_enabled=False)

    with patch.object(
        service._repo, "list_all_staff_with_roles", new_callable=AsyncMock
    ) as mock_list:
        mock_list.return_value = [enrolled, not_enrolled]
        result = await service.list_staff()

    assert result[0]["totp_enabled"] is True
    assert result[1]["totp_enabled"] is False


# ── set_roles ─────────────────────────────────────────────────────


async def test_set_roles_replaces_all_roles() -> None:
    """set_roles removes existing roles and assigns only the requested ones."""
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)

    user = _mock_user(role_keys=("order_manager", "warehouse"))
    owner_role = MagicMock(spec=Role, key="owner", id=uuid.uuid4())

    with patch.object(
        service._repo, "get_staff_user_for_update", new_callable=AsyncMock
    ) as mock_get_locked:
        mock_get_locked.return_value = user
        with patch.object(service._repo, "get_staff_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _mock_user(role_keys=("owner",))
            with patch.object(service._repo, "get_role", new_callable=AsyncMock) as mock_role:
                mock_role.return_value = owner_role
                with patch.object(
                    service._repo, "remove_all_roles", new_callable=AsyncMock
                ) as mock_remove:
                    with patch.object(
                        service._repo, "assign_role", new_callable=AsyncMock
                    ) as mock_assign:
                        with patch.object(
                            service._audit, "record", new_callable=AsyncMock
                        ) as mock_audit:
                            await service.set_roles(
                                user.id,
                                ["owner"],
                                actor_id=uuid.uuid4(),
                                expected_updated_at=user.updated_at,
                            )

    mock_remove.assert_awaited_once_with(user.id)
    mock_assign.assert_awaited_once()
    mock_audit.assert_awaited_once()


async def test_set_roles_rejects_unknown_role() -> None:
    """Setting an unrecognized role key raises ValueError."""
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)

    user = _mock_user(role_keys=("order_manager",))

    with patch.object(
        service._repo, "get_staff_user_for_update", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = user
        with patch.object(service._repo, "get_role", new_callable=AsyncMock) as mock_role:
            mock_role.return_value = None  # unknown role

            with pytest.raises(ValueError, match="unknown role"):
                await service.set_roles(
                    user.id,
                    ["bogus_role"],
                    actor_id=uuid.uuid4(),
                    expected_updated_at=user.updated_at,
                )


async def test_set_roles_rejects_removing_last_owner() -> None:
    """Cannot remove the owner role if it leaves zero active owners."""
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)

    user = _mock_user(role_keys=("owner",))
    marketing_role = MagicMock(spec=Role, key="marketing", id=uuid.uuid4())

    with patch.object(
        service._repo, "get_staff_user_for_update", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = user
        with patch.object(service._repo, "get_role_for_update", new_callable=AsyncMock):
            with patch.object(service._repo, "get_role", new_callable=AsyncMock) as mock_role:
                mock_role.return_value = marketing_role
                with patch.object(
                    service._repo, "count_active_owners", new_callable=AsyncMock
                ) as mock_count:
                    mock_count.return_value = 0
                    with pytest.raises(ValueError, match="last active owner"):
                        await service.set_roles(
                            user.id,
                            ["marketing"],
                            actor_id=uuid.uuid4(),
                            expected_updated_at=user.updated_at,
                        )


async def test_set_roles_allows_removing_owner_when_another_exists() -> None:
    """Removing owner role is allowed when another active owner remains."""
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)

    user = _mock_user(role_keys=("owner",))
    marketing_role = MagicMock(spec=Role, key="marketing", id=uuid.uuid4())

    with patch.object(
        service._repo, "get_staff_user_for_update", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = user
        with patch.object(service._repo, "get_staff_user", new_callable=AsyncMock) as mock_reload:
            mock_reload.return_value = _mock_user(role_keys=("marketing",))
            with patch.object(service._repo, "get_role_for_update", new_callable=AsyncMock):
                with patch.object(service._repo, "get_role", new_callable=AsyncMock) as mock_role:
                    mock_role.return_value = marketing_role
                    with patch.object(
                        service._repo, "count_active_owners", new_callable=AsyncMock
                    ) as mock_count:
                        mock_count.return_value = 1
                        with patch.object(
                            service._repo, "remove_all_roles", new_callable=AsyncMock
                        ):
                            with patch.object(service._repo, "assign_role", new_callable=AsyncMock):
                                with patch.object(service._audit, "record", new_callable=AsyncMock):
                                    result = await service.set_roles(
                                        user.id,
                                        ["marketing"],
                                        actor_id=uuid.uuid4(),
                                        expected_updated_at=user.updated_at,
                                    )

    assert "marketing" in result["roles"]


async def test_set_roles_raises_for_nonexistent_user() -> None:
    """set_roles on a missing user raises LookupError."""
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)

    with patch.object(
        service._repo, "get_staff_user_for_update", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = None
        with pytest.raises(LookupError, match="staff user not found"):
            await service.set_roles(
                uuid.uuid4(),
                ["owner"],
                actor_id=uuid.uuid4(),
                expected_updated_at=datetime.now(UTC),
            )


async def test_set_roles_rejects_stale_staff_version() -> None:
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)
    user = _mock_user(role_keys=("warehouse",))

    with patch.object(
        service._repo, "get_staff_user_for_update", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = user
        with patch.object(service._repo, "remove_all_roles", new_callable=AsyncMock) as remove:
            stale_version = user.updated_at.replace(day=1)
            with pytest.raises(StaffStaleEditError, match="changed since it was loaded"):
                await service.set_roles(
                    user.id,
                    ["order_manager"],
                    actor_id=uuid.uuid4(),
                    expected_updated_at=stale_version,
                )

    remove.assert_not_awaited()


# ── suspend ───────────────────────────────────────────────────────


async def test_suspend_sets_status_and_revokes_sessions() -> None:
    """Suspending an active user sets SUSPENDED and revokes all sessions."""
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)

    user = _mock_user(role_keys=("warehouse",), status=StaffStatus.ACTIVE)

    with patch.object(service._repo, "get_staff_user", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = user
        with patch.object(
            service._repo, "revoke_user_sessions", new_callable=AsyncMock
        ) as mock_revoke:
            with patch.object(service._audit, "record", new_callable=AsyncMock) as mock_audit:
                result = await service.suspend(user.id, actor_id=uuid.uuid4())

    assert result["status"] == "SUSPENDED"
    mock_revoke.assert_awaited_once()
    mock_audit.assert_awaited_once()


async def test_suspend_rejects_already_suspended() -> None:
    """Suspending an already suspended user raises ValueError."""
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)

    user = _mock_user(role_keys=(), status=StaffStatus.SUSPENDED)

    with patch.object(service._repo, "get_staff_user", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = user
        with pytest.raises(ValueError, match="already suspended"):
            await service.suspend(user.id, actor_id=uuid.uuid4())


async def test_suspend_rejects_last_owner() -> None:
    """Cannot suspend the last active owner."""
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)

    user = _mock_user(role_keys=("owner",), status=StaffStatus.ACTIVE)

    with patch.object(service._repo, "get_staff_user", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = user
        with patch.object(
            service._repo, "count_active_owners", new_callable=AsyncMock
        ) as mock_count:
            mock_count.return_value = 0  # no other active owners

            with pytest.raises(ValueError, match="last active owner"):
                await service.suspend(user.id, actor_id=uuid.uuid4())


async def test_suspend_allows_non_owner_without_quorum_check() -> None:
    """Suspending a non-owner doesn't check the owner quorum."""
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)

    user = _mock_user(role_keys=("warehouse",), status=StaffStatus.ACTIVE)

    with patch.object(service._repo, "get_staff_user", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = user
        with patch.object(service._repo, "revoke_user_sessions", new_callable=AsyncMock):
            with patch.object(
                service._repo, "count_active_owners", new_callable=AsyncMock
            ) as mock_count:
                with patch.object(service._audit, "record", new_callable=AsyncMock):
                    await service.suspend(user.id, actor_id=uuid.uuid4())

    # count_active_owners should NOT have been called for non-owner
    mock_count.assert_not_awaited()


# ── activate ──────────────────────────────────────────────────────


async def test_activate_sets_active_status() -> None:
    """Activating a suspended user sets status to ACTIVE."""
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)

    user = _mock_user(role_keys=(), status=StaffStatus.SUSPENDED)

    with patch.object(service._repo, "get_staff_user", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = user
        with patch.object(service._audit, "record", new_callable=AsyncMock):
            result = await service.activate(user.id, actor_id=uuid.uuid4())

    assert result["status"] == "ACTIVE"


async def test_activate_rejects_non_suspended_user() -> None:
    """Activating an already active user raises ValueError."""
    mock_session = AsyncMock()
    service = StaffAdminService(mock_session)

    user = _mock_user(role_keys=(), status=StaffStatus.ACTIVE)

    with patch.object(service._repo, "get_staff_user", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = user
        with pytest.raises(ValueError, match="not suspended"):
            await service.activate(user.id, actor_id=uuid.uuid4())


# ── _make_staff_dict ──────────────────────────────────────────────


def test_make_staff_dict_excludes_secrets() -> None:
    """The serialized dict never exposes credential fields."""
    user = _mock_user(role_keys=("owner",))
    d = _make_staff_dict(user)
    assert "hashed_password" not in d
    assert "totp_secret" not in d
    assert "totp_last_counter" not in d
    assert d["email"] == "test@example.com"
    assert "owner" in d["roles"]

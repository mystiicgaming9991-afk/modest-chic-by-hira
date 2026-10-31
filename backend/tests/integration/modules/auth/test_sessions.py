import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import delete, select

from modest_chic_backend.core.settings import Settings
from modest_chic_backend.db.database import Database
from modest_chic_backend.main import create_app
from modest_chic_backend.modules.auth.models import (
    Role,
    StaffSession,
    StaffStatus,
    StaffUser,
    staff_user_roles,
)
from modest_chic_backend.modules.auth.security import hash_password, hash_token
from modest_chic_backend.modules.auth.sessions import SessionService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required for PostgreSQL tests"
)


def build_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=os.environ["TEST_DATABASE_URL"],
        redis_url=os.environ.get("TEST_REDIS_URL", "redis://localhost:56379/0"),
        jwt_signing_key="j" * 32,
        csrf_signing_key="c" * 32,
        totp_encryption_key="t" * 32,
        outbox_encryption_key="o" * 32,
        trusted_origins=["http://localhost:3000"],
        admin_base_url="http://localhost:3000/admin",
        email_provider="console",
        email_from="admin@localhost",
    )


def create_client() -> TestClient:
    return TestClient(create_app(build_settings()))


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    token = response.cookies.get("mc_csrf")
    assert token is not None
    return {"Origin": "http://localhost:3000", "X-CSRF-Token": token}


async def create_active_staff(email: str, *, role_key: str | None = None) -> uuid.UUID:
    database = Database(os.environ["TEST_DATABASE_URL"])
    user_id = uuid.uuid4()
    try:
        async with database.transaction() as session:
            session.add(
                StaffUser(
                    id=user_id,
                    email=email,
                    display_name="Session Test Staff",
                    hashed_password=hash_password("valid-password-value-77"),
                    status=StaffStatus.ACTIVE,
                )
            )
            if role_key is not None:
                await session.flush()
                role = await session.scalar(select(Role).where(Role.key == role_key))
                assert role is not None
                await session.execute(
                    staff_user_roles.insert().values(
                        staff_user_id=user_id,
                        role_id=role.id,
                        assigned_by=user_id,
                    )
                )
    finally:
        await database.dispose()
    return user_id


def test_refresh_rotation_replay_revokes_the_entire_family() -> None:
    email = f"refresh-{uuid.uuid4()}@example.com"
    asyncio.run(create_active_staff(email))

    with create_client() as client:
        headers = csrf_headers(client)
        login = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "valid-password-value-77"},
        )
        old_refresh = login.cookies.get("mc_staff_refresh")
        assert old_refresh
        old_access = login.json()["access_token"]
        refreshed = client.post("/api/v1/auth/refresh", headers=headers)
        new_refresh = refreshed.cookies.get("mc_staff_refresh")
        new_access = refreshed.json()["access_token"]
        assert new_refresh and new_refresh != old_refresh

        replay = client.post(
            "/api/v1/auth/refresh",
            headers=headers,
            cookies={"mc_staff_refresh": old_refresh},
        )
        old_access_after_replay = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access}"}
        )
        new_access_after_replay = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"}
        )

    assert refreshed.status_code == 200
    assert replay.status_code == 401
    assert old_access_after_replay.status_code == 401
    assert new_access_after_replay.status_code == 401


def test_logout_revokes_session_and_clears_refresh_cookie() -> None:
    email = f"logout-{uuid.uuid4()}@example.com"
    asyncio.run(create_active_staff(email))

    with create_client() as client:
        headers = csrf_headers(client)
        login = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "valid-password-value-77"},
        )
        access_token = login.json()["access_token"]
        logout = client.post("/api/v1/auth/logout", headers=headers)
        protected = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        )

    assert logout.status_code == 204
    assert "Max-Age=0" in logout.headers["set-cookie"]
    assert protected.status_code == 401


def test_simultaneous_refresh_replay_revokes_the_new_session_family() -> None:
    email = f"concurrent-refresh-{uuid.uuid4()}@example.com"
    asyncio.run(create_active_staff(email))

    with create_client() as client:
        login = client.post(
            "/api/v1/auth/login",
            headers=csrf_headers(client),
            json={"email": email, "password": "valid-password-value-77"},
        )
    refresh_token = login.cookies.get("mc_staff_refresh")
    assert refresh_token is not None

    async def refresh_twice() -> tuple[list[object], list[StaffSession]]:
        database = Database(os.environ["TEST_DATABASE_URL"])
        redis = Redis.from_url(os.environ.get("TEST_REDIS_URL", "redis://localhost:56379/0"))
        try:
            service = SessionService(database, redis, build_settings())
            outcomes = await asyncio.gather(
                service.refresh(refresh_token=refresh_token, source_network="test-a"),
                service.refresh(refresh_token=refresh_token, source_network="test-b"),
            )
            async with database.session() as session:
                family_rows = list(
                    (
                        await session.scalars(
                            select(StaffSession).where(
                                StaffSession.token_hash == hash_token(refresh_token)
                            )
                        )
                    ).all()
                )
                assert len(family_rows) == 1
                descendants = list(
                    (
                        await session.scalars(
                            select(StaffSession).where(
                                StaffSession.family_id == family_rows[0].family_id
                            )
                        )
                    ).all()
                )
                return list(outcomes), descendants
        finally:
            await redis.aclose()
            await database.dispose()

    outcomes, sessions = asyncio.run(refresh_twice())
    assert sum(outcome is not None for outcome in outcomes) == 1
    assert len(sessions) == 2
    assert all(staff_session.revoked_at is not None for staff_session in sessions)


def test_expired_refresh_credential_and_access_session_are_rejected() -> None:
    email = f"expired-session-{uuid.uuid4()}@example.com"
    asyncio.run(create_active_staff(email))

    with create_client() as client:
        headers = csrf_headers(client)
        login = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "valid-password-value-77"},
        )
        refresh_token = login.cookies.get("mc_staff_refresh")
        assert refresh_token is not None

        async def expire_session() -> None:
            database = Database(os.environ["TEST_DATABASE_URL"])
            try:
                async with database.transaction() as session:
                    stored = await session.scalar(
                        select(StaffSession).where(
                            StaffSession.token_hash == hash_token(refresh_token)
                        )
                    )
                    assert stored is not None
                    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            finally:
                await database.dispose()

        asyncio.run(expire_session())
        refresh = client.post("/api/v1/auth/refresh", headers=headers)
        private = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )

    assert refresh.status_code == 401
    assert private.status_code == 401


def test_role_removal_and_suspension_apply_to_existing_access_token() -> None:
    email = f"role-change-{uuid.uuid4()}@example.com"
    user_id = asyncio.run(create_active_staff(email, role_key="owner"))

    with create_client() as client:
        headers = csrf_headers(client)
        login = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "valid-password-value-77"},
        )
        authorization = {"Authorization": f"Bearer {login.json()['access_token']}"}
        before = client.get("/api/v1/auth/me", headers=authorization)

        async def change_access() -> None:
            database = Database(os.environ["TEST_DATABASE_URL"])
            try:
                async with database.transaction() as session:
                    await session.execute(
                        delete(staff_user_roles).where(staff_user_roles.c.staff_user_id == user_id)
                    )
            finally:
                await database.dispose()

        asyncio.run(change_access())
        after_role_removal = client.get("/api/v1/auth/me", headers=authorization)
        forbidden = client.post(
            "/api/v1/admin/staff/invitations",
            headers={**headers, **authorization},
            json={"email": f"invite-{uuid.uuid4()}@example.com", "roles": ["order_manager"]},
        )

        async def suspend_staff() -> None:
            database = Database(os.environ["TEST_DATABASE_URL"])
            try:
                async with database.transaction() as session:
                    staff_user = await session.get(StaffUser, user_id)
                    assert staff_user is not None
                    staff_user.status = StaffStatus.SUSPENDED
            finally:
                await database.dispose()

        asyncio.run(suspend_staff())
        after_suspension = client.get("/api/v1/auth/me", headers=authorization)
        refresh_after_suspension = client.post("/api/v1/auth/refresh", headers=headers)

    assert "staff.manage" in before.json()["permission_keys"]
    assert after_role_removal.status_code == 200
    assert "staff.manage" not in after_role_removal.json()["permission_keys"]
    assert forbidden.status_code == 403
    assert after_suspension.status_code == 401
    assert refresh_after_suspension.status_code == 401

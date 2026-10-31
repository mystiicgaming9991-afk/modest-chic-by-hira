import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from modest_chic_backend.core.settings import Settings
from modest_chic_backend.db.database import Database
from modest_chic_backend.main import create_app
from modest_chic_backend.modules.audit.models import AuditLog
from modest_chic_backend.modules.auth.invitations import InvitationService
from modest_chic_backend.modules.auth.models import (
    Role,
    StaffInvitation,
    StaffStatus,
    StaffUser,
    staff_user_roles,
)
from modest_chic_backend.modules.auth.security import hash_password, hash_token

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


async def create_invited_user(email: str, token: str) -> uuid.UUID:
    database = Database(os.environ["TEST_DATABASE_URL"])
    user_id = uuid.uuid4()
    try:
        async with database.transaction() as session:
            owner = StaffUser(
                id=uuid.uuid4(),
                email=f"owner-{user_id}@example.com",
                display_name="Owner",
                hashed_password=hash_password("owner-password-acceptable"),
                status=StaffStatus.ACTIVE,
            )
            invited = StaffUser(
                id=user_id,
                email=email,
                display_name="",
                hashed_password=None,
                status=StaffStatus.INVITED,
            )
            session.add_all([owner, invited])
            await session.flush()
            role = await session.scalar(select(Role).where(Role.key == "order_manager"))
            assert role is not None
            await session.execute(
                staff_user_roles.insert().values(
                    staff_user_id=user_id, role_id=role.id, assigned_by=owner.id
                )
            )
            session.add(
                StaffInvitation(
                    id=uuid.uuid4(),
                    email=email,
                    token_hash=hash_token(token),
                    invited_by=owner.id,
                    expires_at=__import__("datetime").datetime.now(__import__("datetime").UTC)
                    + __import__("datetime").timedelta(hours=24),
                )
            )
    finally:
        await database.dispose()
    return user_id


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 204
    token = response.cookies.get("mc_csrf")
    assert token is not None
    return {"Origin": "http://localhost:3000", "X-CSRF-Token": token}


def test_invitation_acceptance_activates_account_and_allows_email_password_login() -> None:
    email = f"staff-{uuid.uuid4()}@example.com"
    invitation_token = "invitation-token-" + uuid.uuid4().hex
    user_id = asyncio.run(create_invited_user(email, invitation_token))

    with create_client() as client:
        headers = csrf_headers(client)
        accepted = client.post(
            "/api/v1/auth/accept-invitation",
            headers=headers,
            json={
                "token": invitation_token,
                "password": "correct-horse-battery-7",
                "display_name": "Shop Manager",
            },
        )
        reused = client.post(
            "/api/v1/auth/accept-invitation",
            headers=headers,
            json={
                "token": invitation_token,
                "password": "correct-horse-battery-7",
                "display_name": "Shop Manager",
            },
        )
        login = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email.upper(), "password": "correct-horse-battery-7"},
        )

    assert accepted.status_code == 204
    assert reused.status_code == 400
    assert login.status_code == 200
    assert login.json()["access_token"]
    assert login.json()["expires_in"] == 900
    assert login.json()["staff_user"]["id"] == str(user_id)
    assert "refresh_token" not in login.json()
    refresh_cookie = login.cookies.get("mc_staff_refresh")
    assert refresh_cookie
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "SameSite=strict" in login.headers["set-cookie"]


def test_unknown_and_wrong_password_fail_with_same_generic_response() -> None:
    email = f"active-{uuid.uuid4()}@example.com"
    asyncio.run(create_active_user(email))

    with create_client() as client:
        headers = csrf_headers(client)
        wrong_password = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "incorrect-password-value"},
        )
        unknown_email = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={
                "email": f"unknown-{uuid.uuid4()}@example.com",
                "password": "incorrect-password-value",
            },
        )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_invited_and_suspended_staff_have_the_same_generic_login_failure() -> None:
    invited_email = f"invited-{uuid.uuid4()}@example.com"
    suspended_email = f"suspended-{uuid.uuid4()}@example.com"
    asyncio.run(create_invited_user(invited_email, "invite-" + uuid.uuid4().hex))
    asyncio.run(create_active_user(suspended_email, status=StaffStatus.SUSPENDED))

    with create_client() as client:
        headers = csrf_headers(client)
        invited = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": invited_email, "password": "valid-password-value-77"},
        )
        suspended = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": suspended_email, "password": "valid-password-value-77"},
        )

    assert invited.status_code == suspended.status_code == 401
    assert invited.json() == suspended.json()


def test_expired_invitation_does_not_activate_staff() -> None:
    email = f"expired-{uuid.uuid4()}@example.com"
    token = "invite-" + uuid.uuid4().hex
    user_id = asyncio.run(create_invited_user(email, token))

    async def expire_invitation() -> None:
        database = Database(os.environ["TEST_DATABASE_URL"])
        try:
            async with database.transaction() as session:
                invitation = await session.scalar(
                    select(StaffInvitation).where(StaffInvitation.token_hash == hash_token(token))
                )
                assert invitation is not None
                invitation.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        finally:
            await database.dispose()

    asyncio.run(expire_invitation())
    with create_client() as client:
        response = client.post(
            "/api/v1/auth/accept-invitation",
            headers=csrf_headers(client),
            json={"token": token, "password": "valid-password-value-77", "display_name": "Test"},
        )

    async def current_status() -> StaffStatus:
        database = Database(os.environ["TEST_DATABASE_URL"])
        try:
            async with database.session() as session:
                user = await session.get(StaffUser, user_id)
                assert user is not None
                return user.status
        finally:
            await database.dispose()

    assert response.status_code == 400
    assert asyncio.run(current_status()) == StaffStatus.INVITED


def test_concurrent_invitation_acceptance_succeeds_once_and_audits_once() -> None:
    email = f"concurrent-{uuid.uuid4()}@example.com"
    token = "invite-" + uuid.uuid4().hex
    user_id = asyncio.run(create_invited_user(email, token))

    async def accept_and_inspect() -> tuple[list[bool], int]:
        database = Database(os.environ["TEST_DATABASE_URL"])
        redis = Redis.from_url(os.environ.get("TEST_REDIS_URL", "redis://localhost:56379/0"))
        try:
            service = InvitationService(database, redis, build_settings())
            outcomes = await asyncio.gather(
                service.accept_invitation(
                    token=token,
                    password="valid-password-value-77",
                    display_name="Concurrent Staff",
                    source_network="test-a",
                ),
                service.accept_invitation(
                    token=token,
                    password="valid-password-value-77",
                    display_name="Concurrent Staff",
                    source_network="test-b",
                ),
            )
            async with database.session() as session:
                audit_count = await session.scalar(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(
                        AuditLog.action == "staff.invitation.accepted",
                        AuditLog.actor_id == user_id,
                    )
                )
                return list(outcomes), int(audit_count or 0)
        finally:
            await redis.aclose()
            await database.dispose()

    outcomes, audit_count = asyncio.run(accept_and_inspect())
    assert sorted(outcomes) == [False, True]
    assert audit_count == 1


def test_normalized_email_uniqueness_is_enforced_by_postgresql() -> None:
    email = f"unique-{uuid.uuid4()}@example.com"
    asyncio.run(create_active_user(email))

    async def create_duplicate() -> None:
        database = Database(os.environ["TEST_DATABASE_URL"])
        try:
            async with database.transaction() as session:
                session.add(
                    StaffUser(
                        id=uuid.uuid4(),
                        email=f"  {email.upper()}  ",
                        display_name="Duplicate",
                        hashed_password=hash_password("valid-password-value-77"),
                        status=StaffStatus.ACTIVE,
                    )
                )
                await session.flush()
        finally:
            await database.dispose()

    with pytest.raises(IntegrityError):
        asyncio.run(create_duplicate())


def test_login_throttles_attempts_and_audits_without_passwords() -> None:
    email = f"throttle-{uuid.uuid4()}@example.com"
    asyncio.run(create_active_user(email))
    submitted_password = "deliberately-wrong-password"

    with create_client() as client:
        headers = csrf_headers(client)
        responses = [
            client.post(
                "/api/v1/auth/login",
                headers=headers,
                json={"email": email, "password": submitted_password},
            )
            for _ in range(6)
        ]

    async def failed_audit_records() -> list[AuditLog]:
        database = Database(os.environ["TEST_DATABASE_URL"])
        try:
            async with database.session() as session:
                return list(
                    (
                        await session.scalars(
                            select(AuditLog).where(AuditLog.action == "staff.login.failed")
                        )
                    ).all()
                )
        finally:
            await database.dispose()

    records = asyncio.run(failed_audit_records())
    assert [response.status_code for response in responses] == [401] * 5 + [429]
    assert all(submitted_password not in str(record.event_metadata) for record in records)


async def create_active_user(email: str, *, status: StaffStatus = StaffStatus.ACTIVE) -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    try:
        async with database.transaction() as session:
            user = StaffUser(
                id=uuid.uuid4(),
                email=email,
                display_name="Active Staff",
                hashed_password=hash_password("valid-password-value-77"),
                status=status,
            )
            session.add(user)
    finally:
        await database.dispose()

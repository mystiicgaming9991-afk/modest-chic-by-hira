import asyncio
import os
import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import func, select

from modest_chic_backend.core.settings import Settings
from modest_chic_backend.db.database import Database
from modest_chic_backend.main import create_app
from modest_chic_backend.modules.audit.models import AuditLog
from modest_chic_backend.modules.auth.models import StaffPasswordReset, StaffStatus, StaffUser
from modest_chic_backend.modules.auth.passwords import PasswordService
from modest_chic_backend.modules.auth.security import hash_password, hash_token
from modest_chic_backend.modules.outbox.models import OutboxEvent
from modest_chic_backend.modules.outbox.service import OutboxWorker
from modest_chic_backend.providers.email.memory import MemoryEmailProvider

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required for PostgreSQL tests"
)

OUTBOX_KEY = b"o" * 32


def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=os.environ["TEST_DATABASE_URL"],
        redis_url=os.environ.get("TEST_REDIS_URL", "redis://localhost:56379/0"),
        jwt_signing_key="j" * 32,
        csrf_signing_key="c" * 32,
        totp_encryption_key="t" * 32,
        outbox_encryption_key=OUTBOX_KEY.decode("ascii"),
        trusted_origins=["http://localhost:3000"],
        admin_base_url="http://localhost:3000/admin",
        email_provider="console",
        email_from="admin@localhost",
    )


def create_client() -> TestClient:
    return TestClient(create_app(settings()))


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    token = response.cookies.get("mc_csrf")
    assert token is not None
    return {"Origin": "http://localhost:3000", "X-CSRF-Token": token}


async def create_active_staff(email: str) -> uuid.UUID:
    database = Database(os.environ["TEST_DATABASE_URL"])
    user_id = uuid.uuid4()
    try:
        async with database.transaction() as session:
            session.add(
                StaffUser(
                    id=user_id,
                    email=email,
                    display_name="Password Test Staff",
                    hashed_password=hash_password("old-valid-password-775"),
                    status=StaffStatus.ACTIVE,
                )
            )
    finally:
        await database.dispose()
    return user_id


async def deliver_all_messages(provider: MemoryEmailProvider) -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    redis = Redis.from_url(os.environ.get("TEST_REDIS_URL", "redis://localhost:56379/0"))
    worker = OutboxWorker(database, provider, OUTBOX_KEY)
    try:
        while await worker.deliver_next():
            pass
    finally:
        await redis.aclose()
        await database.dispose()


def test_forgot_response_is_indistinguishable_and_reset_is_single_use() -> None:
    email = f"password-reset-{uuid.uuid4()}@example.com"
    asyncio.run(create_active_staff(email))
    provider = MemoryEmailProvider()
    api_settings = settings()
    application = create_app(api_settings)

    with TestClient(application) as client:
        headers = csrf_headers(client)
        login = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "old-valid-password-775"},
        )
        access_token = login.json()["access_token"]
        known_response = client.post(
            "/api/v1/auth/password/forgot", headers=headers, json={"email": email}
        )
        unknown_response = client.post(
            "/api/v1/auth/password/forgot",
            headers=headers,
            json={"email": f"unknown-{uuid.uuid4()}@example.com"},
        )

    asyncio.run(deliver_all_messages(provider))
    message = next(
        email_message
        for email_message in provider.messages.values()
        if email_message.recipient == email
    )
    token_match = re.search(r"token=([^'\"&]+)", message.html_body)
    assert token_match is not None
    reset_token = token_match.group(1)

    with TestClient(application) as client:
        headers = csrf_headers(client)
        reset = client.post(
            "/api/v1/auth/password/reset",
            headers=headers,
            json={"token": reset_token, "new_password": "new-valid-password-876"},
        )
        reused = client.post(
            "/api/v1/auth/password/reset",
            headers=headers,
            json={"token": reset_token, "new_password": "other-valid-password-987"},
        )
        old_access = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        )
        new_login = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "new-valid-password-876"},
        )

    assert known_response.status_code == unknown_response.status_code == 202
    assert known_response.json() == unknown_response.json()
    assert reset.status_code == 204
    assert reused.status_code == 400
    assert old_access.status_code == 401
    assert new_login.status_code == 200

    async def persisted_outbox_payloads() -> list[str]:
        database = Database(os.environ["TEST_DATABASE_URL"])
        try:
            async with database.session() as session:
                events = await session.scalars(
                    select(OutboxEvent).where(OutboxEvent.aggregate_type == "staff_password_reset")
                )
                return [str(event.payload) for event in events]
        finally:
            await database.dispose()

    assert all(reset_token not in payload for payload in asyncio.run(persisted_outbox_payloads()))


def test_password_change_requires_current_credential_and_revokes_sessions() -> None:
    email = f"password-change-{uuid.uuid4()}@example.com"
    asyncio.run(create_active_staff(email))

    with create_client() as client:
        headers = csrf_headers(client)
        login = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "old-valid-password-775"},
        )
        access_token = login.json()["access_token"]
        authorization = {"Authorization": f"Bearer {access_token}"}
        wrong_current = client.post(
            "/api/v1/auth/password/change",
            headers={**headers, **authorization},
            json={
                "current_password": "incorrect-password",
                "new_password": "new-valid-password-876",
            },
        )
        changed = client.post(
            "/api/v1/auth/password/change",
            headers={**headers, **authorization},
            json={
                "current_password": "old-valid-password-775",
                "new_password": "new-valid-password-876",
            },
        )
        old_session = client.get("/api/v1/auth/me", headers=authorization)

    assert wrong_current.status_code == 401
    assert changed.status_code == 204
    assert old_session.status_code == 401


def test_expired_reset_link_does_not_change_password() -> None:
    email = f"expired-reset-{uuid.uuid4()}@example.com"
    user_id = asyncio.run(create_active_staff(email))
    token = "expired-token-" + uuid.uuid4().hex

    async def create_expired_reset() -> None:
        database = Database(os.environ["TEST_DATABASE_URL"])
        try:
            async with database.transaction() as session:
                session.add(
                    StaffPasswordReset(
                        id=uuid.uuid4(),
                        staff_user_id=user_id,
                        token_hash=hash_token(token),
                        expires_at=datetime.now(UTC) - timedelta(seconds=1),
                    )
                )
        finally:
            await database.dispose()

    asyncio.run(create_expired_reset())
    with create_client() as client:
        headers = csrf_headers(client)
        expired = client.post(
            "/api/v1/auth/password/reset",
            headers=headers,
            json={"token": token, "new_password": "new-valid-password-876"},
        )
        original_password = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "old-valid-password-775"},
        )

    assert expired.status_code == 400
    assert original_password.status_code == 200


def test_new_reset_request_invalidates_previous_reset_link() -> None:
    email = f"superseded-reset-{uuid.uuid4()}@example.com"
    asyncio.run(create_active_staff(email))
    provider = MemoryEmailProvider()
    application = create_app(settings())

    with TestClient(application) as client:
        headers = csrf_headers(client)
        first_request = client.post(
            "/api/v1/auth/password/forgot", headers=headers, json={"email": email}
        )
        second_request = client.post(
            "/api/v1/auth/password/forgot", headers=headers, json={"email": email}
        )

    asyncio.run(deliver_all_messages(provider))
    reset_links = [
        re.search(r"token=([^'\"&]+)", message.html_body) for message in provider.messages.values()
    ]
    reset_tokens = [match.group(1) for match in reset_links if match is not None]
    assert len(reset_tokens) == 2

    with TestClient(application) as client:
        headers = csrf_headers(client)
        superseded = client.post(
            "/api/v1/auth/password/reset",
            headers=headers,
            json={"token": reset_tokens[0], "new_password": "first-reset-password-876"},
        )
        current = client.post(
            "/api/v1/auth/password/reset",
            headers=headers,
            json={"token": reset_tokens[1], "new_password": "second-reset-password-987"},
        )
        old_password = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "old-valid-password-775"},
        )
        current_password = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "second-reset-password-987"},
        )

    assert first_request.status_code == second_request.status_code == 202
    assert superseded.status_code == 400
    assert current.status_code == 204
    assert old_password.status_code == 401
    assert current_password.status_code == 200


def test_concurrent_reset_consumption_succeeds_once_and_audits_once() -> None:
    email = f"concurrent-reset-{uuid.uuid4()}@example.com"
    user_id = asyncio.run(create_active_staff(email))
    token = "reset-token-" + uuid.uuid4().hex

    async def create_reset_and_consume() -> tuple[list[bool], int]:
        database = Database(os.environ["TEST_DATABASE_URL"])
        redis = Redis.from_url(os.environ.get("TEST_REDIS_URL", "redis://localhost:56379/0"))
        try:
            async with database.transaction() as session:
                session.add(
                    StaffPasswordReset(
                        id=uuid.uuid4(),
                        staff_user_id=user_id,
                        token_hash=hash_token(token),
                        expires_at=datetime.now(UTC) + timedelta(minutes=30),
                    )
                )
            service = PasswordService(database, redis, settings())
            outcomes = await asyncio.gather(
                service.consume_reset(
                    token=token,
                    new_password="new-valid-password-876",
                    source_network="test-a",
                ),
                service.consume_reset(
                    token=token,
                    new_password="other-valid-password-987",
                    source_network="test-b",
                ),
            )
            async with database.session() as session:
                audit_count = await session.scalar(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(
                        AuditLog.action == "staff.password_reset.completed",
                        AuditLog.actor_id == user_id,
                    )
                )
                return list(outcomes), int(audit_count or 0)
        finally:
            await redis.aclose()
            await database.dispose()

    outcomes, audit_count = asyncio.run(create_reset_and_consume())
    assert sorted(outcomes) == [False, True]
    assert audit_count == 1

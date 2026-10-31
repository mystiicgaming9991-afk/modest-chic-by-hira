import asyncio
import os
import re
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.core.settings import Settings
from modest_chic_backend.db.database import Database
from modest_chic_backend.main import create_app
from modest_chic_backend.modules.auth.bootstrap import bootstrap_owner
from modest_chic_backend.modules.auth.models import StaffInvitation, StaffStatus, StaffUser
from modest_chic_backend.modules.outbox.crypto import decrypt_payload
from modest_chic_backend.modules.outbox.models import OutboxEvent
from modest_chic_backend.modules.outbox.service import OutboxWorker
from modest_chic_backend.providers.email.memory import MemoryEmailProvider

pytestmark = pytest.mark.skipif(
    not os.getenv("BOOTSTRAP_DATABASE_URL") or not os.getenv("TEST_REDIS_URL"),
    reason="BOOTSTRAP_DATABASE_URL and TEST_REDIS_URL are required for bootstrap integration tests",
)


def build_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=os.environ["BOOTSTRAP_DATABASE_URL"],
        redis_url=os.environ["TEST_REDIS_URL"],
        jwt_signing_key="j" * 32,
        csrf_signing_key="c" * 32,
        totp_encryption_key="t" * 32,
        outbox_encryption_key="o" * 32,
        trusted_origins=["http://localhost:3000"],
        admin_base_url="http://localhost:3000/admin",
        email_provider="console",
        email_from="admin@localhost",
    )


def migrate_bootstrap_database() -> None:
    async def reset_schema() -> None:
        engine = create_async_engine(os.environ["BOOTSTRAP_DATABASE_URL"])
        try:
            async with engine.begin() as connection:
                await connection.exec_driver_sql("DROP SCHEMA public CASCADE")
                await connection.exec_driver_sql("CREATE SCHEMA public")
        finally:
            await engine.dispose()

    asyncio.run(reset_schema())

    async def reset_rate_limits() -> None:
        redis = Redis.from_url(os.environ["TEST_REDIS_URL"])
        try:
            keys = await redis.keys("auth-rate-limit:*")
            if keys:
                await redis.delete(*keys)
        finally:
            await redis.aclose()

    asyncio.run(reset_rate_limits())
    config = Config(str(Path(__file__).parents[4] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", os.environ["BOOTSTRAP_DATABASE_URL"])
    config.attributes["database_url_explicit"] = True
    command.upgrade(config, "head")


def test_bootstrap_creates_invited_owner_without_default_password() -> None:
    migrate_bootstrap_database()
    email = f"founder-{uuid.uuid4()}@example.com"
    settings = build_settings()
    user_id = asyncio.run(bootstrap_owner(email=email, settings=settings))

    async def inspect_bootstrap() -> tuple[StaffUser, StaffInvitation, OutboxEvent]:
        database = Database(settings.database_url)
        try:
            async with database.session() as session:
                user = await session.get(StaffUser, user_id)
                invitation = await session.scalar(
                    select(StaffInvitation).where(StaffInvitation.email == email)
                )
                event = await session.scalar(
                    select(OutboxEvent).where(OutboxEvent.event_type == "email.send")
                )
                assert user and invitation and event
                return user, invitation, event
        finally:
            await database.dispose()

    user, invitation, event = asyncio.run(inspect_bootstrap())
    payload = decrypt_payload(event.payload["encrypted"], b"o" * 32)

    assert user.status == StaffStatus.INVITED
    assert user.hashed_password is None
    assert invitation.invited_by == user.id
    assert len(invitation.token_hash) == 64
    assert email == payload["recipient"]
    assert "token=" in payload["html_body"]

    with pytest.raises(ApplicationError) as error:
        asyncio.run(bootstrap_owner(email=email, settings=settings))
    assert error.value.status_code == 409


def test_bootstrap_email_to_owner_login_refresh_and_logout() -> None:
    migrate_bootstrap_database()
    email = f"owner-smoke-{uuid.uuid4()}@example.com"
    settings = build_settings()
    asyncio.run(bootstrap_owner(email=email, settings=settings))
    provider = MemoryEmailProvider()

    async def deliver_invitation() -> None:
        database = Database(settings.database_url)
        try:
            worker = OutboxWorker(database, provider, b"o" * 32)
            assert await worker.deliver_next()
        finally:
            await database.dispose()

    asyncio.run(deliver_invitation())
    message = next(message for message in provider.messages.values() if message.recipient == email)
    token_match = re.search(r"token=([^'\"&]+)", message.html_body)
    assert token_match is not None

    with TestClient(create_app(settings)) as client:
        csrf = client.get("/api/v1/auth/csrf")
        csrf_token = csrf.cookies.get("mc_csrf")
        assert csrf_token is not None
        headers = {"Origin": "http://localhost:3000", "X-CSRF-Token": csrf_token}
        accepted = client.post(
            "/api/v1/auth/accept-invitation",
            headers=headers,
            json={
                "token": token_match.group(1),
                "password": "owner-password-acceptable",
                "display_name": "Store Owner",
            },
        )
        assert accepted.status_code == 204, accepted.text
        login = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "owner-password-acceptable"},
        )
        assert login.status_code == 200, login.text
        access_token = login.json()["access_token"]
        identity = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        )
        refreshed = client.post("/api/v1/auth/refresh", headers=headers)
        logout = client.post("/api/v1/auth/logout", headers=headers)
        after_logout = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
        )

    assert accepted.status_code == 204
    assert login.status_code == 200
    assert identity.status_code == 200
    assert "staff.manage" in identity.json()["permission_keys"]
    assert refreshed.status_code == 200
    assert logout.status_code == 204
    assert after_logout.status_code == 401

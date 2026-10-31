import asyncio
import os
import uuid

import pyotp
import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from modest_chic_backend.core.settings import Settings
from modest_chic_backend.db.database import Database
from modest_chic_backend.main import create_app
from modest_chic_backend.modules.auth.models import (
    Role,
    StaffStatus,
    StaffUser,
    staff_user_roles,
)
from modest_chic_backend.modules.auth.security import hash_password
from modest_chic_backend.modules.auth.totp import decrypt_totp_secret, encrypt_totp_secret
from modest_chic_backend.modules.auth.totp_service import TotpEnrollmentService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required for PostgreSQL tests"
)

TOTP_KEY = b"t" * 32


def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="production",
        database_url=os.environ["TEST_DATABASE_URL"],
        redis_url=os.environ.get("TEST_REDIS_URL", "redis://localhost:56379/0"),
        jwt_signing_key="j" * 32,
        csrf_signing_key="c" * 32,
        totp_encryption_key=TOTP_KEY.decode("ascii"),
        outbox_encryption_key="o" * 32,
        trusted_origins=["https://admin.example.com"],
        admin_base_url="https://admin.example.com/admin",
        email_provider="resend",
        resend_api_key="r" * 32,
        email_from="admin@example.com",
    )


def create_client() -> TestClient:
    return TestClient(create_app(settings()), base_url="https://testserver")


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    token = response.cookies.get("mc_csrf")
    assert token is not None
    return {"Origin": "https://admin.example.com", "X-CSRF-Token": token}


async def create_staff(email: str, *, totp_secret: str | None = None) -> uuid.UUID:
    database = Database(os.environ["TEST_DATABASE_URL"])
    user_id = uuid.uuid4()
    try:
        async with database.transaction() as session:
            staff_user = StaffUser(
                id=user_id,
                email=email,
                display_name="TOTP Test Owner",
                hashed_password=hash_password("valid-password-value-77"),
                totp_secret=(encrypt_totp_secret(totp_secret, TOTP_KEY) if totp_secret else None),
                totp_enabled=totp_secret is not None,
                status=StaffStatus.ACTIVE,
            )
            session.add(staff_user)
            await session.flush()
            owner_role = await session.scalar(select(Role).where(Role.key == "owner"))
            assert owner_role is not None
            await session.execute(
                insert(staff_user_roles).values(
                    staff_user_id=staff_user.id,
                    role_id=owner_role.id,
                    assigned_by=staff_user.id,
                )
            )
    finally:
        await database.dispose()
    return user_id


def test_production_login_is_restricted_until_totp_enrollment_and_rejects_replay() -> None:
    email = f"totp-enroll-{uuid.uuid4()}@example.com"
    asyncio.run(create_staff(email))

    with create_client() as client:
        headers = csrf_headers(client)
        login = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "valid-password-value-77"},
        )
        access_token = login.json()["access_token"]
        authorization = {"Authorization": f"Bearer {access_token}"}
        limited_identity = client.get("/api/v1/auth/me", headers=authorization)
        forbidden_admin = client.post(
            "/api/v1/admin/staff/invitations",
            headers={**headers, **authorization},
            json={"email": f"invite-{uuid.uuid4()}@example.com", "roles": ["order_manager"]},
        )
        setup = client.post("/api/v1/auth/setup-totp", headers={**headers, **authorization})
        secret = setup.json()["secret"]
        code = pyotp.TOTP(secret).now()
        verified = client.post(
            "/api/v1/auth/verify-totp",
            headers={**headers, **authorization},
            json={"totp_code": code},
        )
        replayed = client.post(
            "/api/v1/auth/verify-totp",
            headers={**headers, **authorization},
            json={"totp_code": code},
        )
        active_identity = client.get("/api/v1/auth/me", headers=authorization)

    assert login.status_code == 200
    assert login.json()["auth_state"] == "TOTP_ENROLLMENT_REQUIRED"
    assert "Secure" in login.headers["set-cookie"]
    assert limited_identity.json()["permission_keys"] == []
    assert forbidden_admin.status_code == 403
    assert setup.status_code == 200
    assert setup.json()["qr_code_url"].startswith("otpauth://totp/")
    assert verified.status_code == 204
    assert replayed.status_code == 400
    assert active_identity.json()["totp_enabled"] is True
    assert "staff.manage" in active_identity.json()["permission_keys"]


def test_totp_enabled_login_requires_a_valid_unused_code() -> None:
    email = f"totp-login-{uuid.uuid4()}@example.com"
    secret = pyotp.random_base32()
    asyncio.run(create_staff(email, totp_secret=secret))

    with create_client() as client:
        headers = csrf_headers(client)
        missing_code = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "valid-password-value-77"},
        )
        code = pyotp.TOTP(secret).now()
        valid_code = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "valid-password-value-77", "totp_code": code},
        )
        replayed_code = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "valid-password-value-77", "totp_code": code},
        )

    assert missing_code.status_code == 401
    assert valid_code.status_code == 200
    assert replayed_code.status_code == 401


def test_wrong_password_does_not_consume_valid_totp_code() -> None:
    email = f"totp-password-{uuid.uuid4()}@example.com"
    secret = pyotp.random_base32()
    asyncio.run(create_staff(email, totp_secret=secret))

    with create_client() as client:
        headers = csrf_headers(client)
        code = pyotp.TOTP(secret).now()
        wrong_password = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "incorrect-password-value", "totp_code": code},
        )
        correct_password = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "valid-password-value-77", "totp_code": code},
        )

    assert wrong_password.status_code == 401
    assert correct_password.status_code == 200


def test_concurrent_totp_enrollment_accepts_code_once_and_encrypts_seed() -> None:
    email = f"totp-concurrent-{uuid.uuid4()}@example.com"
    user_id = asyncio.run(create_staff(email))

    with create_client() as client:
        headers = csrf_headers(client)
        login = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": email, "password": "valid-password-value-77"},
        )
        setup = client.post(
            "/api/v1/auth/setup-totp",
            headers={**headers, "Authorization": f"Bearer {login.json()['access_token']}"},
        )
    secret = setup.json()["secret"]
    code = pyotp.TOTP(secret).now()

    async def verify_twice_and_inspect() -> tuple[list[bool], str, bool]:
        database = Database(os.environ["TEST_DATABASE_URL"])
        redis = Redis.from_url(os.environ.get("TEST_REDIS_URL", "redis://localhost:56379/0"))
        try:
            service = TotpEnrollmentService(database, redis, settings())
            outcomes = await asyncio.gather(
                service.verify(staff_user_id=user_id, code=code, source_network="test-a"),
                service.verify(staff_user_id=user_id, code=code, source_network="test-b"),
            )
            async with database.session() as session:
                staff_user = await session.get(StaffUser, user_id)
                assert staff_user is not None and staff_user.totp_secret is not None
                return list(outcomes), staff_user.totp_secret, staff_user.totp_enabled
        finally:
            await redis.aclose()
            await database.dispose()

    outcomes, encrypted_secret, enabled = asyncio.run(verify_twice_and_inspect())
    assert sorted(outcomes) == [False, True]
    assert enabled is True
    assert secret not in encrypted_secret
    assert decrypt_totp_secret(encrypted_secret, TOTP_KEY) == secret

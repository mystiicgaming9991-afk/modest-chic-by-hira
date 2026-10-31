"""Customer account suspension revokes sessions and is versioned and audited."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.audit.models import AuditLog
from modest_chic_backend.modules.auth.models import StaffStatus, StaffUser
from modest_chic_backend.modules.auth.security import hash_token
from modest_chic_backend.modules.customers.auth_service import CustomerAuthService
from modest_chic_backend.modules.customers.models import (
    Customer,
    CustomerAccount,
    CustomerSession,
)
from modest_chic_backend.modules.customers.service import (
    CustomerAccountStaleEditError,
    CustomerService,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_suspend_revokes_sessions_and_reactivation_requires_fresh_proof() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    suffix = uuid.uuid4().hex
    actor_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    account_id = uuid.uuid4()
    session_id = uuid.uuid4()
    raw_session = "customer-session-" + suffix
    key = b"k" * 32
    try:
        async with database.session() as session:
            async with session.begin():
                actor = StaffUser(
                    id=actor_id,
                    email=f"customer-admin-{suffix}@example.test",
                    display_name="Customer Admin",
                    hashed_password="test-hash",
                    status=StaffStatus.ACTIVE,
                )
                customer = Customer(
                    id=customer_id,
                    email=f"customer-{suffix}@example.test",
                    name="Test Customer",
                )
                account = CustomerAccount(
                    id=account_id,
                    email=f"customer-{suffix}@example.test",
                    customer_id=customer_id,
                    status="ACTIVE",
                )
                customer_session = CustomerSession(
                    id=session_id,
                    customer_id=customer_id,
                    token_hash=hash_token(raw_session),
                    family_id=uuid.uuid4(),
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                )
                session.add_all([actor, customer, account, customer_session])
                await session.flush()
                loaded_at = account.updated_at
                service = CustomerService(session)

                result = await service.set_account_status(
                    customer_id, "SUSPENDED", actor_id, loaded_at
                )
                assert result["status"] == "SUSPENDED"
                await session.refresh(customer_session)
                assert customer_session.revoked_at is not None

                identity = CustomerAuthService(session, "s" * 32, key)
                with pytest.raises(ApplicationError, match="Sign in to continue"):
                    await identity.identity(raw_session)

                search = await service.search_customers(account.email)
                assert len(search) == 1
                assert search[0]["account_status"] == "SUSPENDED"
                assert search[0]["account_email"] == account.email

                with pytest.raises(CustomerAccountStaleEditError):
                    await service.set_account_status(customer_id, "ACTIVE", actor_id, loaded_at)

                activated = await service.set_account_status(
                    customer_id, "ACTIVE", actor_id, account.updated_at
                )
                assert activated["status"] == "ACTIVE"
                with pytest.raises(ApplicationError):
                    await identity.identity(raw_session)

                actions = list(
                    (
                        await session.scalars(
                            select(AuditLog.action)
                            .where(
                                AuditLog.entity_id == account_id,
                                AuditLog.entity_type == "customer_account",
                            )
                            .order_by(AuditLog.created_at, AuditLog.id)
                        )
                    ).all()
                )
                assert sorted(actions) == sorted(
                    [
                        "customer.account_suspended",
                        "customer.account_activated",
                    ]
                )
                await session.rollback()
    finally:
        await database.dispose()

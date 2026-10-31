"""Customer marketing consent withdrawal is append-only and idempotent."""

import os
import uuid

import pytest
from sqlalchemy import select

from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.customers.models import Customer, CustomerContactConsent
from modest_chic_backend.modules.customers.service import CustomerService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_withdrawal_appends_once_and_current_preference_is_suppressed() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    customer_id = uuid.uuid4()
    try:
        async with database.session() as session:
            async with session.begin():
                customer = Customer(
                    id=customer_id,
                    email=f"consent-{uuid.uuid4().hex}@example.test",
                )
                session.add(customer)
                await session.flush()
                service = CustomerService(session)
                await service.record_consent(
                    customer_id=customer_id,
                    channel="email",
                    purpose="marketing",
                    consented=True,
                    source="approved_customer_flow",
                )

                withdrawn = await service.withdraw_marketing_email_consent(customer_id)
                repeated = await service.withdraw_marketing_email_consent(customer_id)
                assert withdrawn is not None and withdrawn["consented"] is False
                assert withdrawn["source"] == "customer_self_service"
                assert repeated is not None and repeated["id"] == withdrawn["id"]
                assert (
                    await service.get_current_consent(customer_id, "email", "marketing")
                    == withdrawn
                )
                decisions = list(
                    (
                        await session.scalars(
                            select(CustomerContactConsent).where(
                                CustomerContactConsent.customer_id == customer_id,
                                CustomerContactConsent.channel == "email",
                                CustomerContactConsent.purpose == "marketing",
                            )
                        )
                    ).all()
                )
                assert len(decisions) == 2
                await session.rollback()
    finally:
        await database.dispose()

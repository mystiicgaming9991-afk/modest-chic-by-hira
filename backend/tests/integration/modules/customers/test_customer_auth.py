"""Email ownership and order credentials gate customer history."""

import os
import re
import uuid

import pytest
from sqlalchemy import select

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.checkout.repository import CheckoutRepository
from modest_chic_backend.modules.customers.auth_service import CustomerAuthService
from modest_chic_backend.modules.customers.models import Customer, CustomerOtpChallenge
from modest_chic_backend.modules.orders.enums import (
    FulfillmentMethod,
    OrderSource,
    OrderState,
    PaymentMethod,
    PaymentState,
)
from modest_chic_backend.modules.orders.models import Order
from modest_chic_backend.modules.outbox.crypto import decrypt_payload
from modest_chic_backend.modules.outbox.models import OutboxEvent

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_email_code_sessions_and_explicit_order_claim() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    email = f"buyer-{uuid.uuid4()}@example.test"
    key = b"k" * 32
    try:
        async with database.session() as session:
            async with session.begin():
                guest = Customer(email=email, name="Guest")
                session.add(guest)
                await session.flush()
                service = CustomerAuthService(session, "signing-key", key)

                async def newest_code() -> str:
                    challenge = await session.scalar(
                        select(CustomerOtpChallenge).where(
                            CustomerOtpChallenge.email == email,
                            CustomerOtpChallenge.superseded_at.is_(None),
                        )
                    )
                    assert challenge is not None
                    event = await session.scalar(
                        select(OutboxEvent).where(
                            OutboxEvent.aggregate_type == "customer_otp",
                            OutboxEvent.aggregate_id == challenge.id,
                        )
                    )
                    assert event is not None
                    body = decrypt_payload(event.payload["encrypted"], key)["html_body"]
                    match = re.search(r"<strong>(\d{6})</strong>", body)
                    assert match is not None
                    return match.group(1)

                await service.request_code(email)
                stale = await newest_code()
                await service.request_code(email)
                fresh = await newest_code()
                assert await service.verify_code(email, stale) is None
                first = await service.verify_code(email, fresh)
                assert first is not None
                token, account = first
                assert account.customer_id != guest.id
                assert await service.verify_code(email, fresh) is None
                assert (await service.identity(token))[1].customer_id == account.customer_id

                order = Order(
                    number=f"T-{uuid.uuid4().hex[:12]}",
                    checkout_idempotency_key=f"test-{uuid.uuid4().hex}",
                    checkout_request_hash="a" * 64,
                    source=OrderSource.STOREFRONT,
                    customer_name="Guest",
                    customer_email=email,
                    fulfillment_method=FulfillmentMethod.PICKUP,
                    payment_method=PaymentMethod.COD,
                    subtotal_minor=1000,
                    total_minor=1000,
                    state=OrderState.PENDING_CONFIRMATION,
                    payment_state=PaymentState.PENDING,
                )
                session.add(order)
                await session.flush()
                assert await service.orders(account) == []
                access, grant = await CheckoutRepository(session, key).create_access_token(order.id)
                grant.scope = "review.create"
                with pytest.raises(ApplicationError):
                    await service.claim_order(account, order.id, "wrong")
                with pytest.raises(ApplicationError):
                    await service.claim_order(account, order.id, access)
                grant.scope = "order.read review.create"
                await service.claim_order(account, order.id, access)
                history = await service.orders(account)
                assert len(history) == 1
                assert history[0]["events"][0]["label"] == "Order saved to your account"

                await service.request_code(email)
                another_code = await newest_code()
                second = await service.verify_code(email, another_code)
                assert second is not None
                second_token, same_account = second
                assert same_account.customer_id == account.customer_id
                await service.logout(await service.identity(second_token), others=True)
                with pytest.raises(ApplicationError):
                    await service.identity(token)
                assert (await service.identity(second_token))[1].customer_id == account.customer_id
                await service.logout(await service.identity(second_token))
                with pytest.raises(ApplicationError):
                    await service.identity(second_token)
                await session.rollback()
    finally:
        await database.dispose()


async def test_bad_code_exhaustion_is_persistent() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    email = f"buyer-{uuid.uuid4()}@example.test"
    key = b"k" * 32
    try:
        async with database.session() as session:
            async with session.begin():
                service = CustomerAuthService(session, "signing-key", key)
                await service.request_code(email)
                event = await session.scalar(
                    select(OutboxEvent)
                    .join(
                        CustomerOtpChallenge,
                        OutboxEvent.aggregate_id == CustomerOtpChallenge.id,
                    )
                    .where(
                        OutboxEvent.aggregate_type == "customer_otp",
                        CustomerOtpChallenge.email == email,
                    )
                )
                assert event is not None
                actual = re.search(
                    r"<strong>(\d{6})</strong>",
                    decrypt_payload(event.payload["encrypted"], key)["html_body"],
                )
                assert actual is not None
                wrong = f"{(int(actual.group(1)) + 1) % 1_000_000:06d}"
                for _ in range(5):
                    assert await service.verify_code(email, wrong) is None
                challenge = await session.scalar(
                    select(CustomerOtpChallenge).where(CustomerOtpChallenge.email == email)
                )
                assert challenge is not None
                assert challenge.failed_attempts == 5
                assert await service.verify_code(email, wrong) is None
                await session.rollback()
    finally:
        await database.dispose()

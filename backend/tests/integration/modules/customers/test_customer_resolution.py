"""Canonical guest profile resolution is concurrency safe without merging people."""

import asyncio
import os
import uuid

import pytest
from sqlalchemy import select

from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.customers.models import Customer
from modest_chic_backend.modules.customers.service import CustomerService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_concurrent_same_identity_resolves_to_one_profile() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    phone = f"03{uuid.uuid4().int % 1_000_000_000:09d}"
    try:

        async def resolve(display_phone: str) -> str:
            async with database.transaction() as session:
                customer = await CustomerService(session).resolve_customer(
                    normalized_phone=display_phone,
                    display_phone=display_phone,
                    name="Shared Test Buyer",
                    email=None,
                )
                return str(customer["id"])

        first, second = await asyncio.gather(resolve(phone), resolve("+92" + phone[1:]))
        assert first == second
        async with database.session() as session:
            profiles = (
                await session.scalars(
                    select(Customer).where(
                        Customer.normalized_phone == "+92" + phone[1:],
                        Customer.name == "Shared Test Buyer",
                    )
                )
            ).all()
            assert len(profiles) == 1
    finally:
        await database.dispose()


async def test_conflicting_names_on_shared_phone_remain_separate() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    phone = f"03{uuid.uuid4().int % 1_000_000_000:09d}"
    try:
        async with database.transaction() as session:
            service = CustomerService(session)
            first = await service.resolve_customer(phone, phone, "Buyer One", None)
            second = await service.resolve_customer(phone, phone, "Buyer Two", None)
            assert first["id"] != second["id"]
            await session.rollback()
    finally:
        await database.dispose()

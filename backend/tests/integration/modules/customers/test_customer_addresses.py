"""Customer address data and default selection stay consistent."""

import asyncio
import os
import uuid
from datetime import datetime

import pytest
from sqlalchemy import select

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.db.database import Database
from modest_chic_backend.modules.customers.models import Customer, CustomerAddress
from modest_chic_backend.modules.customers.service import (
    CustomerAddressStaleEditError,
    CustomerService,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


async def test_default_address_replacement_is_serialized_and_returns_full_address() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    customer_id = uuid.uuid4()
    try:
        async with database.session() as session:
            async with session.begin():
                session.add(Customer(id=customer_id, name="Address Test Buyer"))
                await session.flush()
                service = CustomerService(session)

                first = await service.add_address(
                    customer_id,
                    line1="12 Example Road",
                    city="Karachi",
                    recipient_name="Ayesha Khan",
                    phone="+923001234567",
                    delivery_notes="Call on arrival",
                    is_default=True,
                )
                second = await service.add_address(
                    customer_id,
                    line1="5 Garden Street",
                    city="Lahore",
                    is_default=True,
                )

                assert first["recipient_name"] == "Ayesha Khan"
                assert first["phone"] == "+923001234567"
                assert first["delivery_notes"] == "Call on arrival"
                assert second["is_default"] is True

                addresses = list(
                    (
                        await session.scalars(
                            select(CustomerAddress)
                            .where(CustomerAddress.customer_id == customer_id)
                            .order_by(CustomerAddress.created_at, CustomerAddress.id)
                        )
                    ).all()
                )
                assert len(addresses) == 2
                assert {address.line1: address.is_default for address in addresses} == {
                    "12 Example Road": False,
                    "5 Garden Street": True,
                }
                assert all(address.updated_by is None for address in addresses)
                await session.rollback()
    finally:
        await database.dispose()


async def test_concurrent_default_address_adds_leave_one_default() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    customer_id = uuid.uuid4()
    try:
        async with database.transaction() as session:
            session.add(Customer(id=customer_id, name="Concurrent Address Buyer"))

        async def add_default(line1: str) -> dict[str, object]:
            async with database.transaction() as session:
                return await CustomerService(session).add_address(
                    customer_id,
                    line1=line1,
                    city="Karachi",
                    is_default=True,
                )

        await asyncio.gather(
            add_default("First Concurrent Street"),
            add_default("Second Concurrent Street"),
        )

        async with database.session() as session:
            addresses = list(
                (
                    await session.scalars(
                        select(CustomerAddress).where(CustomerAddress.customer_id == customer_id)
                    )
                ).all()
            )
            assert len(addresses) == 2
            assert sum(address.is_default for address in addresses) == 1
    finally:
        async with database.transaction() as session:
            customer = await session.get(Customer, customer_id)
            if customer is not None:
                await session.delete(customer)
        await database.dispose()


async def test_address_edit_is_version_checked_and_replaces_default() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    customer_id = uuid.uuid4()
    try:
        async with database.transaction() as session:
            session.add(Customer(id=customer_id, name="Address Edit Buyer"))

        async with database.transaction() as session:
            service = CustomerService(session)
            old_default = await service.add_address(
                customer_id, line1="Old Street", city="Karachi", is_default=True
            )
            other = await service.add_address(customer_id, line1="Other Street", city="Lahore")
            updated = await service.update_address(
                customer_id,
                uuid.UUID(old_default["id"]),
                expected_updated_at=datetime.fromisoformat(old_default["updated_at"]),
                actor_id=None,  # type: ignore[arg-type]
                line1="New Street",
                city="Islamabad",
                recipient_name="Ayesha Khan",
                phone=None,
                line2=None,
                area=None,
                postal_code=None,
                delivery_notes=None,
                country_code="PK",
                is_default=True,
            )
            assert updated["line1"] == "New Street"
            assert updated["updated_at"] != old_default["updated_at"]

            with pytest.raises(CustomerAddressStaleEditError):
                await service.update_address(
                    customer_id,
                    uuid.UUID(old_default["id"]),
                    expected_updated_at=datetime.fromisoformat(old_default["updated_at"]),
                    actor_id=None,  # type: ignore[arg-type]
                    line1="Stale Street",
                    city="Karachi",
                    recipient_name=None,
                    phone=None,
                    line2=None,
                    area=None,
                    postal_code=None,
                    delivery_notes=None,
                    country_code="PK",
                    is_default=False,
                )

            promoted = await service.update_address(
                customer_id,
                uuid.UUID(other["id"]),
                expected_updated_at=datetime.fromisoformat(other["updated_at"]),
                actor_id=None,  # type: ignore[arg-type]
                line1="Other Street",
                city="Lahore",
                recipient_name=None,
                phone=None,
                line2=None,
                area=None,
                postal_code=None,
                delivery_notes=None,
                country_code="PK",
                is_default=True,
            )
            default_updates = promoted["default_address_updates"]
            assert len(default_updates) == 1
            assert default_updates[0]["id"] == old_default["id"]
            assert default_updates[0]["updated_at"] != updated["updated_at"]

        async with database.session() as session:
            addresses = list(
                (
                    await session.scalars(
                        select(CustomerAddress).where(CustomerAddress.customer_id == customer_id)
                    )
                ).all()
            )
            assert {address.line1: address.is_default for address in addresses} == {
                "New Street": False,
                "Other Street": True,
            }
    finally:
        async with database.transaction() as session:
            customer = await session.get(Customer, customer_id)
            if customer is not None:
                await session.delete(customer)
        await database.dispose()


async def test_address_edit_cannot_cross_customer_boundary() -> None:
    database = Database(os.environ["TEST_DATABASE_URL"])
    customer_id = uuid.uuid4()
    other_customer_id = uuid.uuid4()
    try:
        async with database.transaction() as session:
            session.add_all(
                [
                    Customer(id=customer_id, name="Address Owner"),
                    Customer(id=other_customer_id, name="Different Owner"),
                ]
            )
        async with database.transaction() as session:
            address = await CustomerService(session).add_address(
                customer_id, line1="Private Street", city="Karachi"
            )
        async with database.transaction() as session:
            with pytest.raises(ApplicationError) as error:
                await CustomerService(session).update_address(
                    other_customer_id,
                    uuid.UUID(address["id"]),
                    expected_updated_at=datetime.fromisoformat(address["updated_at"]),
                    actor_id=None,  # type: ignore[arg-type]
                    line1="Attempted Change",
                    city="Lahore",
                    recipient_name=None,
                    phone=None,
                    line2=None,
                    area=None,
                    postal_code=None,
                    delivery_notes=None,
                    country_code="PK",
                    is_default=False,
                )
            assert error.value.status_code == 404
    finally:
        async with database.transaction() as session:
            for customer_id_to_delete in (customer_id, other_customer_id):
                customer = await session.get(Customer, customer_id_to_delete)
                if customer is not None:
                    await session.delete(customer)
        await database.dispose()

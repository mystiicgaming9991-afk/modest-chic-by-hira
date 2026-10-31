"""Customer database access — profiles, addresses, consent records."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from modest_chic_backend.modules.customers.models import (
    Customer,
    CustomerAccount,
    CustomerAddress,
    CustomerContactConsent,
)
from modest_chic_backend.modules.orders.models import Order, OrderEvent


class CustomerRepository:
    """Read/write customer entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_normalized_phone(self, phone: str) -> list[Customer]:
        result = await self._session.execute(
            select(Customer)
            .where(Customer.normalized_phone == phone, Customer.merged_into_id.is_(None))
            .order_by(Customer.created_at, Customer.id)
        )
        return list(result.scalars().all())

    async def get_customer(self, customer_id: uuid.UUID) -> Customer | None:
        return await self._session.get(Customer, customer_id)

    async def get_customer_for_update(self, customer_id: uuid.UUID) -> Customer | None:
        result = await self._session.execute(
            select(Customer).where(Customer.id == customer_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def search_customers(
        self, query: str, phone: str | None
    ) -> list[tuple[Customer, CustomerAccount | None]]:
        pattern = f"%{query.strip().casefold()}%"
        conditions: list[ColumnElement[bool]] = [
            func.lower(Customer.name).like(pattern),
            func.lower(Customer.email).like(pattern),
        ]
        if phone:
            conditions.append(Customer.normalized_phone == phone)
        result = await self._session.execute(
            select(Customer, CustomerAccount)
            .outerjoin(CustomerAccount, CustomerAccount.customer_id == Customer.id)
            .where(Customer.merged_into_id.is_(None), or_(*conditions))
            .order_by(Customer.created_at.desc(), Customer.id)
            .limit(50)
        )
        return list(result.all())

    async def get_account_for_update(self, customer_id: uuid.UUID) -> CustomerAccount | None:
        result = await self._session.execute(
            select(CustomerAccount)
            .where(CustomerAccount.customer_id == customer_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_customer_orders(self, customer_id: uuid.UUID) -> list[Order]:
        result = await self._session.execute(
            select(Order)
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc(), Order.id)
            .limit(100)
        )
        return list(result.scalars().all())

    async def list_order_events(self, order_ids: list[uuid.UUID]) -> list[OrderEvent]:
        if not order_ids:
            return []
        result = await self._session.execute(
            select(OrderEvent)
            .where(OrderEvent.order_id.in_(order_ids))
            .order_by(OrderEvent.effective_at, OrderEvent.id)
        )
        return list(result.scalars().all())

    async def create_customer(
        self,
        normalized_phone: str | None,
        display_phone: str | None,
        name: str | None,
        email: str | None,
    ) -> Customer:
        customer = Customer(
            normalized_phone=normalized_phone,
            display_phone=display_phone,
            name=name,
            email=email,
        )
        self._session.add(customer)
        await self._session.flush()
        return customer

    async def create_address(
        self,
        customer_id: uuid.UUID,
        line1: str,
        city: str,
        *,
        recipient_name: str | None = None,
        phone: str | None = None,
        line2: str | None = None,
        area: str | None = None,
        postal_code: str | None = None,
        delivery_notes: str | None = None,
        country_code: str = "PK",
        is_default: bool = False,
        actor_id: uuid.UUID | None = None,
    ) -> CustomerAddress:
        """Persist an address, replacing any existing default when requested.

        The application service locks the customer row before this mutation so
        concurrent default-address changes are serialized.
        """
        address = CustomerAddress(
            customer_id=customer_id,
            line1=line1,
            city=city,
            recipient_name=recipient_name,
            phone=phone,
            line2=line2,
            area=area,
            postal_code=postal_code,
            delivery_notes=delivery_notes,
            country_code=country_code,
            is_default=is_default,
            created_by=actor_id,
        )
        self._session.add(address)
        await self._session.flush()
        return address

    async def list_addresses(self, customer_id: uuid.UUID) -> list[CustomerAddress]:
        result = await self._session.execute(
            select(CustomerAddress)
            .where(CustomerAddress.customer_id == customer_id)
            .order_by(CustomerAddress.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_address_for_update(
        self, customer_id: uuid.UUID, address_id: uuid.UUID
    ) -> CustomerAddress | None:
        result = await self._session.execute(
            select(CustomerAddress)
            .where(
                CustomerAddress.id == address_id,
                CustomerAddress.customer_id == customer_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def clear_default_addresses(
        self,
        customer_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None,
        updated_at: datetime,
        except_address_id: uuid.UUID | None = None,
    ) -> list[uuid.UUID]:
        statement = update(CustomerAddress).where(
            CustomerAddress.customer_id == customer_id,
            CustomerAddress.is_default.is_(True),
        )
        if except_address_id is not None:
            statement = statement.where(CustomerAddress.id != except_address_id)
        result = await self._session.execute(
            statement.values(
                is_default=False, updated_at=updated_at, updated_by=actor_id
            ).returning(CustomerAddress.id)
        )
        return list(result.scalars().all())

    async def record_consent(
        self,
        customer_id: uuid.UUID,
        channel: str,
        purpose: str,
        consented: bool,
        source: str | None = None,
        policy_version_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        *,
        recorded_at: datetime,
    ) -> CustomerContactConsent:
        consent = CustomerContactConsent(
            customer_id=customer_id,
            channel=channel,
            purpose=purpose,
            consented=consented,
            source=source,
            policy_version_id=policy_version_id,
            created_by=actor_id,
            recorded_at=recorded_at,
        )
        self._session.add(consent)
        await self._session.flush()
        return consent

    async def get_latest_consent(
        self, customer_id: uuid.UUID, channel: str, purpose: str
    ) -> CustomerContactConsent | None:
        result = await self._session.execute(
            select(CustomerContactConsent)
            .where(
                CustomerContactConsent.customer_id == customer_id,
                CustomerContactConsent.channel == channel,
                CustomerContactConsent.purpose == purpose,
            )
            .order_by(CustomerContactConsent.recorded_at.desc(), CustomerContactConsent.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

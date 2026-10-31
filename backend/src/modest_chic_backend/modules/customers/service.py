"""Customer business logic — profile resolution, addresses, consent."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.audit.repository import AuditRepository
from modest_chic_backend.modules.customers.models import CustomerSession
from modest_chic_backend.modules.customers.repository import CustomerRepository


class CustomerAccountStaleEditError(ValueError):
    """A customer account status update used an outdated version."""


class CustomerAddressStaleEditError(ValueError):
    """A customer address update used an outdated version."""


class CustomerService:
    """Application service for guest customer identity and consent."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CustomerRepository(session)
        self._audit = AuditRepository(session)

    async def resolve_customer(
        self,
        normalized_phone: str | None,
        display_phone: str | None,
        name: str | None,
        email: str | None,
    ) -> dict[str, Any]:
        """Resolve a buyer under a phone lock without merging conflicting identities."""
        if not normalized_phone:
            customer = await self._repo.create_customer(
                normalized_phone=None,
                display_phone=display_phone,
                name=name,
                email=email,
            )
            return _customer_dict(customer)

        phone = normalize_phone(normalized_phone)
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": "customer-phone:" + phone},
        )
        matches = await self._repo.find_by_normalized_phone(phone)
        name_key = normalize_name(name)
        matching = [customer for customer in matches if normalize_name(customer.name) == name_key]
        if name_key:
            existing = matching[0] if matching else None
        else:
            existing = matches[0] if len(matches) == 1 else None
        if existing:
            if not existing.display_phone:
                existing.display_phone = display_phone
            if not existing.name and name:
                existing.name = name.strip()
            if not existing.email and email:
                existing.email = email.strip()
            await self._session.flush()
            return _customer_dict(existing)

        customer = await self._repo.create_customer(
            normalized_phone=phone,
            display_phone=display_phone,
            name=name,
            email=email,
        )
        return _customer_dict(customer)

    async def add_address(
        self,
        customer_id: uuid.UUID,
        line1: str,
        city: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a reusable address while serializing default-address changes.

        Raises ``CUSTOMER_NOT_FOUND`` when the target profile does not exist.
        """
        if await self._repo.get_customer_for_update(customer_id) is None:
            raise ApplicationError(404, "CUSTOMER_NOT_FOUND", "Customer profile not found.")
        default_address_updates: list[dict[str, str]] = []
        if kwargs.get("is_default"):
            updated_at = datetime.now(UTC)
            updated_ids = await self._repo.clear_default_addresses(
                customer_id,
                actor_id=kwargs.get("actor_id"),
                updated_at=updated_at,
            )
            default_address_updates = [
                {"id": str(address_id), "updated_at": updated_at.isoformat()}
                for address_id in updated_ids
            ]
        addr = await self._repo.create_address(
            customer_id=customer_id, line1=line1, city=city, **kwargs
        )
        return {**_address_dict(addr), "default_address_updates": default_address_updates}

    async def list_addresses(self, customer_id: uuid.UUID) -> list[dict[str, Any]]:
        addrs = await self._repo.list_addresses(customer_id)
        return [_address_dict(a) for a in addrs]

    async def update_address(
        self,
        customer_id: uuid.UUID,
        address_id: uuid.UUID,
        *,
        expected_updated_at: datetime,
        actor_id: uuid.UUID,
        **values: Any,
    ) -> dict[str, Any]:
        """Update a reusable address after locking its owning customer and version."""
        if await self._repo.get_customer_for_update(customer_id) is None:
            raise ApplicationError(404, "CUSTOMER_NOT_FOUND", "Customer profile not found.")
        address = await self._repo.get_address_for_update(customer_id, address_id)
        if address is None:
            raise ApplicationError(404, "CUSTOMER_ADDRESS_NOT_FOUND", "Saved address not found.")
        if address.updated_at != expected_updated_at:
            raise CustomerAddressStaleEditError(
                "customer address changed since it was loaded; reload and retry"
            )
        is_default = values.pop("is_default")
        default_address_updates: list[dict[str, str]] = []
        if is_default:
            updated_at = datetime.now(UTC)
            updated_ids = await self._repo.clear_default_addresses(
                customer_id,
                except_address_id=address_id,
                actor_id=actor_id,
                updated_at=updated_at,
            )
            default_address_updates = [
                {"id": str(updated_id), "updated_at": updated_at.isoformat()}
                for updated_id in updated_ids
            ]
        for field, value in values.items():
            setattr(address, field, value)
        address.is_default = is_default
        address.updated_at = datetime.now(UTC)
        address.updated_by = actor_id
        await self._session.flush()
        return {**_address_dict(address), "default_address_updates": default_address_updates}

    async def record_consent(
        self,
        customer_id: uuid.UUID,
        channel: str,
        purpose: str,
        consented: bool,
        source: str | None = None,
        policy_version_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        await self._lock_consent_customer(customer_id)
        return await self._append_consent(
            customer_id=customer_id,
            channel=channel,
            purpose=purpose,
            consented=consented,
            source=source,
            policy_version_id=policy_version_id,
            actor_id=actor_id,
        )

    async def get_current_consent(
        self, customer_id: uuid.UUID, channel: str, purpose: str
    ) -> dict[str, Any] | None:
        c = await self._repo.get_latest_consent(customer_id, channel, purpose)
        if c is None:
            return None
        return _consent_dict(c)

    async def withdraw_marketing_email_consent(
        self, customer_id: uuid.UUID
    ) -> dict[str, Any] | None:
        await self._lock_consent_customer(customer_id)
        current = await self.get_current_consent(customer_id, "email", "marketing")
        if current is None or not current["consented"]:
            return current
        version_id = (
            uuid.UUID(str(current["policy_version_id"])) if current["policy_version_id"] else None
        )
        return await self._append_consent(
            customer_id=customer_id,
            channel="email",
            purpose="marketing",
            consented=False,
            source="customer_self_service",
            policy_version_id=version_id,
        )

    async def _lock_consent_customer(self, customer_id: uuid.UUID) -> None:
        if await self._repo.get_customer_for_update(customer_id) is None:
            raise ApplicationError(404, "CUSTOMER_NOT_FOUND", "Customer profile not found.")

    async def _append_consent(
        self,
        *,
        customer_id: uuid.UUID,
        channel: str,
        purpose: str,
        consented: bool,
        source: str | None,
        policy_version_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        latest = await self._repo.get_latest_consent(customer_id, channel, purpose)
        recorded_at = datetime.now(UTC)
        if latest is not None and recorded_at <= latest.recorded_at:
            recorded_at = latest.recorded_at + timedelta(microseconds=1)
        consent = await self._repo.record_consent(
            customer_id=customer_id,
            channel=channel,
            purpose=purpose,
            consented=consented,
            source=source,
            policy_version_id=policy_version_id,
            actor_id=actor_id,
            recorded_at=recorded_at,
        )
        return _consent_dict(consent)

    async def search_customers(self, query: str) -> list[dict[str, Any]]:
        """Return a bounded, minimal staff search result for active profiles."""
        try:
            phone = normalize_phone(query)
        except ApplicationError:
            phone = None
        customers = await self._repo.search_customers(query, phone)
        return [
            {
                **_customer_dict(customer),
                "account_status": account.status if account else None,
                "account_email": account.email if account else None,
                "account_updated_at": account.updated_at.isoformat() if account else None,
            }
            for customer, account in customers
        ]

    async def set_account_status(
        self,
        customer_id: uuid.UUID,
        status: str,
        actor_id: uuid.UUID,
        expected_updated_at: datetime,
    ) -> dict[str, object]:
        if status not in {"ACTIVE", "SUSPENDED"}:
            raise ValueError("account status must be ACTIVE or SUSPENDED")
        account = await self._repo.get_account_for_update(customer_id)
        if account is None:
            raise ApplicationError(
                404, "CUSTOMER_ACCOUNT_NOT_FOUND", "Customer has no verified account."
            )
        if account.updated_at != expected_updated_at:
            raise CustomerAccountStaleEditError(
                "customer account changed since it was loaded; reload and retry"
            )
        if account.status == status:
            return {
                "customer_id": str(customer_id),
                "status": account.status,
                "updated_at": account.updated_at.isoformat(),
            }

        previous_status = account.status
        now = datetime.now(UTC)
        account.status = status
        account.updated_at = now
        account.updated_by = actor_id
        if status == "SUSPENDED":
            await self._session.execute(
                update(CustomerSession)
                .where(
                    CustomerSession.customer_id == customer_id,
                    CustomerSession.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
        await self._audit.record(
            action=(
                "customer.account_suspended"
                if status == "SUSPENDED"
                else "customer.account_activated"
            ),
            entity_type="customer_account",
            actor_id=actor_id,
            entity_id=account.id,
            metadata={"previous_status": previous_status, "new_status": status},
        )
        return {
            "customer_id": str(customer_id),
            "status": account.status,
            "updated_at": account.updated_at.isoformat(),
        }

    async def customer_order_history(self, customer_id: uuid.UUID) -> list[dict[str, Any]]:
        """Return linked order snapshots and safe status events for staff history."""
        orders = await self._repo.list_customer_orders(customer_id)
        events = await self._repo.list_order_events([order.id for order in orders])
        events_by_order: dict[uuid.UUID, list[dict[str, Any]]] = {}
        for event in events:
            events_by_order.setdefault(event.order_id, []).append(
                {
                    "event_type": event.event_type,
                    "previous_state": event.previous_state.value if event.previous_state else None,
                    "new_state": event.new_state.value if event.new_state else None,
                    "effective_at": event.effective_at.isoformat(),
                }
            )
        return [
            {
                "order_id": str(order.id),
                "order_number": order.number,
                "state": order.state.value,
                "payment_method": order.payment_method.value,
                "payment_state": order.payment_state.value,
                "fulfillment_method": order.fulfillment_method.value,
                "total_minor": order.total_minor,
                "created_at": order.created_at.isoformat(),
                "events": events_by_order.get(order.id, []),
            }
            for order in orders
        ]


def _customer_dict(c: Any) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "normalized_phone": c.normalized_phone,
        "display_phone": c.display_phone,
        "name": c.name,
        "email": c.email,
    }


def normalize_phone(value: str) -> str:
    """Normalize a phone into a plus-prefixed digit form; bare PK mobile numbers use +92."""
    raw = value.strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        normalized_digits = digits
    elif raw.startswith("00"):
        normalized_digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        normalized_digits = "92" + digits[1:]
    elif len(digits) == 10 and digits.startswith("3"):
        normalized_digits = "92" + digits
    else:
        normalized_digits = digits
    if not 7 <= len(normalized_digits) <= 15:
        raise ApplicationError(422, "INVALID_PHONE", "Enter a valid contact phone number.")
    return "+" + normalized_digits


def normalize_name(value: str | None) -> str:
    """Collapse whitespace and case-fold a display name for safe identity comparison."""
    return " ".join(value.split()).casefold() if value else ""


def _address_dict(a: Any) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "customer_id": str(a.customer_id),
        "recipient_name": a.recipient_name,
        "phone": a.phone,
        "line1": a.line1,
        "line2": a.line2,
        "city": a.city,
        "area": a.area,
        "postal_code": a.postal_code,
        "delivery_notes": a.delivery_notes,
        "country_code": a.country_code,
        "is_default": a.is_default,
        "updated_at": a.updated_at.isoformat(),
    }


def _consent_dict(c: Any) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "customer_id": str(c.customer_id),
        "channel": c.channel,
        "purpose": c.purpose,
        "consented": c.consented,
        "source": c.source,
        "policy_version_id": str(c.policy_version_id) if c.policy_version_id else None,
        "recorded_at": c.recorded_at.isoformat(),
    }

"""Customer profile resolution, addresses, and consent service tests."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.customers.models import (
    Customer,
    CustomerAddress,
    CustomerContactConsent,
)


def _customer(**kw: object) -> MagicMock:
    c = MagicMock(spec=Customer)
    c.id = uuid.uuid4()
    c.normalized_phone = "+923001234567"
    c.display_phone = "03001234567"
    c.name = "Test Customer"
    c.email = None
    c.merged_into_id = None
    for k, v in kw.items():
        if v is not None:
            setattr(c, k, v)
    return c


# ── Resolve Customer ──────────────────────────────────────────────


async def test_resolve_creates_new_customer_when_no_match() -> None:
    from modest_chic_backend.modules.customers.service import CustomerService

    mock_session = AsyncMock()
    svc = CustomerService(mock_session)

    with patch.object(svc._repo, "find_by_normalized_phone", new_callable=AsyncMock) as find:
        find.return_value = []
        with patch.object(svc._repo, "create_customer", new_callable=AsyncMock) as create:
            new_cust = _customer()
            create.return_value = new_cust
            result = await svc.resolve_customer(
                normalized_phone="+923001234567",
                display_phone="03001234567",
                name="New Buyer",
                email=None,
            )

    find.assert_awaited_once_with("+923001234567")
    create.assert_awaited_once()
    assert result["id"] == str(new_cust.id)


async def test_resolve_returns_existing_on_phone_match() -> None:
    from modest_chic_backend.modules.customers.service import CustomerService

    mock_session = AsyncMock()
    svc = CustomerService(mock_session)
    existing = _customer(name="Repeat Buyer")

    with patch.object(svc._repo, "find_by_normalized_phone", new_callable=AsyncMock) as find:
        find.return_value = [existing]
        result = await svc.resolve_customer(
            normalized_phone="03001234567",
            display_phone="03001234567",
            name="Repeat Buyer",
            email=None,
        )

    assert result["id"] == str(existing.id)
    assert existing.normalized_phone == "+923001234567"


async def test_resolve_does_not_merge_conflicting_name_on_shared_phone() -> None:
    from modest_chic_backend.modules.customers.service import CustomerService

    mock_session = AsyncMock()
    svc = CustomerService(mock_session)
    existing = _customer(name="Another Buyer")

    with patch.object(svc._repo, "find_by_normalized_phone", new_callable=AsyncMock) as find:
        find.return_value = [existing]
        with patch.object(svc._repo, "create_customer", new_callable=AsyncMock) as get:
            get.return_value = _customer(name="Merged Buyer")
            result = await svc.resolve_customer(
                normalized_phone="+923001234567",
                display_phone="0300",
                name="Merged Buyer",
                email=None,
            )

    assert result["id"] == str(get.return_value.id)


# ── Addresses ─────────────────────────────────────────────────────


async def test_add_address_creates_record() -> None:
    from modest_chic_backend.modules.customers.service import CustomerService

    mock_session = AsyncMock()
    svc = CustomerService(mock_session)
    addr = MagicMock(spec=CustomerAddress, id=uuid.uuid4(), customer_id=uuid.uuid4())
    addr.recipient_name = "Ayesha Khan"
    addr.phone = "+923001234567"
    addr.line1 = "123 Main St"
    addr.line2 = "Apartment 2"
    addr.area = "Gulberg"
    addr.city = "Karachi"
    addr.postal_code = "75300"
    addr.delivery_notes = "Call on arrival"
    addr.country_code = "PK"
    addr.is_default = True

    with (
        patch.object(svc._repo, "get_customer_for_update", new_callable=AsyncMock) as get_customer,
        patch.object(svc._repo, "create_address", new_callable=AsyncMock) as ca,
    ):
        get_customer.return_value = _customer()
        ca.return_value = addr
        result = await svc.add_address(
            customer_id=uuid.uuid4(),
            line1="123 Main St",
            city="Karachi",
            country_code="PK",
        )

    assert result["line1"] == "123 Main St"
    assert result["recipient_name"] == "Ayesha Khan"
    assert result["phone"] == "+923001234567"
    assert result["delivery_notes"] == "Call on arrival"
    assert result["is_default"] is True


async def test_add_address_rejects_unknown_customer() -> None:
    from modest_chic_backend.modules.customers.service import CustomerService

    svc = CustomerService(AsyncMock())
    with patch.object(svc._repo, "get_customer_for_update", new_callable=AsyncMock) as get_customer:
        get_customer.return_value = None
        with patch.object(svc._repo, "create_address", new_callable=AsyncMock) as create:
            with pytest.raises(ApplicationError) as exc:
                await svc.add_address(uuid.uuid4(), line1="Street", city="Karachi")
            assert exc.value.status_code == 404
            assert exc.value.code == "CUSTOMER_NOT_FOUND"
            create.assert_not_awaited()


async def test_list_addresses_returns_for_customer() -> None:
    from modest_chic_backend.modules.customers.service import CustomerService

    mock_session = AsyncMock()
    svc = CustomerService(mock_session)
    addr = MagicMock(spec=CustomerAddress, id=uuid.uuid4(), line1="A", city="B")

    with patch.object(svc._repo, "list_addresses", new_callable=AsyncMock) as la:
        la.return_value = [addr]
        result = await svc.list_addresses(customer_id=uuid.uuid4())

    assert len(result) == 1


# ── Consent ───────────────────────────────────────────────────────


async def test_record_consent_creates_record() -> None:
    from modest_chic_backend.modules.customers.service import CustomerService

    mock_session = AsyncMock()
    svc = CustomerService(mock_session)
    consent = MagicMock(
        spec=CustomerContactConsent,
        id=uuid.uuid4(),
        channel="email",
        purpose="marketing",
        consented=True,
        recorded_at=datetime.now(UTC),
    )

    customer_id = uuid.uuid4()
    with (
        patch.object(svc, "_lock_consent_customer", new_callable=AsyncMock),
        patch.object(svc._repo, "get_latest_consent", new_callable=AsyncMock) as latest,
        patch.object(svc._repo, "record_consent", new_callable=AsyncMock) as rc,
    ):
        latest.return_value = None
        rc.return_value = consent
        result = await svc.record_consent(
            customer_id=customer_id,
            channel="email",
            purpose="marketing",
            consented=True,
            source="checkout",
            policy_version_id=None,
        )

    assert result["channel"] == "email"
    assert result["consented"] is True


async def test_get_current_consent_returns_latest() -> None:
    from modest_chic_backend.modules.customers.service import CustomerService

    mock_session = AsyncMock()
    svc = CustomerService(mock_session)
    latest = MagicMock(
        spec=CustomerContactConsent,
        id=uuid.uuid4(),
        channel="email",
        purpose="marketing",
        consented=False,
    )

    with patch.object(svc._repo, "get_latest_consent", new_callable=AsyncMock) as gl:
        gl.return_value = latest
        result = await svc.get_current_consent(
            customer_id=uuid.uuid4(),
            channel="email",
            purpose="marketing",
        )

    assert result is not None
    assert result["consented"] is False

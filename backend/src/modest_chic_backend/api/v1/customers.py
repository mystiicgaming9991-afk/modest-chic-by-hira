"""Customer administration HTTP routes."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from modest_chic_backend.api.v1.dependencies import require_permission
from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.auth.service import StaffIdentity
from modest_chic_backend.modules.customers.service import (
    CustomerAccountStaleEditError,
    CustomerAddressStaleEditError,
    CustomerService,
)

router = APIRouter(prefix="/admin/customers", tags=["admin-customers"])


class AddAddressRequest(BaseModel):
    line1: str = Field(min_length=1, max_length=500)
    city: str = Field(min_length=1, max_length=255)
    recipient_name: str | None = None
    phone: str | None = None
    line2: str | None = None
    area: str | None = None
    postal_code: str | None = None
    delivery_notes: str | None = None
    country_code: str = "PK"
    is_default: bool = False


class UpdateAddressRequest(BaseModel):
    expected_updated_at: datetime
    line1: str = Field(min_length=1, max_length=500)
    city: str = Field(min_length=1, max_length=255)
    recipient_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    line2: str | None = Field(default=None, max_length=500)
    area: str | None = Field(default=None, max_length=255)
    postal_code: str | None = Field(default=None, max_length=20)
    delivery_notes: str | None = None
    country_code: str = Field(min_length=2, max_length=2)
    is_default: bool


class RecordConsentRequest(BaseModel):
    channel: str = Field(min_length=1, max_length=50)
    purpose: str = Field(min_length=1, max_length=100)
    consented: bool
    policy_version_id: UUID | None = None


class SetCustomerAccountStatusRequest(BaseModel):
    status: Literal["ACTIVE", "SUSPENDED"]
    expected_updated_at: datetime


@router.get("/{customer_id}/addresses")
async def list_addresses(
    customer_id: UUID,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("customer.read"))],
) -> list[dict[str, object]]:
    database = request.app.state.database
    async with database.session() as session:
        return await CustomerService(session).list_addresses(customer_id)


@router.get("/{customer_id}/consents/marketing-email")
async def current_marketing_email_consent(
    customer_id: UUID,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("customer.read"))],
) -> dict[str, object] | None:
    """Return the latest marketing email decision without enabling sends."""
    database = request.app.state.database
    async with database.session() as session:
        return await CustomerService(session).get_current_consent(
            customer_id, channel="email", purpose="marketing"
        )


@router.get("")
async def search_customers(
    request: Request,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    identity: Annotated[StaffIdentity, Depends(require_permission("customer.read"))],
) -> list[dict[str, object]]:
    database = request.app.state.database
    async with database.session() as session:
        return await CustomerService(session).search_customers(q)


@router.get("/{customer_id}/orders")
async def customer_order_history(
    customer_id: UUID,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("customer.read"))],
) -> list[dict[str, object]]:
    database = request.app.state.database
    async with database.session() as session:
        return await CustomerService(session).customer_order_history(customer_id)


@router.post("/{customer_id}/addresses", status_code=201)
async def add_address(
    customer_id: UUID,
    payload: AddAddressRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("customer.manage"))],
) -> dict[str, object]:
    database = request.app.state.database
    async with database.transaction() as session:
        return await CustomerService(session).add_address(
            customer_id=customer_id,
            line1=payload.line1,
            city=payload.city,
            recipient_name=payload.recipient_name,
            phone=payload.phone,
            line2=payload.line2,
            area=payload.area,
            postal_code=payload.postal_code,
            delivery_notes=payload.delivery_notes,
            country_code=payload.country_code,
            is_default=payload.is_default,
            actor_id=identity.user.id,
        )


@router.patch("/{customer_id}/addresses/{address_id}")
async def update_address(
    customer_id: UUID,
    address_id: UUID,
    payload: UpdateAddressRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("customer.manage"))],
) -> dict[str, object]:
    database = request.app.state.database
    async with database.transaction() as session:
        try:
            return await CustomerService(session).update_address(
                customer_id=customer_id,
                address_id=address_id,
                expected_updated_at=payload.expected_updated_at,
                actor_id=identity.user.id,
                **payload.model_dump(exclude={"expected_updated_at"}),
            )
        except CustomerAddressStaleEditError as exc:
            raise ApplicationError(
                409, "CUSTOMER_ADDRESS_CHANGED", "Saved address changed. Reload and retry."
            ) from exc


@router.post("/{customer_id}/consents", status_code=201)
async def record_consent(
    customer_id: UUID,
    payload: RecordConsentRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("customer.manage"))],
) -> dict[str, object]:
    database = request.app.state.database
    async with database.transaction() as session:
        return await CustomerService(session).record_consent(
            customer_id=customer_id,
            channel=payload.channel,
            purpose=payload.purpose,
            consented=payload.consented,
            source="staff_admin",
            policy_version_id=payload.policy_version_id,
            actor_id=identity.user.id,
        )


@router.post("/{customer_id}/account-status")
async def set_account_status(
    customer_id: UUID,
    payload: SetCustomerAccountStatusRequest,
    request: Request,
    identity: Annotated[StaffIdentity, Depends(require_permission("customer.manage"))],
) -> dict[str, object]:
    database = request.app.state.database
    async with database.transaction() as session:
        try:
            return await CustomerService(session).set_account_status(
                customer_id=customer_id,
                status=payload.status,
                actor_id=identity.user.id,
                expected_updated_at=payload.expected_updated_at,
            )
        except CustomerAccountStaleEditError as exc:
            raise ApplicationError(
                409, "CUSTOMER_ACCOUNT_CHANGED", "Customer account changed. Reload and retry."
            ) from exc

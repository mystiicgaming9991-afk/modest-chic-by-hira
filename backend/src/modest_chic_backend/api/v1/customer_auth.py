"""Email OTP customer identity and verified order history."""

from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.core.errors import (
    ApplicationError,
    RateLimitExceeded,
    RateLimitServiceUnavailable,
)
from modest_chic_backend.core.rate_limit import RateLimiter, RateLimiterUnavailable
from modest_chic_backend.modules.customers.auth_service import CustomerAuthService
from modest_chic_backend.modules.customers.service import CustomerService
from modest_chic_backend.modules.reviews.service import ReviewService

router = APIRouter(prefix="/customer-auth", tags=["customer-auth"])


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class VerifyRequest(EmailRequest):
    code: str = Field(min_length=1, max_length=20)


class ReviewSubmission(BaseModel):
    order_item_id: UUID
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=255)
    body: str | None = Field(default=None, max_length=5000)


def _service(request: Request, session: AsyncSession) -> CustomerAuthService:
    settings = request.app.state.settings
    return CustomerAuthService(
        session,
        settings.csrf_signing_key.get_secret_value(),
        settings.outbox_encryption_key.get_secret_value().encode(),
    )


async def _limit(request: Request, operation: str, email: str, limit: int) -> None:
    network = request.client.host if request.client else "unknown"
    try:
        allowed = await RateLimiter(request.app.state.redis).consume(
            operation, email, network, limit, 3600, key_prefix="customer-auth-rate-limit"
        )
    except RateLimiterUnavailable as error:
        raise RateLimitServiceUnavailable() from error
    if not allowed:
        raise RateLimitExceeded()


def _token(value: str | None) -> str:
    if not value:
        raise ApplicationError(401, "CUSTOMER_UNAUTHORIZED", "Sign in to continue.")
    return value


@router.post("/request-otp")
async def request_otp(payload: EmailRequest, request: Request) -> dict[str, str]:
    email = CustomerAuthService.clean_email(payload.email)
    await _limit(request, "request", email, 5)
    async with request.app.state.database.transaction() as session:
        await _service(request, session).request_code(email)
    return {"message": "If this address can receive mail, a sign-in code has been sent."}


@router.post("/verify-otp")
async def verify_otp(payload: VerifyRequest, request: Request) -> JSONResponse:
    email = CustomerAuthService.clean_email(payload.email)
    await _limit(request, "verify", email, 15)
    async with request.app.state.database.transaction() as session:
        result = await _service(request, session).verify_code(email, payload.code)
    if result is None:
        raise ApplicationError(401, "INVALID_CODE", "Code invalid or expired. Request a new code.")
    raw, account = result
    return JSONResponse(
        {"session_token": raw, "customer_id": str(account.customer_id), "email": account.email}
    )


@router.get("/me")
async def me(
    request: Request, x_customer_token: str | None = Header(default=None)
) -> dict[str, str]:
    async with request.app.state.database.session() as session:
        _, account = await _service(request, session).identity(_token(x_customer_token))
        return {"customer_id": str(account.customer_id), "email": account.email}


@router.post("/logout")
async def logout(
    request: Request, x_customer_token: str | None = Header(default=None)
) -> dict[str, bool]:
    async with request.app.state.database.transaction() as session:
        service = _service(request, session)
        await service.logout(await service.identity(_token(x_customer_token)))
    return {"ok": True}


@router.post("/logout-others")
async def logout_others(
    request: Request, x_customer_token: str | None = Header(default=None)
) -> dict[str, bool]:
    async with request.app.state.database.transaction() as session:
        service = _service(request, session)
        await service.logout(await service.identity(_token(x_customer_token)), others=True)
    return {"ok": True}


@router.get("/orders")
async def orders(
    request: Request, x_customer_token: str | None = Header(default=None)
) -> dict[str, object]:
    async with request.app.state.database.session() as session:
        service = _service(request, session)
        _, account = await service.identity(_token(x_customer_token))
        return {"items": await service.orders(account)}


@router.post("/orders/{order_id}/claim")
async def claim(
    order_id: UUID,
    request: Request,
    x_customer_token: str | None = Header(default=None),
    x_order_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if not x_order_token:
        raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
    async with request.app.state.database.transaction() as session:
        service = _service(request, session)
        _, account = await service.identity(_token(x_customer_token))
        await service.claim_order(account, order_id, x_order_token)
    return {"ok": True}


@router.post("/orders/{order_id}/reviews", status_code=201)
async def submit_review(
    order_id: UUID,
    payload: ReviewSubmission,
    request: Request,
    x_order_token: str | None = Header(default=None),
) -> dict[str, object]:
    if not x_order_token:
        raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
    key = request.app.state.settings.outbox_encryption_key.get_secret_value().encode()
    async with request.app.state.database.transaction() as session:
        return await ReviewService(session, key).submit_for_order_item(
            order_id=order_id,
            order_item_id=payload.order_item_id,
            access_token=x_order_token,
            rating=payload.rating,
            title=payload.title,
            body=payload.body,
        )


@router.get("/consents/marketing-email")
async def marketing_email_consent(
    request: Request, x_customer_token: str | None = Header(default=None)
) -> dict[str, object]:
    async with request.app.state.database.session() as session:
        _, account = await _service(request, session).identity(_token(x_customer_token))
        consent = await CustomerService(session).get_current_consent(
            account.customer_id, "email", "marketing"
        )
    return {
        "consented": bool(consent and consent["consented"]),
        "recorded_at": consent["recorded_at"] if consent else None,
    }


@router.post("/consents/marketing-email")
async def withdraw_marketing_email_consent(
    request: Request, x_customer_token: str | None = Header(default=None)
) -> dict[str, object]:
    async with request.app.state.database.transaction() as session:
        _, account = await _service(request, session).identity(_token(x_customer_token))
        current = await CustomerService(session).withdraw_marketing_email_consent(
            account.customer_id
        )
    return {
        "consented": False,
        "recorded_at": current["recorded_at"] if current else None,
    }

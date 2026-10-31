"""Customer email proof, revocable sessions, and explicit guest order claiming."""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.auth.security import (
    create_opaque_token,
    hash_token,
    normalize_email,
)
from modest_chic_backend.modules.checkout.repository import CheckoutRepository
from modest_chic_backend.modules.customers.models import (
    Customer,
    CustomerAccount,
    CustomerOtpChallenge,
    CustomerSession,
)
from modest_chic_backend.modules.orders.customer_view import customer_order_timeline
from modest_chic_backend.modules.orders.models import Order, OrderEvent
from modest_chic_backend.modules.outbox.service import OutboxService

CHALLENGE_LIFETIME = timedelta(minutes=10)
SESSION_LIFETIME = timedelta(days=30)
MAX_ATTEMPTS = 5


class CustomerAuthService:
    def __init__(self, session: AsyncSession, signing_key: str, encryption_key: bytes) -> None:
        self.session = session
        self.signing_key = signing_key.encode()
        self.encryption_key = encryption_key

    @staticmethod
    def clean_email(value: str) -> str:
        email = normalize_email(value)
        if (
            len(email) > 255
            or "@" not in email
            or email.startswith("@")
            or "." not in email.rsplit("@", 1)[-1]
        ):
            raise ApplicationError(422, "INVALID_EMAIL", "Enter a valid email address.")
        return email

    def _code_hash(self, challenge_id: uuid.UUID, email: str, code: str) -> str:
        return hmac.new(
            self.signing_key, f"{challenge_id}:{email}:{code}".encode(), hashlib.sha256
        ).hexdigest()

    async def _email_lock(self, email: str) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": "customer-otp:" + email},
        )

    async def request_code(self, email: str) -> None:
        now = datetime.now(UTC)
        await self._email_lock(email)
        await self.session.execute(
            update(CustomerOtpChallenge)
            .where(
                CustomerOtpChallenge.email == email,
                CustomerOtpChallenge.superseded_at.is_(None),
            )
            .values(superseded_at=now)
        )
        challenge_id = uuid.uuid4()
        code = f"{secrets.randbelow(1_000_000):06d}"
        self.session.add(
            CustomerOtpChallenge(
                id=challenge_id,
                email=email,
                token_hash=self._code_hash(challenge_id, email, code),
                expires_at=now + CHALLENGE_LIFETIME,
            )
        )
        await self.session.flush()
        await OutboxService(self.session, self.encryption_key).enqueue_email(
            aggregate_type="customer_otp",
            aggregate_id=challenge_id,
            recipient=email,
            subject="Your Modest Chic sign-in code",
            html_body=(
                f"<p>Your sign-in code is <strong>{code}</strong>.</p>"
                "<p>It expires in 10 minutes.</p>"
            ),
        )

    async def verify_code(self, email: str, code: str) -> tuple[str, CustomerAccount] | None:
        now = datetime.now(UTC)
        await self._email_lock(email)
        result = await self.session.execute(
            select(CustomerOtpChallenge)
            .where(
                CustomerOtpChallenge.email == email,
                CustomerOtpChallenge.superseded_at.is_(None),
            )
            .order_by(CustomerOtpChallenge.created_at.desc(), CustomerOtpChallenge.id.desc())
            .limit(1)
            .with_for_update()
        )
        challenge = result.scalar_one_or_none()
        if (
            challenge is None
            or challenge.consumed_at
            or challenge.superseded_at
            or challenge.expires_at <= now
            or challenge.failed_attempts >= MAX_ATTEMPTS
        ):
            return None
        valid_format = len(code) == 6 and code.isascii() and code.isdigit()
        valid_code = valid_format and hmac.compare_digest(
            challenge.token_hash, self._code_hash(challenge.id, email, code)
        )
        if not valid_code:
            challenge.failed_attempts += 1
            return None
        challenge.consumed_at = now
        account_result = await self.session.execute(
            select(CustomerAccount).where(CustomerAccount.email == email).with_for_update()
        )
        account = account_result.scalar_one_or_none()
        if account is None:
            customer = Customer(email=email)
            self.session.add(customer)
            await self.session.flush()
            account = CustomerAccount(email=email, customer_id=customer.id)
            self.session.add(account)
            await self.session.flush()
        if account.status != "ACTIVE":
            return None
        raw = create_opaque_token()
        self.session.add(
            CustomerSession(
                customer_id=account.customer_id,
                token_hash=hash_token(raw),
                family_id=uuid.uuid4(),
                expires_at=now + SESSION_LIFETIME,
            )
        )
        await self.session.flush()
        return raw, account

    async def identity(self, raw_token: str) -> tuple[CustomerSession, CustomerAccount]:
        result = await self.session.execute(
            select(CustomerSession, CustomerAccount)
            .join(CustomerAccount, CustomerAccount.customer_id == CustomerSession.customer_id)
            .where(
                CustomerSession.token_hash == hash_token(raw_token),
                CustomerSession.revoked_at.is_(None),
                CustomerSession.expires_at > datetime.now(UTC),
                CustomerAccount.status == "ACTIVE",
            )
        )
        identity = result.one_or_none()
        if identity is None:
            raise ApplicationError(401, "CUSTOMER_UNAUTHORIZED", "Sign in to continue.")
        return identity

    async def logout(
        self, identity: tuple[CustomerSession, CustomerAccount], others: bool = False
    ) -> None:
        current, account = identity
        query = update(CustomerSession).where(
            CustomerSession.customer_id == account.customer_id, CustomerSession.revoked_at.is_(None)
        )
        if others:
            query = query.where(CustomerSession.id != current.id)
        else:
            query = query.where(CustomerSession.id == current.id)
        await self.session.execute(query.values(revoked_at=datetime.now(UTC)))

    async def orders(self, account: CustomerAccount) -> list[dict[str, object]]:
        result = await self.session.execute(
            select(Order)
            .where(Order.customer_id == account.customer_id)
            .order_by(Order.created_at.desc())
            .limit(100)
        )
        orders = result.scalars().all()
        events_by_order: dict[uuid.UUID, list[OrderEvent]] = {}
        if orders:
            events = await self.session.scalars(
                select(OrderEvent)
                .where(OrderEvent.order_id.in_([order.id for order in orders]))
                .order_by(OrderEvent.order_id, OrderEvent.effective_at, OrderEvent.id)
            )
            for event in events.all():
                events_by_order.setdefault(event.order_id, []).append(event)
        return [
            {
                "order_id": str(order.id),
                "order_number": order.number,
                "state": order.state.value,
                "total_minor": order.total_minor,
                "created_at": order.created_at.isoformat(),
                "events": customer_order_timeline(events_by_order.get(order.id, [])),
            }
            for order in orders
        ]

    async def claim_order(
        self, account: CustomerAccount, order_id: uuid.UUID, credential: str
    ) -> None:
        proof = await CheckoutRepository(self.session, self.encryption_key).find_order_access(
            credential
        )
        if proof is None or proof.order_id != order_id or not proof.allows("order.read"):
            raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
        order = await self.session.get(Order, order_id, with_for_update=True)
        if order is None or (
            order.customer_id is not None and order.customer_id != account.customer_id
        ):
            raise ApplicationError(404, "ORDER_NOT_FOUND", "Order not found.")
        if order.customer_id is None:
            order.customer_id = account.customer_id
            self.session.add(
                OrderEvent(
                    order_id=order.id,
                    event_type="order.claimed",
                    actor_type="customer",
                    event_metadata={
                        "customer_id": str(account.customer_id),
                        "proof": "order_access_token",
                    },
                )
            )

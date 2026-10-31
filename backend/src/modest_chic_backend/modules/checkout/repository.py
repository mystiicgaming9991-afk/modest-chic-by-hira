"""Checkout repository — order access tokens."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.checkout.models import OrderAccessToken
from modest_chic_backend.modules.settings.crypto import decrypt_setting_value, encrypt_setting_value


class CheckoutRepository:
    def __init__(self, session: AsyncSession, encryption_key: bytes) -> None:
        self._session = session
        self._encryption_key = encryption_key

    async def create_access_token(self, order_id: uuid.UUID) -> tuple[str, OrderAccessToken]:
        raw = "mc_ord_" + secrets.token_hex(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        replay = encrypt_setting_value(self._encryption_key, raw)

        token = OrderAccessToken(
            order_id=order_id,
            token_hash=token_hash,
            replay_ciphertext=json.dumps(replay).encode(),
            replay_key_version=1,
            expires_at=datetime.now(UTC) + timedelta(days=90),
        )
        self._session.add(token)
        await self._session.flush()
        return raw, token

    async def replay_access_token(self, order_id: uuid.UUID) -> str | None:
        result = await self._session.execute(
            select(OrderAccessToken).where(
                OrderAccessToken.order_id == order_id,
                OrderAccessToken.revoked_at.is_(None),
                OrderAccessToken.expires_at > datetime.now(UTC),
            )
        )
        token = result.scalar_one_or_none()
        if token is None:
            return None
        return str(decrypt_setting_value(self._encryption_key, json.loads(token.replay_ciphertext)))

    async def find_order_access(self, raw_token: str) -> OrderAccessToken | None:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        result = await self._session.execute(
            select(OrderAccessToken).where(
                OrderAccessToken.token_hash == token_hash,
                OrderAccessToken.revoked_at.is_(None),
                OrderAccessToken.expires_at > datetime.now(UTC),
            )
        )
        return result.scalar_one_or_none()

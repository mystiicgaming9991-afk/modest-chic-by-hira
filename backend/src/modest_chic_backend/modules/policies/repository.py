"""Policy version database access — immutable append-only records."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.policies.models import PolicyVersion


class PoliciesRepository:
    """Insert and query immutable policy versions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_type(self, type: str) -> list[PolicyVersion]:
        """Return all policy versions for the given type, ordered by version."""
        result = await self._session.execute(
            select(PolicyVersion).where(PolicyVersion.type == type).order_by(PolicyVersion.version)
        )
        return list(result.scalars().all())

    async def get_all(self) -> list[PolicyVersion]:
        """Return all policy versions across all types."""
        result = await self._session.execute(
            select(PolicyVersion).order_by(PolicyVersion.type, PolicyVersion.version)
        )
        return list(result.scalars().all())

    async def get_effective(self, type: str) -> PolicyVersion | None:
        """Return the currently effective version for the given type.

        The effective version is the one with the highest version number
        whose effective_from is at or before the current UTC time.
        """
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(PolicyVersion)
            .where(
                PolicyVersion.type == type,
                PolicyVersion.effective_from <= now,
            )
            .order_by(PolicyVersion.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def insert(
        self,
        type: str,
        effective_from: datetime,
        content: dict[str, Any],
        approved_by: uuid.UUID | None,
    ) -> PolicyVersion:
        """Insert a new immutable policy version with auto-incremented version.

        The version number is determined by (max existing version for this type) + 1.
        """
        # Determine the next version number
        result = await self._session.execute(
            select(func.coalesce(func.max(PolicyVersion.version), 0)).where(
                PolicyVersion.type == type
            )
        )
        max_version: int = result.scalar_one()
        next_version = max_version + 1

        policy = PolicyVersion(
            type=type,
            version=next_version,
            effective_from=effective_from,
            content=content,
            approved_by=approved_by,
        )
        self._session.add(policy)
        await self._session.flush()
        return policy

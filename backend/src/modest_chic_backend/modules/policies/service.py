"""Policy version business logic — immutable publication with audit trail."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.audit.repository import AuditRepository
from modest_chic_backend.modules.policies.repository import PoliciesRepository
from modest_chic_backend.modules.policies.schemas import (
    PolicyVersionListResponse,
    PolicyVersionRead,
    validate_policy_type,
)


class PoliciesService:
    """Application service for publishing and querying immutable policy versions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = PoliciesRepository(session)
        self._audit = AuditRepository(session)

    async def publish_version(
        self,
        type: str,
        effective_from: datetime,
        content: dict[str, Any],
        approved_by: uuid.UUID,
    ) -> PolicyVersionRead:
        """Insert a new immutable policy version with auto-incremented version number.

        Args:
            type: The policy type (must be in VALID_POLICY_TYPES).
            effective_from: When this version becomes governing (UTC).
            content: The immutable policy text (JSON-serializable).
            approved_by: The staff member publishing this version.

        Returns:
            The newly created PolicyVersion.

        Raises:
            ValueError: If the type is not recognized.
        """
        validate_policy_type(type)

        policy = await self._repo.insert(
            type=type,
            effective_from=effective_from,
            content=content,
            approved_by=approved_by,
        )
        await self._audit.record(
            action="policy.published",
            entity_type="policy_version",
            actor_id=approved_by,
            entity_id=policy.id,
            metadata={"type": type, "version": policy.version},
        )
        return PolicyVersionRead(
            id=policy.id,
            type=policy.type,
            version=policy.version,
            effective_from=policy.effective_from,
            content=policy.content,
            approved_by=policy.approved_by,
            created_at=policy.created_at,
        )

    async def list_versions(self, type: str | None = None) -> PolicyVersionListResponse:
        """Return all policy versions, optionally filtered by type.

        Args:
            type: Optional filter by policy type.

        Returns:
            A list response with PolicyVersionRead items.
        """
        if type:
            validate_policy_type(type)
            rows = await self._repo.get_by_type(type)
        else:
            rows = await self._repo.get_all()

        items = [
            PolicyVersionRead(
                id=row.id,
                type=row.type,
                version=row.version,
                effective_from=row.effective_from,
                content=row.content,
                approved_by=row.approved_by,
                created_at=row.created_at,
            )
            for row in rows
        ]
        return PolicyVersionListResponse(items=items)

    async def get_effective(self, type: str) -> PolicyVersionRead | None:
        """Return the currently effective version for the given type.

        Args:
            type: The policy type.

        Returns:
            The effective PolicyVersionRead, or None if no version exists.

        Raises:
            ValueError: If the type is not recognized.
        """
        validate_policy_type(type)
        row = await self._repo.get_effective(type)
        if row is None:
            return None
        return PolicyVersionRead(
            id=row.id,
            type=row.type,
            version=row.version,
            effective_from=row.effective_from,
            content=row.content,
            approved_by=row.approved_by,
            created_at=row.created_at,
        )

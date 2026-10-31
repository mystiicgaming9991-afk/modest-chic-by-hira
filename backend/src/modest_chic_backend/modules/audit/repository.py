"""Transactional security audit event persistence."""

import re
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.modules.audit.models import AuditLog

_METADATA_KEYS_BY_ACTION: dict[str, frozenset[str]] = {
    "catalog.category_updated": frozenset({"fields"}),
    "catalog.collection_products_set": frozenset(),
    "catalog.collection_updated": frozenset({"fields"}),
    "catalog.media_attached": frozenset(
        {
            "product_id",
            "variant_id",
            "media_type",
            "sort_order",
            "is_primary",
            "replaced_primary_ids",
        }
    ),
    "catalog.product_archived": frozenset(),
    "catalog.product_categories_set": frozenset({"category_ids"}),
    "catalog.product_created": frozenset({"slug"}),
    "catalog.product_tags_set": frozenset({"tag_ids"}),
    "catalog.product_updated": frozenset({"fields"}),
    "catalog.variant_created": frozenset(),
    "catalog.variant_updated": frozenset({"fields"}),
    "customer.account_activated": frozenset({"previous_status", "new_status"}),
    "customer.account_suspended": frozenset({"previous_status", "new_status"}),
    "inventory.low_stock_threshold.updated": frozenset(
        {"variant_id", "location_id", "previous_threshold", "low_stock_threshold"}
    ),
    "policy.published": frozenset({"type", "version"}),
    "review.approved": frozenset({"status"}),
    "review.rejected": frozenset({"status"}),
    "settings.secret_read": frozenset({"key"}),
    "settings.secret_updated": frozenset({"key", "version"}),
    "settings.updated": frozenset({"key", "version"}),
    "staff.activated": frozenset({"previous_status"}),
    "staff.bootstrap.owner_created": frozenset(),
    "staff.invitation.accepted": frozenset(),
    "staff.invitation.created": frozenset({"role_count"}),
    "staff.login.failed": frozenset({"outcome"}),
    "staff.login.succeeded": frozenset({"totp_enabled"}),
    "staff.password_change.failed": frozenset({"outcome"}),
    "staff.password_changed": frozenset(),
    "staff.password_reset.completed": frozenset(),
    "staff.password_reset.requested": frozenset({"outcome"}),
    "staff.roles_changed": frozenset({"previous", "new"}),
    "staff.session.logged_out": frozenset(),
    "staff.session.refreshed": frozenset(),
    "staff.session.refresh_reuse": frozenset({"outcome"}),
    "staff.suspended": frozenset({"previous_status"}),
    "staff.totp.enrollment_completed": frozenset(),
    "staff.totp.enrollment_failed": frozenset({"outcome"}),
    "staff.totp.enrollment_started": frozenset(),
}
_MAX_METADATA_STRING_LENGTH = 256
_MAX_METADATA_LIST_LENGTH = 100
_SAFE_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,63}$")
_SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SAFE_MEDIA_TYPE = re.compile(r"^[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+$")
_OUTCOMES = frozenset({"accepted", "denied", "family_revoked"})
_ACCOUNT_STATUSES = frozenset({"ACTIVE", "SUSPENDED"})
_REVIEW_STATUSES = frozenset({"APPROVED", "REJECTED"})


class AuditRepository:
    """Append allow-listed audit metadata within the owning operation transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        action: str,
        entity_type: str,
        actor_id: uuid.UUID | None,
        entity_id: uuid.UUID | None = None,
        correlation_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist a security event while excluding credential and PII fields."""
        allowed_keys = _METADATA_KEYS_BY_ACTION.get(action, frozenset())
        safe_metadata = {
            key: value
            for key, value in (metadata or {}).items()
            if key in allowed_keys and _is_safe_metadata_value(key, value)
        }
        self._session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                correlation_id=correlation_id,
                event_metadata=safe_metadata or None,
            )
        )
        await self._session.flush()


def _is_safe_metadata_value(key: str, value: Any) -> bool:
    """Validate metadata values against the safe representation for each field."""
    if key == "outcome":
        return isinstance(value, str) and value in _OUTCOMES
    if key in {"totp_enabled", "is_primary"}:
        return type(value) is bool
    if key in {"role_count", "sort_order"}:
        return type(value) is int and value >= 0
    if key == "version":
        return type(value) is int and value > 0
    if key in {"previous_threshold", "low_stock_threshold"}:
        return value is None or (type(value) is int and value >= 0)
    if key in {"previous_status", "new_status"}:
        return isinstance(value, str) and value in _ACCOUNT_STATUSES
    if key == "status":
        return isinstance(value, str) and value in _REVIEW_STATUSES
    if key == "variant_id":
        return value is None or _is_uuid(value)
    if key in {"product_id", "location_id"}:
        return _is_uuid(value)
    if key in {"category_ids", "tag_ids", "replaced_primary_ids"}:
        return _is_bounded_list(value, _is_uuid)
    if key in {"previous", "new", "fields"}:
        return _is_bounded_list(value, _is_safe_code)
    if key == "slug":
        return (
            isinstance(value, str)
            and len(value) <= _MAX_METADATA_STRING_LENGTH
            and bool(_SAFE_SLUG.fullmatch(value))
        )
    if key == "media_type":
        return (
            isinstance(value, str) and len(value) <= 50 and bool(_SAFE_MEDIA_TYPE.fullmatch(value))
        )
    if key in {"key", "type"}:
        return _is_safe_code(value)
    return False


def _is_safe_code(value: Any) -> bool:
    """Accept only short identifier-like values used for audit codes and field names."""
    return isinstance(value, str) and bool(_SAFE_CODE.fullmatch(value))


def _is_uuid(value: Any) -> bool:
    """Accept canonical UUID strings only for entity references in metadata."""
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value.lower()
    except ValueError:
        return False


def _is_bounded_list(value: Any, item_is_safe: Callable[[Any], bool]) -> bool:
    """Accept a bounded list when every item satisfies its field-specific validator."""
    return (
        isinstance(value, list)
        and len(value) <= _MAX_METADATA_LIST_LENGTH
        and all(item_is_safe(item) for item in value)
    )

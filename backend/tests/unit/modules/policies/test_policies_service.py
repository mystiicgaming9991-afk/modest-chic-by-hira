"""Unit tests for policies service business logic."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from modest_chic_backend.modules.policies.models import PolicyVersion
from modest_chic_backend.modules.policies.schemas import validate_policy_type
from modest_chic_backend.modules.policies.service import PoliciesService

# ── Policy Type Validation ────────────────────────────────────────


def test_valid_policy_types_are_accepted() -> None:
    for t in ("checkout_bundle", "returns", "shipping", "privacy", "terms", "cod_confirmation"):
        validate_policy_type(t)  # should not raise


def test_invalid_policy_type_raises() -> None:
    with pytest.raises(ValueError, match="unknown policy type"):
        validate_policy_type("invalid_type")


# ── publish_version ───────────────────────────────────────────────


async def test_publish_version_inserts_and_audits() -> None:
    """publish_version calls repository insert and records audit."""
    mock_session = AsyncMock()
    service = PoliciesService(mock_session)

    now = datetime.now(UTC)
    policy = PolicyVersion(
        type="returns",
        version=1,
        effective_from=now,
        content={"window_days": 7},
        approved_by=None,
    )
    policy.id = uuid.uuid4()
    policy.created_at = now

    with patch.object(service._repo, "insert", new_callable=AsyncMock) as mock_insert:
        mock_insert.return_value = policy
        with patch.object(service._audit, "record", new_callable=AsyncMock) as mock_audit:
            result = await service.publish_version(
                type="returns",
                effective_from=now,
                content={"window_days": 7},
                approved_by=uuid.uuid4(),
            )

    mock_insert.assert_awaited_once()
    mock_audit.assert_awaited_once()
    assert result.type == "returns"
    assert result.version == 1
    assert result.content == {"window_days": 7}


async def test_publish_version_rejects_invalid_type() -> None:
    """Publishing with an unknown type raises ValueError."""
    mock_session = AsyncMock()
    service = PoliciesService(mock_session)

    with pytest.raises(ValueError, match="unknown policy type"):
        await service.publish_version(
            type="bogus_policy",
            effective_from=datetime.now(UTC),
            content={},
            approved_by=uuid.uuid4(),
        )


# ── list_versions ─────────────────────────────────────────────────


async def test_list_versions_filters_by_type() -> None:
    """list_versions with a type filter delegates to get_by_type."""
    mock_session = AsyncMock()
    service = PoliciesService(mock_session)

    now = datetime.now(UTC)
    row = PolicyVersion(
        type="terms",
        version=1,
        effective_from=now,
        content={"title": "Terms"},
    )
    row.id = uuid.uuid4()
    row.created_at = now

    with patch.object(service._repo, "get_by_type", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [row]
        result = await service.list_versions(type="terms")

    assert len(result.items) == 1
    assert result.items[0].type == "terms"
    assert result.items[0].version == 1


async def test_list_versions_returns_all_when_no_filter() -> None:
    """list_versions without filter returns all versions."""
    mock_session = AsyncMock()
    service = PoliciesService(mock_session)

    now = datetime.now(UTC)
    row1 = PolicyVersion(type="terms", version=1, effective_from=now, content={"t": 1})
    row1.id = uuid.uuid4()
    row1.created_at = now
    row2 = PolicyVersion(type="returns", version=1, effective_from=now, content={"r": 1})
    row2.id = uuid.uuid4()
    row2.created_at = now

    with patch.object(service._repo, "get_all", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [row1, row2]
        result = await service.list_versions()

    assert len(result.items) == 2


async def test_list_versions_rejects_invalid_filter() -> None:
    """list_versions with an invalid type filter raises ValueError."""
    mock_session = AsyncMock()
    service = PoliciesService(mock_session)

    with pytest.raises(ValueError, match="unknown policy type"):
        await service.list_versions(type="nope")


# ── get_effective ─────────────────────────────────────────────────


async def test_get_effective_returns_policy() -> None:
    """get_effective returns the currently effective version."""
    mock_session = AsyncMock()
    service = PoliciesService(mock_session)

    now = datetime.now(UTC)
    row = PolicyVersion(
        type="shipping",
        version=2,
        effective_from=now - timedelta(days=1),
        content={"free_over": 5000},
    )
    row.id = uuid.uuid4()
    row.created_at = now

    with patch.object(service._repo, "get_effective", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = row
        result = await service.get_effective(type="shipping")

    assert result is not None
    assert result.version == 2
    assert result.content == {"free_over": 5000}


async def test_get_effective_returns_none_when_no_version() -> None:
    """get_effective returns None when no versions exist."""
    mock_session = AsyncMock()
    service = PoliciesService(mock_session)

    with patch.object(service._repo, "get_effective", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        result = await service.get_effective(type="returns")

    assert result is None


async def test_get_effective_rejects_invalid_type() -> None:
    """get_effective with an invalid type raises ValueError."""
    mock_session = AsyncMock()
    service = PoliciesService(mock_session)

    with pytest.raises(ValueError, match="unknown policy type"):
        await service.get_effective(type="invalid")

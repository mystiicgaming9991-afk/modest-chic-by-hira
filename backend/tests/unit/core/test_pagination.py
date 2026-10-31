"""Unit tests for cursor-based pagination."""

import uuid

import pytest

from modest_chic_backend.core.pagination import CursorPaginator, PaginationParams


def test_encode_decode_round_trip() -> None:
    """A UUID survives encoding to cursor and decoding back."""
    original = uuid.uuid4()
    cursor = CursorPaginator.encode(original)
    decoded = CursorPaginator.decode(cursor)
    assert decoded == original


def test_encode_produces_url_safe_string() -> None:
    """Cursors are URL-safe base64 with no padding."""
    cursor = CursorPaginator.encode(uuid.uuid4())
    assert "+" not in cursor
    assert "/" not in cursor
    assert "=" not in cursor


def test_decode_invalid_cursor_raises() -> None:
    """A malformed cursor string raises ValueError."""
    with pytest.raises(ValueError, match="invalid cursor"):
        CursorPaginator.decode("not-a-uuid!")


def test_decode_empty_string_raises() -> None:
    """An empty string raises ValueError."""
    with pytest.raises(ValueError, match="invalid cursor"):
        CursorPaginator.decode("")


def test_paginate_returns_items_and_cursor_when_more_pages() -> None:
    """When items exceed limit, return a page and a next cursor."""
    items = [type("Item", (), {"id": uuid.uuid4()})() for _ in range(25)]
    page, next_cursor = CursorPaginator.paginate(items, limit=20)
    assert len(page) == 20
    assert next_cursor is not None
    assert CursorPaginator.decode(next_cursor) == items[19].id


def test_paginate_returns_all_items_with_no_cursor_when_fits() -> None:
    """When items fit within the limit, return all with no cursor."""
    items = [type("Item", (), {"id": uuid.uuid4()})() for _ in range(10)]
    page, next_cursor = CursorPaginator.paginate(items, limit=20)
    assert len(page) == 10
    assert next_cursor is None


def test_paginate_handles_empty_list() -> None:
    """An empty list returns empty page and None cursor."""
    page, next_cursor = CursorPaginator.paginate([], limit=20)
    assert page == []
    assert next_cursor is None


def test_pagination_params_defaults() -> None:
    """Default params have after=None and limit=20."""
    params = PaginationParams()
    assert params.after is None
    assert params.limit == 20


def test_pagination_params_validates_limit() -> None:
    """Limit must be between 1 and 100."""
    assert PaginationParams(limit=1).limit == 1
    assert PaginationParams(limit=100).limit == 100


def test_pagination_params_rejects_limit_too_low() -> None:
    with pytest.raises(ValueError):
        PaginationParams(limit=0)


def test_pagination_params_rejects_limit_too_high() -> None:
    with pytest.raises(ValueError):
        PaginationParams(limit=101)

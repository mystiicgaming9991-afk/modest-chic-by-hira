"""Cursor-based pagination utilities for list endpoints."""

from __future__ import annotations

import base64
import uuid
from typing import Any, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class CursorPaginator:
    """Encode and decode UUID-based cursors for stable pagination.

    Cursors are base64-encoded UUID strings. The client passes `after=<cursor>`
    and `limit=<N>`; the response includes `next_cursor` (or null on the last page).
    """

    @staticmethod
    def encode(uuid_value: uuid.UUID) -> str:
        """Encode a UUID into an opaque cursor string."""
        return base64.urlsafe_b64encode(uuid_value.bytes).rstrip(b"=").decode("ascii")

    @staticmethod
    def decode(cursor: str) -> uuid.UUID:
        """Decode a cursor string back into a UUID.

        Raises:
            ValueError: If the cursor is not a valid encoded UUID.
        """
        try:
            # Add padding back
            padded = cursor + "=" * (-len(cursor) % 4)
            return uuid.UUID(bytes=base64.urlsafe_b64decode(padded))
        except Exception as exc:
            raise ValueError(f"invalid cursor: {cursor}") from exc

    @staticmethod
    def paginate(
        items: list[Any],
        id_attr: str = "id",
        limit: int = 20,
    ) -> tuple[list[Any], str | None]:
        """Slice items and produce a next cursor.

        Args:
            items: The full list (at most limit + 1 items to detect more pages).
            id_attr: The attribute name containing the UUID cursor field.
            limit: The page size.

        Returns:
            A tuple of (page_items, next_cursor_or_none).
        """
        if len(items) > limit:
            page_items = items[:limit]
            last = page_items[-1]
            next_id = getattr(last, id_attr)
            next_cursor = CursorPaginator.encode(next_id)
            return page_items, next_cursor
        return items, None


class PaginationParams(BaseModel):
    """Query parameters for cursor-based pagination."""

    after: str | None = Field(default=None, description="Cursor from previous response")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum items per page")

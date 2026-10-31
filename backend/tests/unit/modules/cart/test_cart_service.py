"""Unit tests for guest cart service.

TDD RED: service.py doesn't exist yet.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from modest_chic_backend.modules.cart.models import Cart, CartItem


def _cart(**kw: object) -> MagicMock:
    c = MagicMock(spec=Cart)
    c.id = uuid.uuid4()
    c.guest_token_hash = "abc123"
    c.currency = "PKR"
    c.version = 1
    c.expires_at = datetime.now(UTC) + timedelta(days=7)
    c.items = []
    for k, v in kw.items():
        if v is not None:
            setattr(c, k, v)
    return c


def _item(*, variant_id: uuid.UUID | None = None, quantity: int = 1) -> MagicMock:
    i = MagicMock(spec=CartItem)
    i.id = uuid.uuid4()
    i.variant_id = variant_id or uuid.uuid4()
    i.quantity = quantity
    return i


async def test_get_or_create_cart_creates_new() -> None:
    from modest_chic_backend.modules.cart.service import CartService

    mock_session = AsyncMock()
    svc = CartService(mock_session)
    new_cart = _cart()

    with patch.object(svc._repo, "find_by_token_hash", new_callable=AsyncMock) as find:
        find.return_value = None
        with patch.object(svc._repo, "create_cart", new_callable=AsyncMock) as create:
            create.return_value = new_cart
            result = await svc.get_or_create_cart(guest_token_hash="hash123")

    assert result["id"] == str(new_cart.id)
    assert result["version"] == 1


async def test_get_or_create_returns_existing() -> None:
    from modest_chic_backend.modules.cart.service import CartService

    mock_session = AsyncMock()
    svc = CartService(mock_session)
    existing = _cart(version=5, items=[_item()])

    with patch.object(svc._repo, "find_by_token_hash", new_callable=AsyncMock) as find:
        find.return_value = existing
        result = await svc.get_or_create_cart(guest_token_hash="hash123")

    assert result["version"] == 5
    assert len(result["items"]) == 1


async def test_add_item_to_cart() -> None:
    from modest_chic_backend.modules.cart.service import CartService

    mock_session = AsyncMock()
    svc = CartService(mock_session)
    variant_id = uuid.uuid4()
    cart_empty = _cart(items=[], version=1)
    cart_with_item = _cart(items=[_item(variant_id=variant_id, quantity=2)], version=2)

    with patch.object(svc._repo, "get_cart_with_items", new_callable=AsyncMock) as get:
        get.side_effect = [cart_empty, cart_with_item]
        with patch.object(svc._repo, "add_or_update_item", new_callable=AsyncMock) as add:
            new_item = _item(variant_id=variant_id, quantity=2)
            add.return_value = new_item
            result = await svc.add_item(cart_id=cart_empty.id, variant_id=variant_id, quantity=2)

    assert len(result["items"]) >= 1
    assert result["version"] == 2  # incremented


async def test_update_item_quantity() -> None:
    from modest_chic_backend.modules.cart.service import CartService

    mock_session = AsyncMock()
    svc = CartService(mock_session)
    variant_id = uuid.uuid4()
    cart = _cart(items=[_item(variant_id=variant_id, quantity=1)])

    with patch.object(svc._repo, "get_cart_with_items", new_callable=AsyncMock) as get:
        get.return_value = cart
        with patch.object(svc._repo, "add_or_update_item", new_callable=AsyncMock) as add:
            updated = _item(variant_id=variant_id, quantity=3)
            add.return_value = updated
            result = await svc.add_item(cart_id=cart.id, variant_id=variant_id, quantity=3)

    assert result["version"] == 2


async def test_remove_item_from_cart() -> None:
    from modest_chic_backend.modules.cart.service import CartService

    mock_session = AsyncMock()
    svc = CartService(mock_session)
    item_id = uuid.uuid4()
    cart = _cart(items=[_item()])
    cart.items[0].id = item_id

    with patch.object(svc._repo, "get_cart_with_items", new_callable=AsyncMock) as get:
        get.return_value = cart
        with patch.object(svc._repo, "remove_item", new_callable=AsyncMock) as remove:
            result = await svc.remove_item(cart_id=cart.id, item_id=item_id)

    remove.assert_awaited_once_with(cart.id, item_id)
    assert result["version"] == 2


async def test_get_cart_returns_none_for_expired() -> None:
    from modest_chic_backend.modules.cart.service import CartService

    mock_session = AsyncMock()
    svc = CartService(mock_session)
    expired = _cart(expires_at=datetime.now(UTC) - timedelta(days=1))

    with patch.object(svc._repo, "find_by_token_hash", new_callable=AsyncMock) as find:
        find.return_value = expired
        result = await svc.get_or_create_cart(guest_token_hash="old")

    # Reuse the row because guest_token_hash has a unique constraint.
    assert result["id"] == str(expired.id)
    assert result["items"] == []
    assert expired.expires_at > datetime.now(UTC)

"""Unit tests for inventory service — stock management and reservations.

TDD: RED (import failed) → GREEN (service implemented).
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modest_chic_backend.modules.inventory.enums import MovementReason, ReservationStatus
from modest_chic_backend.modules.inventory.models import (
    InventoryBalance,
    InventoryLocation,
    InventoryMovement,
    InventoryReservation,
)


def _balance(**kw: object) -> MagicMock:
    defaults: dict = {
        "id": uuid.uuid4(),
        "variant_id": uuid.uuid4(),
        "location_id": uuid.uuid4(),
        "on_hand": 10,
        "reserved": 0,
        "low_stock_threshold": None,
        "version": 1,
    }
    defaults.update({k: v for k, v in kw.items() if v is not None})
    return MagicMock(spec=InventoryBalance, **defaults)


def _location() -> MagicMock:
    return MagicMock(spec=InventoryLocation, id=uuid.uuid4(), key="main")


# ── US1: Receive ─────────────────────────────────────────────────


async def test_receive_stock_increments_on_hand() -> None:
    from modest_chic_backend.modules.inventory.service import InventoryService

    mock_session = AsyncMock()
    svc = InventoryService(mock_session)
    balance = _balance(on_hand=5)
    location = _location()

    with patch.object(svc._repo, "get_location_by_key", new_callable=AsyncMock) as gl:
        gl.return_value = location
        with patch.object(svc._repo, "get_variant_with_product", new_callable=AsyncMock) as gv:
            gv.return_value = (MagicMock(), MagicMock())
            with patch.object(svc._repo, "get_or_create_balance", new_callable=AsyncMock) as gb:
                gb.return_value = balance
                with patch.object(svc._repo, "record_movement", new_callable=AsyncMock):
                    result = await svc.receive_stock(
                        variant_id=balance.variant_id,
                        location_key="main",
                        quantity=3,
                        actor_id=uuid.uuid4(),
                        idempotency_key=None,
                    )

    assert balance.on_hand == 8
    assert result["on_hand"] == 8
    assert result["available"] == 8


async def test_receive_stock_is_idempotent() -> None:
    from modest_chic_backend.modules.inventory.service import InventoryService

    mock_session = AsyncMock()
    svc = InventoryService(mock_session)
    ikey = str(uuid.uuid4())
    variant_id = uuid.uuid4()
    location = _location()
    existing = MagicMock(
        spec=InventoryMovement,
        id=uuid.uuid4(),
        variant_id=variant_id,
        location_id=location.id,
        delta_on_hand=5,
        delta_reserved=0,
        reason=MovementReason.RECEIVE,
        notes=None,
    )

    with patch.object(svc._repo, "get_location_by_key", new_callable=AsyncMock) as gl:
        gl.return_value = location
        with patch.object(svc._repo, "get_variant_with_product", new_callable=AsyncMock) as gv:
            gv.return_value = (MagicMock(), MagicMock())
            with patch.object(svc._repo, "check_idempotent", new_callable=AsyncMock) as ci:
                ci.return_value = existing
                with patch.object(svc._repo, "get_balance", new_callable=AsyncMock) as gb:
                    gb.return_value = _balance(variant_id=variant_id, location_id=location.id)
                    result = await svc.receive_stock(
                        variant_id=variant_id,
                        location_key="main",
                        quantity=5,
                        actor_id=uuid.uuid4(),
                        idempotency_key=ikey,
                    )

    ci.assert_awaited_once_with(ikey)
    assert result is not None


async def test_receive_stock_rejects_idempotency_key_reuse_with_changed_quantity() -> None:
    from modest_chic_backend.modules.inventory.service import InventoryService

    svc = InventoryService(AsyncMock())
    variant_id = uuid.uuid4()
    location = _location()
    existing = MagicMock(
        spec=InventoryMovement,
        id=uuid.uuid4(),
        variant_id=variant_id,
        location_id=location.id,
        delta_on_hand=4,
        delta_reserved=0,
        reason=MovementReason.RECEIVE,
        notes=None,
    )
    with patch.object(svc._repo, "get_location_by_key", new_callable=AsyncMock) as gl:
        gl.return_value = location
        with patch.object(svc._repo, "get_variant_with_product", new_callable=AsyncMock) as gv:
            gv.return_value = (MagicMock(), MagicMock())
            with patch.object(svc._repo, "check_idempotent", new_callable=AsyncMock) as ci:
                ci.return_value = existing
                with pytest.raises(ValueError, match="different stock movement"):
                    await svc.receive_stock(
                        variant_id=variant_id,
                        location_key="main",
                        quantity=5,
                        actor_id=uuid.uuid4(),
                        idempotency_key=str(uuid.uuid4()),
                    )


# ── US1: Adjust ──────────────────────────────────────────────────


async def test_adjust_stock_increases_on_hand() -> None:
    from modest_chic_backend.modules.inventory.service import InventoryService

    mock_session = AsyncMock()
    svc = InventoryService(mock_session)
    balance = _balance(on_hand=10, version=3)

    with patch.object(svc._repo, "get_variant_with_product", new_callable=AsyncMock) as gv:
        gv.return_value = (MagicMock(), MagicMock())
        with patch.object(svc._repo, "get_balance_for_update", new_callable=AsyncMock) as gb:
            gb.return_value = balance
            with patch.object(svc._repo, "record_movement", new_callable=AsyncMock):
                result = await svc.adjust_stock(
                    variant_id=balance.variant_id,
                    location_id=balance.location_id,
                    delta=5,
                    reason=MovementReason.ADJUST,
                    actor_id=uuid.uuid4(),
                    idempotency_key=None,
                    notes="Cycle count correction",
                )

    assert result["on_hand"] == 15
    assert balance.on_hand == 15


async def test_adjust_stock_rejects_negative_overflow() -> None:
    from modest_chic_backend.modules.inventory.service import InventoryService

    mock_session = AsyncMock()
    svc = InventoryService(mock_session)
    balance = _balance(on_hand=3)

    with patch.object(svc._repo, "get_variant_with_product", new_callable=AsyncMock) as gv:
        gv.return_value = (MagicMock(), MagicMock())
        with patch.object(svc._repo, "get_balance_for_update", new_callable=AsyncMock) as gb:
            gb.return_value = balance
            with pytest.raises(ValueError, match="reserved quantity"):
                await svc.adjust_stock(
                    variant_id=balance.variant_id,
                    location_id=balance.location_id,
                    delta=-5,
                    reason=MovementReason.ADJUST,
                    actor_id=uuid.uuid4(),
                    idempotency_key=None,
                    notes="Incorrect count",
                )


# ── US2: Reserve ────────────────────────────────────────────────


async def test_reserve_succeeds_when_stock_available() -> None:
    from modest_chic_backend.modules.inventory.service import InventoryService

    mock_session = AsyncMock()
    svc = InventoryService(mock_session)
    balance = _balance(on_hand=10, reserved=2)

    with patch.object(svc._repo, "get_balance_by_id_for_update", new_callable=AsyncMock) as gb:
        gb.return_value = balance
        with patch.object(svc._repo, "create_reservation", new_callable=AsyncMock) as cr:
            reservation = MagicMock(
                spec=InventoryReservation,
                id=uuid.uuid4(),
                status=ReservationStatus.ACTIVE,
                quantity=3,
            )
            cr.return_value = reservation
            with patch.object(svc._repo, "record_movement", new_callable=AsyncMock):
                result = await svc.reserve(
                    balance_id=balance.id,
                    order_item_id=uuid.uuid4(),
                    quantity=3,
                    expires_at=datetime.now(UTC) + timedelta(minutes=15),
                )

    assert balance.reserved == 5
    assert result["reserved"] == 5
    assert result["available"] == 5


async def test_reserve_fails_when_insufficient() -> None:
    from modest_chic_backend.modules.inventory.service import InventoryService

    mock_session = AsyncMock()
    svc = InventoryService(mock_session)
    balance = _balance(on_hand=5, reserved=4)

    with patch.object(svc._repo, "get_balance_by_id_for_update", new_callable=AsyncMock) as gb:
        gb.return_value = balance
        with pytest.raises(ValueError, match="insufficient"):
            await svc.reserve(
                balance_id=balance.id,
                order_item_id=uuid.uuid4(),
                quantity=3,
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
            )


# ── US2: Release ────────────────────────────────────────────────


async def test_release_decrements_reserved() -> None:
    from modest_chic_backend.modules.inventory.service import InventoryService

    mock_session = AsyncMock()
    svc = InventoryService(mock_session)
    balance = _balance(on_hand=10, reserved=5)
    reservation = MagicMock(
        spec=InventoryReservation,
        id=uuid.uuid4(),
        status=ReservationStatus.ACTIVE,
        quantity=2,
        balance_id=balance.id,
    )

    with patch.object(svc._repo, "get_reservation_for_update", new_callable=AsyncMock) as gr:
        gr.return_value = reservation
        with patch.object(svc._repo, "get_balance_by_id_for_update", new_callable=AsyncMock) as gb:
            gb.return_value = balance
            with patch.object(svc._repo, "record_movement", new_callable=AsyncMock):
                await svc.release(reservation.id)

    assert reservation.status == ReservationStatus.RELEASED
    assert balance.reserved == 3


async def test_release_is_idempotent() -> None:
    from modest_chic_backend.modules.inventory.service import InventoryService

    mock_session = AsyncMock()
    svc = InventoryService(mock_session)
    reservation = MagicMock(
        spec=InventoryReservation,
        id=uuid.uuid4(),
        status=ReservationStatus.RELEASED,
        quantity=1,
    )

    with patch.object(svc._repo, "get_reservation_for_update", new_callable=AsyncMock) as gr:
        gr.return_value = reservation
        result = await svc.release(reservation.id)

    assert result is not None


# ── US2: Consume ────────────────────────────────────────────────


async def test_consume_decrements_both() -> None:
    from modest_chic_backend.modules.inventory.service import InventoryService

    mock_session = AsyncMock()
    svc = InventoryService(mock_session)
    balance = _balance(on_hand=10, reserved=5)
    reservation = MagicMock(
        spec=InventoryReservation,
        id=uuid.uuid4(),
        status=ReservationStatus.ACTIVE,
        quantity=2,
        balance_id=balance.id,
    )

    with patch.object(svc._repo, "get_reservation_for_update", new_callable=AsyncMock) as gr:
        gr.return_value = reservation
        with patch.object(svc._repo, "get_balance_by_id_for_update", new_callable=AsyncMock) as gb:
            gb.return_value = balance
            with patch.object(svc._repo, "record_movement", new_callable=AsyncMock):
                await svc.consume(reservation.id)

    assert reservation.status == ReservationStatus.CONSUMED
    assert balance.on_hand == 8
    assert balance.reserved == 3


async def test_consume_is_idempotent() -> None:
    from modest_chic_backend.modules.inventory.service import InventoryService

    mock_session = AsyncMock()
    svc = InventoryService(mock_session)
    reservation = MagicMock(
        spec=InventoryReservation,
        id=uuid.uuid4(),
        status=ReservationStatus.CONSUMED,
        quantity=1,
    )

    with patch.object(svc._repo, "get_reservation_for_update", new_callable=AsyncMock) as gr:
        gr.return_value = reservation
        result = await svc.consume(reservation.id)

    assert result is not None


# ── US2: Expire ─────────────────────────────────────────────────


async def test_expire_stale_releases_expired() -> None:
    from modest_chic_backend.modules.inventory.service import InventoryService

    mock_session = AsyncMock()
    svc = InventoryService(mock_session)
    stale = MagicMock(
        spec=InventoryReservation,
        id=uuid.uuid4(),
        status=ReservationStatus.ACTIVE,
        quantity=3,
        balance_id=uuid.uuid4(),
    )

    with patch.object(svc._repo, "find_stale_reservations", new_callable=AsyncMock) as fs:
        fs.return_value = [stale]
        with patch.object(svc._repo, "get_balance_by_id_for_update", new_callable=AsyncMock) as gb:
            gb.return_value = _balance(on_hand=5, reserved=3)
            with patch.object(svc._repo, "record_movement", new_callable=AsyncMock):
                with patch(
                    "modest_chic_backend.modules.inventory.service.CouponService.resolve_order_redemption",
                    new_callable=AsyncMock,
                ):
                    result = await svc.expire_stale()

    assert result == 1
    assert stale.status == ReservationStatus.EXPIRED

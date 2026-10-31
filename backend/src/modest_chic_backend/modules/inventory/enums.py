"""Inventory enums — reservation status and movement reason."""

import enum


class ReservationStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


class MovementReason(enum.StrEnum):
    RECEIVE = "RECEIVE"
    ADJUST = "ADJUST"
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    CONSUME = "CONSUME"
    EXPIRE = "EXPIRE"
    RESTOCK = "RESTOCK"

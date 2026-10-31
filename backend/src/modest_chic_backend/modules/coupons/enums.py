"""Coupon enums."""

import enum


class CouponType(enum.StrEnum):
    FIXED = "FIXED"
    PERCENT = "PERCENT"


class CouponState(enum.StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    EXPIRED = "EXPIRED"


class CouponRedemptionStatus(enum.StrEnum):
    RESERVED = "RESERVED"
    CONSUMED = "CONSUMED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"

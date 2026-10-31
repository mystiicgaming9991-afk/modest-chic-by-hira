"""Order enums."""

import enum


class OrderSource(enum.StrEnum):
    STOREFRONT = "STOREFRONT"
    MANUAL = "MANUAL"
    SOCIAL = "SOCIAL"


class OrderState(enum.StrEnum):
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    FULFILLED = "FULFILLED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PaymentMethod(enum.StrEnum):
    COD = "COD"
    ONLINE = "ONLINE"
    MANUAL = "MANUAL"


class PaymentState(enum.StrEnum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"


class FulfillmentMethod(enum.StrEnum):
    DELIVERY = "DELIVERY"
    PICKUP = "PICKUP"

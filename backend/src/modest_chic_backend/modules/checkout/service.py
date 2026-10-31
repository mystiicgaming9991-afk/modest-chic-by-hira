"""Approved guest checkout with exact retry replay and stock reservations."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.cart.models import Cart, CartItem
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.models import Product, ProductVariant, product_categories
from modest_chic_backend.modules.checkout.repository import CheckoutRepository
from modest_chic_backend.modules.coupons.service import CouponService
from modest_chic_backend.modules.customers.service import CustomerService
from modest_chic_backend.modules.inventory.models import InventoryBalance
from modest_chic_backend.modules.inventory.service import InventoryService
from modest_chic_backend.modules.orders.models import Order, OrderItem, OrderPolicyAcceptance
from modest_chic_backend.modules.orders.service import OrderService
from modest_chic_backend.modules.payments.models import Payment, PaymentEvent
from modest_chic_backend.modules.policies.repository import PoliciesRepository
from modest_chic_backend.modules.settings.repository import SettingsRepository

_POLICY_TYPES = ("checkout_bundle", "shipping", "returns")


class CheckoutService:
    def __init__(self, session: AsyncSession, encryption_key: bytes) -> None:
        self._session = session
        self._orders = OrderService(session)
        self._repo = CheckoutRepository(session, encryption_key)
        self._settings = SettingsRepository(session)
        self._policies = PoliciesRepository(session)

    async def options(self, *, require_guest_checkout: bool = True) -> dict[str, Any]:
        guest = await self._settings.get_by_key("checkout.guest_allowed")
        cod = await self._settings.get_by_key("checkout.cod_allowed")
        availability = await self._settings.get_by_key("fulfillment.availability")
        fee = await self._settings.get_by_key("checkout.delivery_fee_minor")
        policies = [await self._policies.get_effective(kind) for kind in _POLICY_TYPES]
        open_for_checkout = (
            (not require_guest_checkout or (guest is not None and cast(Any, guest.value) is True))
            and cod is not None
            and cast(Any, cod.value) is True
            and all(policy and policy.approved_by and policy.content for policy in policies)
        )
        methods = (
            availability.value if availability and isinstance(availability.value, dict) else {}
        )
        fee_value = cast(Any, fee.value) if fee else None
        delivery_cities = methods.get("delivery_cities", [])
        pickup_cities = methods.get("pickup_cities", [])
        delivery = bool(
            open_for_checkout
            and methods.get("delivery") is True
            and isinstance(delivery_cities, list)
            and delivery_cities
            and type(fee_value) is int
            and fee_value >= 0
        )
        pickup = bool(
            open_for_checkout
            and methods.get("pickup") is True
            and isinstance(pickup_cities, list)
            and pickup_cities
        )
        return {
            "delivery_cities": (
                [city for city in delivery_cities if isinstance(city, str)] if delivery else []
            ),
            "pickup_cities": (
                [city for city in pickup_cities if isinstance(city, str)] if pickup else []
            ),
            "delivery_fee_minor": fee_value if delivery else None,
            "payment_methods": ["COD"] if delivery or pickup else [],
        }

    async def quote(
        self,
        cart_token: str,
        coupon_code: str | None = None,
        fulfillment_method: str = "DELIVERY",
        city: str | None = None,
        customer_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        cart = await self._get_cart(cart_token)
        await self._lock_stock(cart["items"])
        terms = await self._approved_terms(fulfillment_method, city)
        coupon = None
        if coupon_code:
            coupon = await CouponService(self._session).validate_coupon(
                coupon_code, cart["items"], customer_id
            )
            if coupon is None:
                raise ApplicationError(
                    422, "COUPON_INVALID", "This promotion is not available for this order."
                )
        totals = self._compute_totals(
            cart,
            terms["shipping_charge_minor"],
            int(coupon["discount_minor"]) if coupon else 0,
        )
        for item in cart["items"]:
            item["discount_minor"] = (
                coupon["allocations"].get(item["variant_id"], 0) if coupon else 0
            )
        return {
            **totals,
            "items": cart["items"],
            "cart_version": cart["version"],
            "policy_version_ids": terms["policy_version_ids"],
            "policies": terms["policies"],
            "payment_methods": ["COD"],
            "idempotency_key": secrets.token_urlsafe(24),
            "applied_coupon": (
                {"code": coupon["code"], "discount_minor": coupon["discount_minor"]}
                if coupon
                else None
            ),
        }

    async def place_order(
        self,
        cart_token: str,
        checkout_id: str,
        customer_name: str,
        customer_phone: str,
        fulfillment_method: str,
        payment_method: str,
        *,
        cart_version: int,
        accepted_total_minor: int,
        policy_version_ids: dict[str, str],
        accepted_policy: bool,
        coupon_code: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not accepted_policy:
            raise ApplicationError(422, "POLICY_REQUIRED", "Please accept the checkout terms.")
        if set(policy_version_ids) != set(_POLICY_TYPES):
            raise ApplicationError(
                422,
                "POLICY_REQUIRED",
                "Accept the current checkout, shipping, and returns policies.",
            )
        if payment_method != "COD":
            raise ApplicationError(422, "PAYMENT_UNAVAILABLE", "Only COD is available.")
        if not customer_name.strip() or not customer_phone.strip():
            raise ApplicationError(422, "CONTACT_REQUIRED", "Name and phone are required.")
        if fulfillment_method == "DELIVERY" and not kwargs.get("address_line1"):
            raise ApplicationError(422, "ADDRESS_REQUIRED", "Delivery address is required.")

        request_data = {
            "guest": hashlib.sha256(cart_token.encode()).hexdigest(),
            "customer_id": str(kwargs.get("customer_id")) if kwargs.get("customer_id") else None,
            "cart_version": cart_version,
            "accepted_total_minor": accepted_total_minor,
            "policy_version_ids": policy_version_ids,
            "coupon_code": coupon_code.strip().upper() if coupon_code else None,
            "customer_name": customer_name.strip(),
            "customer_phone": customer_phone.strip(),
            "fulfillment_method": fulfillment_method,
            "payment_method": payment_method,
            "address": kwargs,
        }
        request_hash = hashlib.sha256(
            json.dumps(request_data, sort_keys=True, default=str).encode()
        ).hexdigest()
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": checkout_id},
        )
        result = await self._session.execute(
            select(Order).where(Order.checkout_idempotency_key == checkout_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            if existing.checkout_request_hash != request_hash:
                raise ApplicationError(409, "CHECKOUT_REPLAY_CONFLICT", "This request changed.")
            token = await self._repo.replay_access_token(existing.id)
            if token is None:
                raise ApplicationError(410, "ORDER_ACCESS_EXPIRED", "Order access expired.")
            return self._order_response(existing, token)

        cart = await self._get_cart(cart_token)
        if cart["version"] != cart_version:
            raise ApplicationError(409, "CART_CHANGED", "Your cart changed. Review the quote.")
        terms = await self._approved_terms(fulfillment_method, kwargs.get("address_city"))
        if terms["policy_version_ids"] != policy_version_ids:
            raise ApplicationError(409, "POLICY_CHANGED", "Checkout terms changed. Review them.")
        balances = await self._lock_stock(cart["items"])

        if kwargs.get("customer_id") is None:
            customer = await CustomerService(self._session).resolve_customer(
                normalized_phone=customer_phone,
                display_phone=customer_phone.strip(),
                name=customer_name.strip(),
                email=kwargs.get("customer_email"),
            )
            kwargs["customer_id"] = uuid.UUID(customer["id"])
        customer_id = kwargs.get("customer_id")
        coupon = None
        if coupon_code:
            coupon = await CouponService(self._session).validate_coupon(
                coupon_code, cart["items"], customer_id, for_update=True
            )
            if coupon is None:
                raise ApplicationError(
                    409,
                    "COUPON_CHANGED",
                    "This promotion is no longer available. Review your order.",
                )
        totals = self._compute_totals(
            cart,
            terms["shipping_charge_minor"],
            int(coupon["discount_minor"]) if coupon else 0,
        )
        if totals["total_minor"] != accepted_total_minor:
            raise ApplicationError(409, "QUOTE_CHANGED", "The total changed. Review the quote.")
        if coupon:
            for item in cart["items"]:
                item["discount_allocated_minor"] = coupon["allocations"].get(item["variant_id"], 0)

        created = await self._orders.create_order(
            customer_name=customer_name.strip(),
            customer_phone=customer_phone.strip(),
            fulfillment_method=fulfillment_method,
            payment_method=payment_method,
            items=cart["items"],
            checkout_idempotency_key=checkout_id,
            source="STOREFRONT",
            policy_version_id=uuid.UUID(policy_version_ids["checkout_bundle"]),
            subtotal_minor=totals["subtotal_minor"],
            discount_minor=totals["discount_minor"],
            shipping_charge_minor=totals["shipping_charge_minor"],
            total_minor=totals["total_minor"],
            **kwargs,
        )
        order_id = uuid.UUID(created["id"])
        order = await self._session.get(Order, order_id)
        assert order is not None
        order.checkout_request_hash = request_hash
        self._session.add_all(
            OrderPolicyAcceptance(
                order_id=order_id,
                policy_type=policy_type,
                policy_version_id=uuid.UUID(version_id),
            )
            for policy_type, version_id in terms["policy_version_ids"].items()
        )
        if coupon is not None:
            await CouponService(self._session).reserve_redemption(
                code=coupon["code"],
                items=cart["items"],
                customer_id=customer_id,
                order_id=order_id,
                discount_minor=int(coupon["discount_minor"]),
                idempotency_key=f"coupon:{checkout_id}",
            )
        payment = Payment(
            order_id=order_id,
            provider="COD",
            method="COD",
            attempt_number=1,
            amount_minor=totals["total_minor"],
            currency="PKR",
            status="PENDING",
            idempotency_key=checkout_id,
        )
        self._session.add(payment)
        await self._session.flush()
        self._session.add(PaymentEvent(payment_id=payment.id, event_type="INITIATED"))
        item_result = await self._session.execute(
            select(OrderItem).where(OrderItem.order_id == order_id)
        )
        order_items = {item.variant_id: item for item in item_result.scalars().all()}
        inventory = InventoryService(self._session)
        for line in cart["items"]:
            variant_id = uuid.UUID(line["variant_id"])
            remaining = line["quantity"]
            for balance in balances[variant_id]:
                take = min(remaining, balance.on_hand - balance.reserved)
                if take > 0:
                    await inventory.reserve(
                        balance.id,
                        order_items[variant_id].id,
                        take,
                        datetime.now(UTC) + timedelta(days=2),
                        order_id=order_id,
                    )
                    remaining -= take
                if remaining == 0:
                    break
        await self._session.execute(
            delete(CartItem).where(CartItem.cart_id == uuid.UUID(cart["id"]))
        )
        cart_row = await self._session.get(Cart, uuid.UUID(cart["id"]))
        assert cart_row is not None
        cart_row.version += 1
        token, _ = await self._repo.create_access_token(order_id)
        return self._order_response(order, token)

    async def _get_cart(self, cart_token: str) -> dict[str, Any]:
        token_hash = hashlib.sha256(cart_token.encode()).hexdigest()
        result = await self._session.execute(
            select(Cart)
            .options(selectinload(Cart.items))
            .where(Cart.guest_token_hash == token_hash, Cart.expires_at > datetime.now(UTC))
            .with_for_update()
        )
        cart = result.scalar_one_or_none()
        if cart is None or not cart.items:
            raise ApplicationError(409, "EMPTY_CART", "Your cart is empty or expired.")
        variant_result = await self._session.execute(
            select(ProductVariant, Product)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(ProductVariant.id.in_([item.variant_id for item in cart.items]))
        )
        variants = {variant.id: (variant, product) for variant, product in variant_result.all()}
        category_result = await self._session.execute(
            select(product_categories.c.product_id, product_categories.c.category_id).where(
                product_categories.c.product_id.in_(
                    [product.id for _, product in variants.values()]
                )
            )
        )
        category_ids: dict[uuid.UUID, list[str]] = {}
        for product_id, category_id in category_result.all():
            category_ids.setdefault(product_id, []).append(str(category_id))
        lines = []
        for item in cart.items:
            entry = variants.get(item.variant_id)
            if (
                entry is None
                or not entry[0].is_active
                or entry[1].status != ProductStatus.PUBLISHED
            ):
                raise ApplicationError(409, "PRODUCT_UNAVAILABLE", "An item is unavailable.")
            variant, product = entry
            price = (
                variant.sale_price_minor
                if variant.sale_price_minor is not None
                else variant.price_minor
            )
            lines.append(
                {
                    "variant_id": str(variant.id),
                    "product_id": str(product.id),
                    "category_ids": category_ids.get(product.id, []),
                    "sku": variant.sku,
                    "product_title": product.title,
                    "variant_name": variant.color_name,
                    "color_name": variant.color_name,
                    "quantity": item.quantity,
                    "unit_price_minor": price,
                    "line_total_minor": price * item.quantity,
                }
            )
        return {"id": str(cart.id), "version": cart.version, "items": lines}

    async def _approved_terms(
        self,
        fulfillment_method: str,
        city: str | None = None,
        *,
        require_guest_checkout: bool = True,
    ) -> dict[str, Any]:
        guest = await self._settings.get_by_key("checkout.guest_allowed")
        cod = await self._settings.get_by_key("checkout.cod_allowed")
        availability = await self._settings.get_by_key("fulfillment.availability")
        policies = {kind: await self._policies.get_effective(kind) for kind in _POLICY_TYPES}
        if (
            (require_guest_checkout and (not guest or cast(Any, guest.value) is not True))
            or not cod
            or cast(Any, cod.value) is not True
            or any(
                policy is None or policy.approved_by is None or not policy.content
                for policy in policies.values()
            )
        ):
            raise ApplicationError(409, "CHECKOUT_CLOSED", "Checkout is not open yet.")
        methods = availability.value if availability else {}
        if not isinstance(methods, dict):
            methods = {}
        if fulfillment_method == "DELIVERY" and methods.get("delivery") is True:
            approved_cities = methods.get("delivery_cities", [])
            if not city or not isinstance(approved_cities, list) or city not in approved_cities:
                raise ApplicationError(409, "UNSERVICEABLE_CITY", "Delivery is unavailable here.")
            fee = await self._settings.get_by_key("checkout.delivery_fee_minor")
            fee_value = cast(Any, fee.value) if fee else None
            if type(fee_value) is not int or fee_value < 0:
                raise ApplicationError(
                    409, "DELIVERY_UNAVAILABLE", "Delivery terms are unavailable."
                )
            shipping = fee_value
        elif fulfillment_method == "PICKUP" and methods.get("pickup") is True:
            approved_cities = methods.get("pickup_cities", [])
            if not city or not isinstance(approved_cities, list) or city not in approved_cities:
                raise ApplicationError(409, "UNSERVICEABLE_CITY", "Pickup is unavailable here.")
            shipping = 0
        else:
            raise ApplicationError(409, "FULFILLMENT_UNAVAILABLE", "This option is unavailable.")
        accepted_policies = {
            kind: {
                "policy_version_id": str(policy.id),
                "version": policy.version,
                "content": policy.content,
            }
            for kind, policy in policies.items()
            if policy is not None
        }
        return {
            "shipping_charge_minor": shipping,
            "policy_version_ids": {
                kind: policy["policy_version_id"] for kind, policy in accepted_policies.items()
            },
            "policies": accepted_policies,
        }

    async def _lock_stock(
        self, items: list[dict[str, Any]]
    ) -> dict[uuid.UUID, list[InventoryBalance]]:
        ids = sorted(uuid.UUID(line["variant_id"]) for line in items)
        result = await self._session.execute(
            select(InventoryBalance)
            .where(InventoryBalance.variant_id.in_(ids))
            .order_by(InventoryBalance.variant_id, InventoryBalance.id)
            .with_for_update()
        )
        balances: dict[uuid.UUID, list[InventoryBalance]] = {key: [] for key in ids}
        for balance in result.scalars().all():
            balances[balance.variant_id].append(balance)
        for line in items:
            available = sum(
                balance.on_hand - balance.reserved
                for balance in balances[uuid.UUID(line["variant_id"])]
            )
            if available < line["quantity"]:
                raise ApplicationError(409, "INSUFFICIENT_STOCK", "An item is out of stock.")
        return balances

    @staticmethod
    def _compute_totals(
        cart: dict[str, Any], shipping_charge_minor: int, discount_minor: int = 0
    ) -> dict[str, int]:
        subtotal = sum(int(item["line_total_minor"]) for item in cart["items"])
        return {
            "subtotal_minor": subtotal,
            "discount_minor": discount_minor,
            "shipping_charge_minor": shipping_charge_minor,
            "total_minor": subtotal - discount_minor + shipping_charge_minor,
        }

    @staticmethod
    def _order_response(order: Order, token: str) -> dict[str, Any]:
        return {
            "order_id": str(order.id),
            "order_number": order.number,
            "state": order.state.value,
            "total_minor": order.total_minor,
            "access_token": token,
        }

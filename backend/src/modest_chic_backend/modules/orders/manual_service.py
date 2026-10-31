"""Staff-created social orders using current catalog, policy, and stock rules."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modest_chic_backend.core.errors import ApplicationError
from modest_chic_backend.modules.catalog.enums import ProductStatus
from modest_chic_backend.modules.catalog.models import Product, ProductVariant
from modest_chic_backend.modules.checkout.service import CheckoutService
from modest_chic_backend.modules.customers.service import CustomerService
from modest_chic_backend.modules.inventory.service import InventoryService
from modest_chic_backend.modules.orders.enums import OrderSource
from modest_chic_backend.modules.orders.models import Order, OrderItem, OrderPolicyAcceptance
from modest_chic_backend.modules.orders.service import OrderService
from modest_chic_backend.modules.payments.models import Payment, PaymentEvent


class ManualOrderService:
    """Create replay-safe MANUAL or SOCIAL COD orders for staff."""

    def __init__(self, session: AsyncSession, checkout: CheckoutService) -> None:
        self._session = session
        self._checkout = checkout
        self._orders = OrderService(session)

    async def create(
        self,
        *,
        idempotency_key: str,
        customer_name: str,
        customer_phone: str,
        items: list[dict[str, Any]],
        fulfillment_method: str,
        city: str,
        actor_id: uuid.UUID,
        source: str = "MANUAL",
        customer_email: str | None = None,
        address_line1: str | None = None,
        address_line2: str | None = None,
        address_area: str | None = None,
        address_postal_code: str | None = None,
        delivery_notes: str | None = None,
        attribution_source: str | None = None,
        attribution_campaign: str | None = None,
        attribution_creator_code: str | None = None,
    ) -> dict[str, Any]:
        if source not in {OrderSource.MANUAL.value, OrderSource.SOCIAL.value}:
            raise ApplicationError(
                422, "ORDER_SOURCE_INVALID", "Use MANUAL or SOCIAL as the order source."
            )
        if not customer_name.strip() or not customer_phone.strip():
            raise ApplicationError(422, "CONTACT_REQUIRED", "Customer name and phone are required.")
        if not items:
            raise ApplicationError(422, "ORDER_ITEMS_REQUIRED", "Add at least one order item.")
        if fulfillment_method == "DELIVERY" and not (address_line1 and address_line1.strip()):
            raise ApplicationError(422, "ADDRESS_REQUIRED", "Delivery address is required.")

        normalized_items: dict[uuid.UUID, int] = {}
        for item in items:
            variant_id = uuid.UUID(str(item["variant_id"]))
            quantity = int(item["quantity"])
            if quantity <= 0:
                raise ApplicationError(422, "QUANTITY_INVALID", "Item quantity must be positive.")
            normalized_items[variant_id] = normalized_items.get(variant_id, 0) + quantity

        request_data = {
            "source": source,
            "customer_name": customer_name.strip(),
            "customer_phone": customer_phone.strip(),
            "customer_email": customer_email,
            "items": sorted((str(key), value) for key, value in normalized_items.items()),
            "fulfillment_method": fulfillment_method,
            "city": city.strip(),
            "address": [
                address_line1,
                address_line2,
                address_area,
                address_postal_code,
                delivery_notes,
            ],
            "attribution": [attribution_source, attribution_campaign, attribution_creator_code],
        }
        request_hash = hashlib.sha256(
            json.dumps(request_data, sort_keys=True, default=str).encode()
        ).hexdigest()
        order_key = "manual:" + idempotency_key
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": "manual-order:" + idempotency_key},
        )
        existing = await self._session.scalar(
            select(Order).where(Order.checkout_idempotency_key == order_key)
        )
        if existing is not None:
            if existing.checkout_request_hash != request_hash:
                raise ApplicationError(
                    409,
                    "ORDER_REPLAY_CONFLICT",
                    "This request key was already used with different order details.",
                )
            return _response(existing, replayed=True)

        lines = await self._current_lines(normalized_items)
        stock = await self._checkout._lock_stock(lines)
        terms = await self._checkout._approved_terms(
            fulfillment_method, city, require_guest_checkout=False
        )
        shipping = terms["shipping_charge_minor"]
        subtotal = sum(line["line_total_minor"] for line in lines)
        total = subtotal + shipping
        customer = await CustomerService(self._session).resolve_customer(
            normalized_phone=customer_phone,
            display_phone=customer_phone.strip(),
            name=customer_name.strip(),
            email=customer_email,
        )
        created = await self._orders.create_order(
            customer_id=uuid.UUID(customer["id"]),
            customer_name=customer_name.strip(),
            customer_phone=customer_phone.strip(),
            customer_email=customer_email,
            fulfillment_method=fulfillment_method,
            payment_method="COD",
            items=lines,
            subtotal_minor=subtotal,
            discount_minor=0,
            shipping_charge_minor=shipping,
            total_minor=total,
            checkout_idempotency_key=order_key,
            source=source,
            actor_id=actor_id,
            policy_version_id=uuid.UUID(terms["policy_version_ids"]["checkout_bundle"]),
            address_line1=address_line1,
            address_line2=address_line2,
            address_area=address_area,
            address_city=city.strip(),
            address_postal_code=address_postal_code,
            delivery_notes=delivery_notes,
            attribution_source=attribution_source,
            attribution_campaign=attribution_campaign,
            attribution_creator_code=attribution_creator_code,
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
        order_items = (
            await self._session.scalars(select(OrderItem).where(OrderItem.order_id == order_id))
        ).all()
        items_by_variant = {item.variant_id: item for item in order_items}
        inventory = InventoryService(self._session)
        expires_at = datetime.now(UTC) + timedelta(days=2)
        for line in lines:
            variant_id = uuid.UUID(line["variant_id"])
            remaining = line["quantity"]
            for balance in stock[variant_id]:
                take = min(remaining, balance.on_hand - balance.reserved)
                if take > 0:
                    await inventory.reserve(
                        balance.id,
                        items_by_variant[variant_id].id,
                        take,
                        expires_at,
                        order_id=order_id,
                    )
                    remaining -= take
                if remaining == 0:
                    break
        payment = Payment(
            order_id=order_id,
            provider="COD",
            method="COD",
            attempt_number=1,
            amount_minor=total,
            currency="PKR",
            status="PENDING",
            idempotency_key=order_key,
            payment_metadata={"source": "staff_manual_order"},
        )
        self._session.add(payment)
        await self._session.flush()
        self._session.add(PaymentEvent(payment_id=payment.id, event_type="INITIATED"))
        await self._session.flush()
        return _response(order, replayed=False)

    async def _current_lines(self, requested: dict[uuid.UUID, int]) -> list[dict[str, Any]]:
        result = await self._session.execute(
            select(ProductVariant, Product)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(ProductVariant.id.in_(requested))
        )
        found = {variant.id: (variant, product) for variant, product in result.all()}
        if set(found) != set(requested):
            raise ApplicationError(409, "PRODUCT_UNAVAILABLE", "A selected variant is unavailable.")
        lines: list[dict[str, Any]] = []
        for variant_id in sorted(requested):
            variant, product = found[variant_id]
            if not variant.is_active or product.status != ProductStatus.PUBLISHED:
                raise ApplicationError(
                    409, "PRODUCT_UNAVAILABLE", "A selected variant is unavailable."
                )
            price = (
                variant.sale_price_minor
                if variant.sale_price_minor is not None
                else variant.price_minor
            )
            lines.append(
                {
                    "variant_id": str(variant.id),
                    "sku": variant.sku,
                    "product_title": product.title,
                    "variant_name": variant.color_name,
                    "color_name": variant.color_name,
                    "quantity": requested[variant_id],
                    "unit_price_minor": price,
                    "sale_price_minor": variant.sale_price_minor,
                    "line_total_minor": price * requested[variant_id],
                }
            )
        return lines


def _response(order: Order, *, replayed: bool) -> dict[str, Any]:
    return {
        "order_id": str(order.id),
        "order_number": order.number,
        "source": order.source.value,
        "state": order.state.value,
        "total_minor": order.total_minor,
        "replayed": replayed,
    }

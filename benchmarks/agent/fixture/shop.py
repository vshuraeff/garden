"""Stable checkout contract with a legacy monolithic implementation."""

from __future__ import annotations

from collections.abc import Mapping


def checkout(
    order_id: str,
    sku: str,
    quantity: int,
    unit_price_cents: int,
    stock: Mapping[str, int],
    coupon_code: str,
    recipient: str,
) -> dict[str, object]:
    """Return the stable checkout result consumed by the CLI."""

    if not order_id or not sku or not recipient:
        raise ValueError("order_id, sku, and recipient must not be empty")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    available = stock.get(sku, 0)
    if available < quantity:
        raise ValueError(f"insufficient stock for {sku}")
    updated_stock = dict(stock)
    updated_stock[sku] = available - quantity
    subtotal_cents = quantity * unit_price_cents
    percent = {"SAVE10": 10, "SAVE20": 20}.get(coupon_code.strip(), 0)
    total_cents = (subtotal_cents * (100 - percent) + 50) // 100
    order = {
        "id": order_id,
        "sku": sku,
        "quantity": quantity,
        "unit_price_cents": unit_price_cents,
        "subtotal_cents": subtotal_cents,
        "total_cents": total_cents,
    }
    notification = f"to {recipient}: order {order_id} charged {total_cents} cents"
    return {
        "notification": notification,
        "order": order,
        "stock": updated_stock,
    }


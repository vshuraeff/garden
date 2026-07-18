"""Public order record construction."""

from __future__ import annotations


def create_order(
    order_id: str,
    sku: str,
    quantity: int,
    unit_price_cents: int,
    total_cents: int,
) -> dict[str, int | str]:
    """Return a validated order record."""

    if not order_id:
        raise ValueError("order_id must not be empty")
    if not sku:
        raise ValueError("sku must not be empty")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if unit_price_cents < 0 or total_cents < 0:
        raise ValueError("prices must not be negative")
    return {
        "id": order_id,
        "sku": sku,
        "quantity": quantity,
        "unit_price_cents": unit_price_cents,
        "subtotal_cents": quantity * unit_price_cents,
        "total_cents": total_cents,
    }


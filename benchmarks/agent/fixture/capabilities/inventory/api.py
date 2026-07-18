"""Public inventory reservation behavior."""

from __future__ import annotations

from collections.abc import Mapping


def reserve(stock: Mapping[str, int], sku: str, quantity: int) -> dict[str, int]:
    """Return a new stock mapping with one reservation applied."""

    if quantity <= 0:
        raise ValueError("quantity must be positive")
    available = stock.get(sku, 0)
    if available < quantity:
        raise ValueError(f"insufficient stock for {sku}")
    updated = dict(stock)
    updated[sku] = available - quantity
    return updated


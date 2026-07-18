"""Public coupon and total calculations."""

from __future__ import annotations


COUPON_DISCOUNTS = {"SAVE10": 10, "SAVE20": 20}


def discount_percent(coupon_code: str) -> int:
    """Return the percentage registered for a coupon code."""

    return COUPON_DISCOUNTS.get(coupon_code.strip(), 0)


def discounted_total(subtotal_cents: int, percent: int) -> int:
    """Apply a percentage discount using integer half-up rounding."""

    if subtotal_cents < 0:
        raise ValueError("subtotal_cents must not be negative")
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return (subtotal_cents * (100 - percent) + 50) // 100


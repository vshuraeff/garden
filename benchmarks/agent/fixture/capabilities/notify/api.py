"""Public notification formatting."""

from __future__ import annotations


def order_confirmation(recipient: str, order_id: str, total_cents: int) -> str:
    """Return the stable customer confirmation text."""

    if not recipient:
        raise ValueError("recipient must not be empty")
    return f"to {recipient}: order {order_id} charged {total_cents} cents"


from __future__ import annotations

import unittest

from capabilities.orders.api import create_order


class OrderTests(unittest.TestCase):
    def test_create_order_builds_public_record(self) -> None:
        self.assertEqual(
            {
                "id": "o-1",
                "quantity": 2,
                "sku": "widget",
                "subtotal_cents": 1000,
                "total_cents": 900,
                "unit_price_cents": 500,
            },
            create_order("o-1", "widget", 2, 500, 900),
        )


if __name__ == "__main__":
    unittest.main()


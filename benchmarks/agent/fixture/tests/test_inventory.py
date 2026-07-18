from __future__ import annotations

import unittest

from capabilities.inventory.api import reserve


class InventoryTests(unittest.TestCase):
    def test_reserve_returns_updated_copy(self) -> None:
        stock = {"widget": 5}

        updated = reserve(stock, "widget", 2)

        self.assertEqual({"widget": 3}, updated)
        self.assertEqual({"widget": 5}, stock)

    def test_reserve_rejects_insufficient_stock(self) -> None:
        with self.assertRaisesRegex(ValueError, "insufficient stock for widget"):
            reserve({"widget": 1}, "widget", 2)


if __name__ == "__main__":
    unittest.main()


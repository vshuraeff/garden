from __future__ import annotations

import unittest

from capabilities.pricing.api import discount_percent, discounted_total


class PricingTests(unittest.TestCase):
    def test_registered_coupon_and_unknown_coupon(self) -> None:
        self.assertEqual(10, discount_percent("SAVE10"))
        self.assertEqual(0, discount_percent("UNKNOWN"))

    def test_discounted_total_uses_half_up_rounding(self) -> None:
        self.assertEqual(1800, discounted_total(2000, 10))
        self.assertEqual(1799, discounted_total(1999, 10))


if __name__ == "__main__":
    unittest.main()

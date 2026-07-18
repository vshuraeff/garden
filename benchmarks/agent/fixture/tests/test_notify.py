from __future__ import annotations

import unittest

from capabilities.notify.api import order_confirmation


class NotifyTests(unittest.TestCase):
    def test_order_confirmation_has_stable_text(self) -> None:
        self.assertEqual(
            "to buyer@example.test: order o-1 charged 900 cents",
            order_confirmation("buyer@example.test", "o-1", 900),
        )


if __name__ == "__main__":
    unittest.main()


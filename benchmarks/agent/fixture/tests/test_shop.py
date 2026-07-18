from __future__ import annotations

import contextlib
import io
import json
import unittest

import cli
from shop import checkout


EXPECTED_CHECKOUT = {
    "notification": "to buyer@example.test: order o-1 charged 900 cents",
    "order": {
        "id": "o-1",
        "quantity": 2,
        "sku": "widget",
        "subtotal_cents": 1000,
        "total_cents": 900,
        "unit_price_cents": 500,
    },
    "stock": {"widget": 3},
}


class CheckoutContractTests(unittest.TestCase):
    def test_checkout_public_result(self) -> None:
        self.assertEqual(
            EXPECTED_CHECKOUT,
            checkout(
                "o-1",
                "widget",
                2,
                500,
                {"widget": 5},
                "SAVE10",
                "buyer@example.test",
            ),
        )

    def test_cli_emits_stable_compact_json(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = cli.main(
                [
                    "o-1",
                    "widget",
                    "2",
                    "500",
                    '{"widget":5}',
                    "SAVE10",
                    "buyer@example.test",
                ]
            )

        self.assertEqual(0, exit_code)
        self.assertEqual(EXPECTED_CHECKOUT, json.loads(output.getvalue()))
        self.assertEqual(
            json.dumps(EXPECTED_CHECKOUT, sort_keys=True, separators=(",", ":")) + "\n",
            output.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()

"""JSON command-line boundary for the toy checkout."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from shop import checkout


def build_parser() -> argparse.ArgumentParser:
    """Return the stable checkout argument parser."""

    parser = argparse.ArgumentParser(prog="toy-checkout")
    parser.add_argument("order_id")
    parser.add_argument("sku")
    parser.add_argument("quantity", type=int)
    parser.add_argument("unit_price_cents", type=int)
    parser.add_argument("stock_json")
    parser.add_argument("coupon_code")
    parser.add_argument("recipient")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Print one stable compact JSON checkout record."""

    args = build_parser().parse_args(argv)
    stock = json.loads(args.stock_json)
    if not isinstance(stock, dict) or not all(
        isinstance(key, str) and isinstance(value, int)
        for key, value in stock.items()
    ):
        raise ValueError("stock_json must decode to an object of integer counts")
    result = checkout(
        args.order_id,
        args.sku,
        args.quantity,
        args.unit_price_cents,
        stock,
        args.coupon_code,
        args.recipient,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

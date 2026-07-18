#!/usr/bin/env -S uv run --no-project
"""Run with: uv run --no-project fixture/verify/T2.py <cell-workdir>."""

from __future__ import annotations

import sys

from _common import (
    add_target_to_import_path,
    finish,
    function_arguments,
    imported_modules,
    parse_module,
    run_unittest_suite,
    target_from_argv,
)


EXPECTED_ARGUMENTS = [
    "stock",
    "order_id",
    "sku",
    "quantity",
    "unit_price_cents",
    "total_cents",
]


def main(argv: list[str] | None = None) -> int:
    """Verify the T2 orders-to-inventory feature."""

    arguments = argv or sys.argv
    target = target_from_argv(arguments)
    errors: list[str] = []
    feature_test = target / "tests" / "test_t2_feature.py"
    if not feature_test.is_file():
        errors.append("tests/test_t2_feature.py is missing")

    orders_path = target / "capabilities" / "orders" / "api.py"
    tree = parse_module(orders_path)
    function_args = function_arguments(tree, "reserve_and_create_order")
    if function_args != EXPECTED_ARGUMENTS:
        errors.append("reserve_and_create_order signature is missing or changed")

    imports = imported_modules(tree)
    capability_imports = {
        module for module in imports if module.startswith("capabilities.")
    }
    if not any(
        module.startswith("capabilities.inventory") for module in capability_imports
    ):
        errors.append("orders does not use the public inventory boundary")
    forbidden = sorted(
        module
        for module in capability_imports
        if module.startswith(("capabilities.pricing", "capabilities.notify"))
    )
    if forbidden:
        errors.append(f"orders crosses unregistered capability boundaries: {forbidden}")

    add_target_to_import_path(target)
    try:
        from capabilities.orders.api import reserve_and_create_order

        original = {"widget": 5}
        order, updated = reserve_and_create_order(
            original, "o-2", "widget", 2, 500, 900
        )
        if original != {"widget": 5} or updated != {"widget": 3}:
            errors.append("reservation mutates input or returns the wrong stock")
        if order.get("id") != "o-2" or order.get("total_cents") != 900:
            errors.append("created order does not preserve create_order behavior")
    except Exception as error:
        errors.append(f"reserved-order contract is not callable: {error}")

    suite = run_unittest_suite(target)
    if not suite["passed"]:
        errors.append("fixture unittest suite failed")
    return finish("T2", suite, errors)


if __name__ == "__main__":
    raise SystemExit(main())


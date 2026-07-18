#!/usr/bin/env -S uv run --no-project
"""Run with: uv run --no-project fixture/verify/T3.py <cell-workdir>."""

from __future__ import annotations

import json
import os
import subprocess
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


CHECKOUT_ARGUMENTS = [
    "order_id",
    "sku",
    "quantity",
    "unit_price_cents",
    "stock",
    "coupon_code",
    "recipient",
]
EXPECTED_RESULT = {
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


def main(argv: list[str] | None = None) -> int:
    """Verify the T3 migration and stable public contracts."""

    arguments = argv or sys.argv
    target = target_from_argv(arguments)
    errors: list[str] = []
    migration_test = target / "tests" / "test_t3_migration.py"
    if not migration_test.is_file():
        errors.append("tests/test_t3_migration.py is missing")

    shop_path = target / "shop.py"
    tree = parse_module(shop_path)
    if function_arguments(tree, "checkout") != CHECKOUT_ARGUMENTS:
        errors.append("checkout public signature changed")
    imports = imported_modules(tree)
    for capability in ("orders", "inventory", "pricing", "notify"):
        prefix = f"capabilities.{capability}"
        if not any(module.startswith(prefix) for module in imports):
            errors.append(f"shop does not compose the {capability} public boundary")

    add_target_to_import_path(target)
    try:
        from shop import checkout

        result = checkout(
            "o-1",
            "widget",
            2,
            500,
            {"widget": 5},
            "SAVE10",
            "buyer@example.test",
        )
        if result != EXPECTED_RESULT:
            errors.append("checkout return contract changed")
    except Exception as error:
        errors.append(f"checkout contract is not callable: {error}")

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "o-1",
            "widget",
            "2",
            "500",
            '{"widget":5}',
            "SAVE10",
            "buyer@example.test",
        ],
        cwd=target,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    expected_stdout = json.dumps(
        EXPECTED_RESULT, sort_keys=True, separators=(",", ":")
    ) + "\n"
    if completed.returncode != 0 or completed.stdout != expected_stdout:
        errors.append("CLI JSON output contract changed")

    suite = run_unittest_suite(target)
    if not suite["passed"]:
        errors.append("fixture unittest suite failed")
    return finish("T3", suite, errors)


if __name__ == "__main__":
    raise SystemExit(main())

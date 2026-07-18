#!/usr/bin/env -S uv run --no-project
"""Run with: uv run --no-project fixture/verify/T1.py <cell-workdir>."""

from __future__ import annotations

import sys

from _common import (
    add_target_to_import_path,
    finish,
    function_arguments,
    parse_module,
    run_unittest_suite,
    target_from_argv,
)


def main(argv: list[str] | None = None) -> int:
    """Verify the T1 regression and pricing public contract."""

    arguments = argv or sys.argv
    target = target_from_argv(arguments)
    errors: list[str] = []
    regression = target / "tests" / "test_t1_regression.py"
    if not regression.is_file():
        errors.append("tests/test_t1_regression.py is missing")
    elif "discount_percent" not in regression.read_text(encoding="utf-8"):
        errors.append("T1 regression test no longer exercises discount_percent")

    pricing_path = target / "capabilities" / "pricing" / "api.py"
    function_args = function_arguments(parse_module(pricing_path), "discount_percent")
    if function_args != ["coupon_code"]:
        errors.append("discount_percent(coupon_code) signature changed")

    add_target_to_import_path(target)
    try:
        from capabilities.pricing.api import discount_percent

        if discount_percent("  save10 ") != 10:
            errors.append("whitespace and lowercase coupon lookup still fails")
        if discount_percent("unknown") != 0:
            errors.append("unknown coupon behavior changed")
    except Exception as error:
        errors.append(f"pricing contract is not callable: {error}")

    suite = run_unittest_suite(target)
    if not suite["passed"]:
        errors.append("fixture unittest suite failed")
    return finish("T1", suite, errors)


if __name__ == "__main__":
    raise SystemExit(main())


"""Shared stdlib helpers for task verifiers."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def target_from_argv(argv: list[str]) -> Path:
    """Return the validated fixture workdir argument."""

    if len(argv) != 2:
        raise ValueError("expected exactly one cell-workdir argument")
    target = Path(argv[1]).resolve()
    if not (target / "capabilities").is_dir() or not (target / "tests").is_dir():
        raise ValueError(f"not a fixture workdir: {target}")
    return target


def run_unittest_suite(target: Path) -> dict[str, Any]:
    """Run the fixture suite without writing bytecode into the workdir."""

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
            "-v",
        ],
        cwd=target,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    return {
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
    }


def parse_module(path: Path) -> ast.Module:
    """Parse one Python module from the target workdir."""

    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def function_arguments(tree: ast.Module, name: str) -> list[str] | None:
    """Return positional argument names for a top-level function."""

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return [argument.arg for argument in node.args.args]
    return None


def imported_modules(tree: ast.Module) -> set[str]:
    """Return statically declared import module names."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def add_target_to_import_path(target: Path) -> None:
    """Make the isolated target importable by this verifier process."""

    sys.path.insert(0, str(target))


def finish(task_id: str, suite: dict[str, Any], errors: list[str]) -> int:
    """Print one small JSON result and return the verifier exit code."""

    passed = bool(suite.get("passed")) and not errors
    print(
        json.dumps(
            {
                "errors": errors,
                "pass": passed,
                "task_id": task_id,
                "unittest": suite,
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 1


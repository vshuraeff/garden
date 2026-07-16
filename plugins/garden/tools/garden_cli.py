#!/usr/bin/env -S uv run --no-project
"""Command-line access to the same deterministic checks as the GARDEN hooks."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Iterable

from config_schema import ConfigError
from garden_config import (
    ConfigWriteError,
    initialize_config,
    load_config,
    migrate_config,
    migrate_config_to_schema_v2,
    render_effective,
    resolve_effective,
)
from garden_core import inspect_file, inspect_project
from garden_project import install, remove


def _print_config_errors(errors: Iterable[ConfigError]) -> None:
    for error in errors:
        print(error, file=sys.stderr)


def _has_expired_exception(exceptions: list[dict[str, object]]) -> bool:
    for exception in exceptions:
        review_after = exception.get("review_after")
        if not isinstance(review_after, str) or not review_after:
            continue
        try:
            review_date = date.fromisoformat(review_after)
        except ValueError:
            continue
        if review_date < date.today():
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="garden")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="inspect one project")
    inspect_parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "also fail when the project is not an active GARDEN project; "
            "an inactive or unrecognized root must never count as a passing audit"
        ),
    )
    inspect_parser.add_argument("root", nargs="?", default=".")

    file_parser = subparsers.add_parser("check-file", help="check one changed file")
    file_parser.add_argument("path")

    config_parser = subparsers.add_parser("config", help="validate or show config")
    config_subparsers = config_parser.add_subparsers(
        dest="config_command", required=True
    )
    for command in ("validate", "show"):
        parser_for_command = config_subparsers.add_parser(command)
        parser_for_command.add_argument("root", nargs="?", default=".")

    init_parser = subparsers.add_parser("init", help="initialize .garden.toml")
    init_parser.add_argument("root", nargs="?", default=".")
    init_parser.add_argument("--force", action="store_true")

    migrate_parser = subparsers.add_parser(
        "migrate-config", help="migrate legacy project activation"
    )
    migrate_parser.add_argument("root", nargs="?", default=".")
    migrate_parser.add_argument("--force", action="store_true")
    migrate_parser.add_argument("--to-schema", type=int, choices=[2])
    migrate_parser.add_argument("--owner")

    for command in ("install-project", "remove-project"):
        project_parser = subparsers.add_parser(command)
        project_parser.add_argument("root")
        project_parser.add_argument(
            "--harness", choices=("claude", "codex", "both"), required=True
        )
        project_parser.add_argument("--force", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "inspect":
        value = inspect_project(Path(args.root))
        has_errors = bool(value.get("summary", {}).get("errors", 0))
        if args.strict and (
            not value.get("active", False)
            or not value.get("configuration", {}).get("valid", False)
            or not value.get("complete", False)
            or _has_expired_exception(value.get("exceptions", []))
        ):
            has_errors = True
    elif args.command == "check-file":
        findings = [finding.__dict__ for finding in inspect_file(Path(args.path))]
        value = {
            "path": str(Path(args.path).resolve()),
            "findings": findings,
        }
        has_errors = any(finding["severity"] == "error" for finding in findings)
    elif args.command in ("install-project", "remove-project"):
        action = install if args.command == "install-project" else remove
        action(Path(args.root).resolve(), args.harness, force=args.force)
        value = {
            "action": args.command,
            "root": str(Path(args.root).resolve()),
            "harness": args.harness,
        }
        has_errors = False
    elif args.command == "config":
        result = load_config(Path(args.root))
        if result.errors:
            _print_config_errors(result.errors)
            return 1
        if args.config_command == "validate":
            if result.present:
                print(f"valid: {result.path}")
            else:
                print(f"valid: no .garden.toml at {result.root}")
        else:
            print(render_effective(resolve_effective(result.config)), end="")
        return 0

    else:
        if (
            args.command == "migrate-config"
            and args.owner is not None
            and args.to_schema != 2
        ):
            print("--owner requires --to-schema 2", file=sys.stderr)
            return 1
        try:
            if args.command == "init":
                destination = initialize_config(Path(args.root), force=args.force)
            elif args.to_schema == 2:
                destination = migrate_config_to_schema_v2(
                    Path(args.root), force=args.force, owner=args.owner
                )
            else:
                destination = migrate_config(Path(args.root), force=args.force)
        except (ConfigWriteError, OSError) as error:
            print(error, file=sys.stderr)
            return 1
        print(destination)
        return 0

    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

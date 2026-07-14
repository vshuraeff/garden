from __future__ import annotations

import json
import random
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from config_schema import CAPABILITY_STRATEGIES, PROJECT_TYPES  # noqa: E402
from garden_config import (  # noqa: E402
    load_config,
    render_effective,
    resolve_effective,
)
from garden_core import inspect_project  # noqa: E402
from garden_paths import _relative_path, is_within  # noqa: E402


RANDOM_SEED = 20260714


def _build_random_project(root: Path, rng: random.Random) -> None:
    root.mkdir()
    (root / "naming-registry.txt").write_text("root: root\n", encoding="utf-8")
    if rng.choice((True, False)):
        (root / "CONTEXT.md").write_text("# Context\n", encoding="utf-8")
    for index in range(rng.randint(1, 4)):
        name = f"cap-{index}-{rng.randrange(1000)}"
        capability = root / name
        capability.mkdir()
        (capability / "handler.py").write_text("pass\n", encoding="utf-8")
        if rng.choice((True, False)):
            (capability / "CONTRACT.md").write_text(
                "Version: 1.0.0\n", encoding="utf-8"
            )
        if rng.choice((True, False)):
            (capability / "test_handler.py").write_text(
                "def test_handler():\n    pass\n", encoding="utf-8"
            )


class GardenPropertyTests(unittest.TestCase):
    def test_path_confinement_invariant(self) -> None:
        rng = random.Random(RANDOM_SEED)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for _ in range(150):
                parts: list[str] = []
                for _ in range(rng.randint(0, 8)):
                    if rng.randrange(5) == 0:
                        parts.append(".")
                    parts.append(
                        f"segment-{rng.randrange(10_000)}-{rng.choice('abcxyz')}"
                    )
                relative = Path(*parts) if parts else Path(".")
                candidate = (root / relative).resolve()
                expected = candidate.relative_to(root)

                self.assertTrue(
                    is_within(candidate, root),
                    f"joined path escaped confinement: {relative!s}",
                )
                self.assertEqual(
                    expected,
                    _relative_path(candidate, root),
                    f"confinement helpers disagreed for {relative!s}",
                )

    def test_report_round_trip_is_json_lossless(self) -> None:
        rng = random.Random(RANDOM_SEED + 1)
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            for index in range(10):
                root = workspace / f"project-{index}"
                _build_random_project(root, rng)
                report = inspect_project(root)
                round_tripped = json.loads(json.dumps(report))

                self.assertEqual(
                    report,
                    round_tripped,
                    f"report was not JSON-lossless for {root.name}: {report!r}",
                )

    def test_config_resolution_and_rendering_are_idempotent(self) -> None:
        rng = random.Random(RANDOM_SEED + 2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for _ in range(30):
                project_type = rng.choice(PROJECT_TYPES)
                strategy = rng.choice(CAPABILITY_STRATEGIES)
                segments = [f"area-{rng.randrange(10_000)}" for _ in range(3)]
                include = ", ".join(
                    f'"src/{segment}/**/*.py"'
                    for segment in segments[: rng.randint(1, 3)]
                )
                exclude = ", ".join(
                    f'"src/{segment}/generated/**"'
                    for segment in segments[: rng.randint(1, 2)]
                )
                content = (
                    "schema_version = 1\n"
                    f'[project]\ntype = "{project_type}"\n'
                    f"[scan]\ninclude = [{include}]\nexclude = [{exclude}]\n"
                    "[capabilities]\n"
                    f'strategy = "{strategy}"\n'
                    'roots = ["src", "lib"]\n'
                    f"depth = {rng.randint(1, 3)}\n"
                    "[tests]\n"
                    'patterns = ["**/test_*.py"]\n'
                    f'association = "{rng.choice(("same-capability", "test-roots"))}"\n'
                    "[documentation]\nroot_context_required = false\n"
                )
                (root / ".garden.toml").write_text(content, encoding="utf-8")
                loaded = load_config(root)

                self.assertEqual(
                    (), loaded.errors, f"generated config was invalid: {content!r}"
                )
                first = resolve_effective(loaded.config)
                second = resolve_effective(loaded.config)
                self.assertEqual(
                    first,
                    second,
                    f"resolution was not idempotent for {content!r}",
                )
                self.assertEqual(
                    render_effective(first),
                    render_effective(second),
                    f"rendering was not idempotent for {content!r}",
                )

    def test_reports_have_no_duplicate_or_conflicting_finding_identity(self) -> None:
        rng = random.Random(RANDOM_SEED + 3)
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            for index in range(20):
                root = workspace / f"project-{index}"
                _build_random_project(root, rng)
                findings = inspect_project(root)["findings"]
                identities = [
                    (
                        finding["severity"],
                        finding["rule"],
                        finding["path"],
                        finding["message"],
                    )
                    for finding in findings
                ]
                severities: dict[tuple[str, str], set[str]] = {}
                for finding in findings:
                    key = (finding["rule"], finding["path"])
                    severities.setdefault(key, set()).add(finding["severity"])

                self.assertEqual(
                    len(identities),
                    len(set(identities)),
                    f"exact duplicate finding in {root.name}: {findings!r}",
                )
                self.assertTrue(
                    all(len(values) == 1 for values in severities.values()),
                    f"conflicting finding severities in {root.name}: {findings!r}",
                )


if __name__ == "__main__":
    unittest.main()

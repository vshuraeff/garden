#!/usr/bin/env -S uv run --no-project
"""Run explicit snapshot mutations against their named owning gates.

Mutation payloads use one checked-in JSON file containing reusable base trees
and one explicit operation per manifest row. Repository-level gates receive a
temporary copy of the pinned repository; smaller gates receive standalone base
files from the payload. Every target is hashed before and after mutation, then
reversed and hash-checked before the temporary directory is discarded.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

from lib.mutation_ops import (
    apply_mutation,
    materialize_files,
    reverse_mutation,
    reversal_is_exact,
)
from lib.provenance import (
    git_commit,
    load_toolchain,
    normalize_path_bytes,
    platform_string,
    plugin_version,
    python_version_string,
    repository_root,
    sha256_bytes,
)


EXPECTED_CATEGORY_COUNTS = {
    "config-schema-or-path-confinement": 8,
    "activation-file-limits-incomplete-scan": 6,
    "enforced-context-naming-contract": 8,
    "evidence-registry-citations": 8,
    "doc-metadata-links-rule-sync": 6,
    "manifests-package-reference-drift": 6,
    "security-property-regressions": 6,
    "gap-probe": 8,
    "clean-control": 12,
}


def mutation_root() -> Path:
    """Return the mutation corpus root."""

    return Path(__file__).resolve().parent / "mutations"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_inputs() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = _load_json(mutation_root() / "manifest.json")
    payloads = _load_json(mutation_root() / "payloads" / "snapshots.json")
    if not isinstance(manifest, list) or len(manifest) != 68:
        raise ValueError("mutation manifest must contain exactly 68 rows")
    if not isinstance(payloads, dict):
        raise TypeError("mutation payload file must be an object")
    counts = Counter(str(row["category"]) for row in manifest)
    if counts != Counter(EXPECTED_CATEGORY_COUNTS):
        raise ValueError(f"mutation category counts differ: {dict(counts)}")
    classifications = Counter(str(row["classification"]) for row in manifest)
    if classifications != Counter(
        {"must_block": 51, "gap_probe": 4, "clean_control": 13}
    ):
        raise ValueError(f"mutation classifications differ: {dict(classifications)}")
    mutations = payloads.get("mutations")
    if not isinstance(mutations, dict):
        raise TypeError("mutation payload map is missing")
    manifest_ids = {str(row["mutation_id"]) for row in manifest}
    if manifest_ids != set(mutations):
        raise ValueError("manifest and payload mutation IDs differ")
    return manifest, payloads


def _copy_repository(destination: Path) -> None:
    source = repository_root()

    def ignored(directory: str, names: list[str]) -> set[str]:
        relative = Path(directory).resolve().relative_to(source)
        excluded = {
            name
            for name in names
            if name in {".git", "__pycache__"} or name.endswith(".pyc")
        }
        if relative == Path("benchmarks"):
            excluded.add("results")
        return excluded

    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        ignore=ignored,
    )


def _initialize_git(root: Path) -> None:
    commands = (
        ["git", "init", "-q"],
        ["git", "config", "maintenance.auto", "false"],
        ["git", "config", "gc.auto", "0"],
        ["git", "add", "--all"],
        [
            "git",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=garden-benchmark",
            "-c",
            "user.email=benchmark@example.invalid",
            "commit",
            "-q",
            "--no-verify",
            "-m",
            "temporary benchmark baseline",
        ],
    )
    for command in commands:
        subprocess.run(command, cwd=root, check=True, capture_output=True)


def _materialize_base(
    root: Path, payload: Mapping[str, Any], payloads: Mapping[str, Any]
) -> None:
    bases = payloads.get("bases")
    if not isinstance(bases, Mapping):
        raise TypeError("mutation bases are missing")
    base_name = str(payload["base"])
    base = bases.get(base_name)
    if not isinstance(base, Mapping):
        raise KeyError(f"unknown mutation base: {base_name}")
    source = base.get("source")
    if source in ("repository", "repository-git"):
        _copy_repository(root)
        if source == "repository-git":
            _initialize_git(root)
        return
    files = base.get("files")
    if not isinstance(files, Mapping):
        raise TypeError(f"base {base_name} has no files")
    materialize_files(root, files)


def _install_evidence_validator(root: Path) -> None:
    destination = root / "plugins" / "garden" / "tools" / "validate_evidence.py"
    if destination.exists():
        return
    destination.parent.mkdir(parents=True)
    source = repository_root() / "plugins" / "garden" / "tools" / "validate_evidence.py"
    shutil.copy2(source, destination)


def _gate_command(gate: str, root: Path) -> list[str]:
    original_tools = repository_root() / "plugins" / "garden" / "tools"
    copied_tools = root / "plugins" / "garden" / "tools"
    if gate == "garden-config-validate":
        return [
            "uv",
            "run",
            "--no-project",
            str(original_tools / "garden_cli.py"),
            "config",
            "validate",
            str(root),
        ]
    if gate == "garden-inspect-strict":
        return [
            "uv",
            "run",
            "--no-project",
            str(original_tools / "garden_cli.py"),
            "inspect",
            "--strict",
            str(root),
        ]
    if gate == "validate-evidence":
        _install_evidence_validator(root)
        return [
            "uv",
            "run",
            "--no-project",
            str(copied_tools / "validate_evidence.py"),
        ]
    if gate == "validate-docs":
        script = copied_tools / "validate_docs.py"
        return ["uv", "run", "--no-project", str(script)]
    if gate == "validate-package":
        script = copied_tools / "validate_package.py"
        return ["uv", "run", "--no-project", str(script)]
    if gate == "sync-references-check":
        script = copied_tools / "sync_references.py"
        return ["uv", "run", "--no-project", str(script), "--check"]
    if gate == "plugin-version-check":
        script = copied_tools / "plugin_version.py"
        return [
            "uv",
            "run",
            "--no-project",
            str(script),
            "check",
            "--base",
            "HEAD",
        ]
    raise ValueError(f"unknown owning gate: {gate}")


def _rule_ids(stdout: bytes) -> list[str]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    findings = payload.get("findings", [])
    return sorted(
        {
            str(finding["rule"])
            for finding in findings
            if isinstance(finding, dict) and isinstance(finding.get("rule"), str)
        }
    )


def _outcome(**values: object) -> str:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _run_mutation(
    row: Mapping[str, Any],
    payload: Mapping[str, Any],
    payloads: Mapping[str, Any],
    toolchain: Mapping[str, Any],
    commit: str,
    version: str,
) -> tuple[dict[str, Any], bool, bool, bool]:
    with tempfile.TemporaryDirectory(prefix="garden-mutation-") as directory:
        root = Path(directory)
        _materialize_base(root, payload, payloads)
        state = apply_mutation(root, payload)
        if state.target_path != row["target_path"]:
            raise ValueError(f"target mismatch for {row['mutation_id']}")
        command = _gate_command(str(row["owning_gate"]), root)
        started = time.perf_counter_ns()
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            check=False,
        )
        elapsed = time.perf_counter_ns() - started
        combined = completed.stdout + completed.stderr
        signature = str(row["expected_rule_id_or_signature"])
        signature_seen = signature != "none" and signature.encode() in combined
        blocked = completed.returncode != 0
        killed = blocked and signature_seen
        detected = signature_seen
        reverse_mutation(root, state)
        reversed_exactly = reversal_is_exact(root, state)
        if not reversed_exactly:
            raise RuntimeError(f"mutation reversal failed: {row['mutation_id']}")

    classification = str(row["classification"])
    if classification == "must_block":
        expected = {"killed": True}
        actual = {
            "blocked": blocked,
            "killed": killed,
            "signature_seen": signature_seen,
        }
    elif classification == "gap_probe":
        expected = {"gap_probe_kind": row["gap_probe_kind"]}
        actual = {
            "blocked": blocked,
            "detected": detected,
            "signature_seen": signature_seen,
        }
    else:
        expected = {"blocked": False}
        actual = {"blocked": blocked, "signature_seen": signature_seen}
    actual.update(
        {
            "after_sha256": state.after_sha256,
            "after_file_count": len(state.after_file_sha256),
            "before_sha256": state.before_sha256,
            "before_file_count": len(state.before_file_sha256),
            "reversed_exactly": reversed_exactly,
        }
    )
    findings = _rule_ids(completed.stdout)
    if signature_seen and signature != "none" and signature not in findings:
        findings.append(signature)
    record = {
        "schema_version": str(toolchain["schema_version"]),
        "benchmark_version": str(toolchain["benchmark_version"]),
        "suite": "mutations",
        "case_id": row["mutation_id"],
        "condition": classification,
        "repository_commit": toolchain["repository_commit"],
        "garden_commit": commit,
        "plugin_version": version,
        "seed": toolchain["seed"],
        "expected_outcome": _outcome(**expected),
        "actual_outcome": _outcome(**actual),
        "exit_code": completed.returncode,
        "finding_ids": sorted(set(findings)),
        "stdout_sha256": sha256_bytes(normalize_path_bytes(completed.stdout, [root])),
        "stderr_sha256": sha256_bytes(normalize_path_bytes(completed.stderr, [root])),
        "elapsed_ns": elapsed,
        "platform": platform_string(),
        "python_version": python_version_string(),
    }
    return record, killed, detected, blocked


def _write_records(
    stream: TextIO,
    rows: Sequence[Mapping[str, Any]],
    payloads: Mapping[str, Any],
    toolchain: Mapping[str, Any],
    commit: str,
    version: str,
) -> tuple[int, int, int, list[str]]:
    must_killed = gap_detected = clean_blocked = 0
    gap_outcomes: list[str] = []
    mutation_payloads = payloads["mutations"]
    for row in rows:
        payload = mutation_payloads[row["mutation_id"]]
        record, killed, detected, blocked = _run_mutation(
            row, payload, payloads, toolchain, commit, version
        )
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        classification = row["classification"]
        if classification == "must_block":
            must_killed += killed
        elif classification == "gap_probe":
            gap_detected += detected
            gap_outcomes.append(
                f"{row['mutation_id']}:{row['gap_probe_kind']}:"
                f"detected={str(detected).lower()}:blocked={str(blocked).lower()}"
            )
        else:
            clean_blocked += blocked
    return must_killed, gap_detected, clean_blocked, gap_outcomes


def main(argv: Sequence[str] | None = None) -> int:
    """Run selected mutation cases and emit raw records."""

    manifest, payloads = _load_inputs()
    mutation_ids = [str(row["mutation_id"]) for row in manifest]
    parser = argparse.ArgumentParser(
        description="run deterministic named-gate mutation cases"
    )
    parser.add_argument("--mutation", choices=mutation_ids)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    toolchain = load_toolchain()
    commit = git_commit()
    version = plugin_version()
    if version != toolchain["plugin_version"]:
        parser.error("plugin version differs from benchmarks/toolchain.toml")
    selected = [row for row in manifest if args.mutation in (None, row["mutation_id"])]
    random.Random(int(toolchain["seed"])).shuffle(selected)

    if args.out is None:
        stats = _write_records(
            sys.stdout, selected, payloads, toolchain, commit, version
        )
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="\n") as stream:
            stats = _write_records(
                stream, selected, payloads, toolchain, commit, version
            )
    must_killed, gap_detected, clean_blocked, gap_outcomes = stats
    must_total = sum(row["classification"] == "must_block" for row in selected)
    gap_total = sum(row["classification"] == "gap_probe" for row in selected)
    clean_total = sum(row["classification"] == "clean_control" for row in selected)
    print(
        f"must_block_kill_rate={must_killed}/{must_total} "
        f"gap_probe_detection_rate={gap_detected}/{gap_total} "
        f"clean_control_false_blocks={clean_blocked}/{clean_total}",
        file=sys.stderr,
    )
    if gap_outcomes:
        print("gap_probe_outcomes=" + ",".join(sorted(gap_outcomes)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

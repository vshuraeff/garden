"""Deterministic materialization, mutation, hashing, and reversal helpers."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TreeEntry:
    """One captured filesystem entry relative to a mutation target."""

    relative_path: str
    kind: str
    content: bytes
    mode: int


@dataclass(frozen=True)
class MutationState:
    """State required to prove and reverse one applied mutation."""

    target_path: str
    before_sha256: str | None
    after_sha256: str | None
    before_file_sha256: tuple[tuple[str, str], ...]
    after_file_sha256: tuple[tuple[str, str], ...]
    entries: tuple[TreeEntry, ...]


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _entries(path: Path) -> tuple[TreeEntry, ...]:
    if not _lexists(path):
        return ()
    if path.is_symlink():
        return (TreeEntry(".", "symlink", os.readlink(path).encode(), 0o777),)
    if path.is_file():
        return (
            TreeEntry(
                ".",
                "file",
                path.read_bytes(),
                stat.S_IMODE(path.stat().st_mode),
            ),
        )

    entries = [TreeEntry(".", "directory", b"", stat.S_IMODE(path.stat().st_mode))]
    for child in sorted(path.rglob("*")):
        relative = child.relative_to(path).as_posix()
        if child.is_symlink():
            entries.append(
                TreeEntry(relative, "symlink", os.readlink(child).encode(), 0o777)
            )
        elif child.is_dir():
            entries.append(
                TreeEntry(
                    relative,
                    "directory",
                    b"",
                    stat.S_IMODE(child.stat().st_mode),
                )
            )
        else:
            entries.append(
                TreeEntry(
                    relative,
                    "file",
                    child.read_bytes(),
                    stat.S_IMODE(child.stat().st_mode),
                )
            )
    return tuple(entries)


def _hash_entries(entries: tuple[TreeEntry, ...]) -> str | None:
    if not entries:
        return None
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry.relative_path.encode())
        digest.update(b"\0")
        digest.update(entry.kind.encode())
        digest.update(b"\0")
        digest.update(entry.mode.to_bytes(4, "big"))
        digest.update(entry.content)
        digest.update(b"\0")
    return digest.hexdigest()


def _file_hashes(entries: tuple[TreeEntry, ...]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (entry.relative_path, hashlib.sha256(entry.content).hexdigest())
        for entry in entries
        if entry.kind in {"file", "symlink"}
    )


def hash_path(path: Path) -> str | None:
    """Hash one file, symlink, or directory tree deterministically."""

    return _hash_entries(_entries(path))


def materialize_files(root: Path, files: Mapping[str, object]) -> None:
    """Materialize a relative-path mapping under an empty fixture root."""

    for relative, value in sorted(files.items()):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            destination.write_text(value, encoding="utf-8")
        elif isinstance(value, Mapping) and isinstance(value.get("hex"), str):
            destination.write_bytes(bytes.fromhex(value["hex"]))
        else:
            raise TypeError(f"unsupported materialized value for {relative}")


def _remove(path: Path) -> None:
    if not _lexists(path):
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def _write_text(path: Path, content: str) -> None:
    _remove(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _apply_operation(root: Path, operation: Mapping[str, Any]) -> None:
    target = root / str(operation["path"])
    kind = operation["kind"]
    if kind == "write":
        _write_text(target, str(operation["content"]))
    elif kind == "write-bytes-hex":
        _remove(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes.fromhex(str(operation["hex"])))
    elif kind == "delete":
        _remove(target)
    elif kind == "replace":
        content = target.read_text(encoding="utf-8")
        old = str(operation["old"])
        expected_count = int(operation.get("expected_count", 1))
        if content.count(old) != expected_count:
            raise ValueError(
                f"replacement count for {operation['path']} differs from "
                f"{expected_count}"
            )
        target.write_text(content.replace(old, str(operation["new"])), encoding="utf-8")
    elif kind == "append":
        with target.open("a", encoding="utf-8") as handle:
            handle.write(str(operation["content"]))
    elif kind == "repeat":
        _write_text(target, str(operation["content"]) * int(operation["count"]))
    elif kind == "generate-files":
        _remove(target)
        target.mkdir(parents=True)
        count = int(operation["count"])
        prefix = str(operation.get("prefix", "entry"))
        content = str(operation.get("content", ""))
        for index in range(count):
            (target / f"{prefix}-{index:05d}").write_text(content, encoding="utf-8")
    elif kind == "symlink":
        _remove(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(str(operation["link_target"]))
    else:
        raise ValueError(f"unknown mutation operation: {kind}")


def apply_mutation(root: Path, payload: Mapping[str, Any]) -> MutationState:
    """Apply one explicit payload operation and return reversible state."""

    operation = payload.get("operation")
    if not isinstance(operation, Mapping):
        raise TypeError("mutation payload has no operation object")
    target_path = str(operation["path"])
    target = root / target_path
    entries = _entries(target)
    before = _hash_entries(entries)
    before_files = _file_hashes(entries)
    _apply_operation(root, operation)
    after_entries = _entries(target)
    after = _hash_entries(after_entries)
    after_files = _file_hashes(after_entries)
    return MutationState(
        target_path,
        before,
        after,
        before_files,
        after_files,
        entries,
    )


def reverse_mutation(root: Path, state: MutationState) -> None:
    """Restore the exact captured state for an applied mutation."""

    target = root / state.target_path
    _remove(target)
    if not state.entries:
        return
    for entry in sorted(
        state.entries,
        key=lambda item: (item.relative_path.count("/"), item.relative_path),
    ):
        destination = (
            target if entry.relative_path == "." else target / entry.relative_path
        )
        if entry.kind == "directory":
            destination.mkdir(parents=True, exist_ok=True)
            destination.chmod(entry.mode)
        elif entry.kind == "symlink":
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(entry.content.decode())
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(entry.content)
            destination.chmod(entry.mode)


def reversal_is_exact(root: Path, state: MutationState) -> bool:
    """Return whether the target hash matches its pre-mutation value."""

    return hash_path(root / state.target_path) == state.before_sha256

"""Conservative worktree evidence, independent of the coding agent.

This module does NOT modify Git's index or the candidate worktree.
"""
from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from .contract import Contract
from .engine import IMMUTABLE_CONTROL_PATHS
from .git import Change, GitError, git
from .patterns import matches
from .test_identity import preserves_test_identity


MAX_RENAME_BYTES = 16 * 1024 * 1024
MAX_IGNORED_OUTPUT_BYTES = 16 * 1024 * 1024
IGNORED_SCAN_TIMEOUT_SECONDS = 30


def _rooted_regular_file(repo: Path, path: str) -> Path | None:
    """Only read normal files whose resolved paths remain inside the repository.

    Reject symlinks (including symlinked parents escaping the repo). A second
    process can still race this check; we never claim atomic filesystem proof.
    """
    candidate = repo / path
    try:
        if not candidate.resolve().is_relative_to(repo.resolve()):
            return None
        if not stat.S_ISREG(candidate.lstat().st_mode):
            return None
        if candidate.stat().st_size > MAX_RENAME_BYTES:
            return None
    except (OSError, RuntimeError):
        return None
    return candidate


def _file_digest(path: Path) -> str | None:
    try:
        # O_NOFOLLOW prevents following a last-component symlink on Unix.
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                return None
            if os.fstat(descriptor).st_size > MAX_RENAME_BYTES:
                return None
            digest = hashlib.sha256()
            with os.fdopen(descriptor, "rb", closefd=False) as reader:
                content = reader.read()
                digest.update(content.replace(b"\r\n", b"\n"))
            return digest.hexdigest()
        finally:
            os.close(descriptor)
    except OSError:
        return None


def recover_exact_test_moves(
    repo: Path, base_sha: str, contract: Contract, changes: list[Change]
) -> tuple[list[Change], list[dict[str, str]]]:
    """Recover uniquely identifiable, byte-identical, unstaged test renames.

    Git sees an unstaged move as a tracked deletion and a separate untracked
    file. Only canonical, unchanged test content at a NEW allowed test path
    qualifies. Modified, symlinked, ambiguous and duplicate candidate moves
    remain conservative deletions. A recovery is not a semantic test audit.
    """
    sources: dict[str, list[str]] = defaultdict(list)
    destinations: dict[str, list[str]] = defaultdict(list)
    for change in changes:
        if (
            change.operation == "D" and change.before
            and matches(contract.test_paths, change.before)
            and matches(contract.allow, change.before)
        ):
            # The baseline source must be a normal tracked file, not a
            # symlink, submodule, tree, or other Git object type.
            entries = git(repo, "ls-tree", "-z", base_sha, "--", change.before)
            records = [part for part in entries.split(b"\0") if part]
            if len(records) != 1 or b"\t" not in records[0]:
                continue
            metadata, recorded_path = records[0].split(b"\t", 1)
            if recorded_path.decode("utf-8", "surrogateescape") != change.before:
                continue
            if metadata.split(b" ", 1)[0] not in (b"100644", b"100755"):
                continue
            size_output = git(
                repo, "cat-file", "-s", f"{base_sha}:{change.before}"
            )
            if not size_output.endswith(b"\n"):
                continue
            size = size_output[:-1]
            if (
                not size
                or any(byte < ord("0") or byte > ord("9") for byte in size)
                or (len(size) > 1 and size.startswith(b"0"))
            ):
                continue
            limit = str(MAX_RENAME_BYTES).encode("ascii")
            if len(size) > len(limit) or (
                len(size) == len(limit) and size > limit
            ):
                continue
            data = git(repo, "show", f"{base_sha}:{change.before}")
            if len(data) <= MAX_RENAME_BYTES:
                digest = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
                sources[digest].append(change.before)
        elif (
            change.operation == "?" and change.after
            and matches(contract.test_paths, change.after)
            and matches(contract.allow, change.after)
        ):
            file = _rooted_regular_file(repo, change.after)
            if file is not None:
                digest = _file_digest(file)
                if digest is not None:
                    destinations[digest].append(change.after)

    recovered: dict[str, str] = {}
    for digest, old_paths in sources.items():
        new_paths = destinations.get(digest, [])
        if len(old_paths) == 1 and len(new_paths) == 1:
            old, new = old_paths[0], new_paths[0]
            if old != new and preserves_test_identity(old, new):
                recovered[old] = new

    if not recovered:
        return changes, []
    consumed = set(recovered.values())
    result: list[Change] = []
    for change in changes:
        if change.operation == "D" and change.before in recovered:
            result.append(Change("R", change.before, recovered[change.before]))
        elif change.operation == "?" and change.after in consumed:
            continue
        else:
            result.append(change)
    report = [
        {"before": before, "after": after, "method": "exact_content_match"}
        for before, after in sorted(recovered.items())
    ]
    return sorted(result, key=lambda c: (c.after or c.before or "", c.operation)), report


def list_ignored_protected(
    repo: Path, contract: Contract, contract_path: str
) -> tuple[list[str], int]:
    """Opt-in enumeration of ignored, untracked *paths*, not file contents.

    Git's own exclude rules are honored, and no paths are followed or opened.
    This is an existence check, not an attribution of who created the file.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "--others", "--ignored",
             "--exclude-standard", "-z"],
            capture_output=True, timeout=IGNORED_SCAN_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitError("Ignored path enumeration timed out; audit incomplete") from exc
    if proc.returncode != 0:
        raise GitError(
            "Ignored path enumeration failed: " +
            proc.stderr.decode("utf-8", "replace")[:300]
        )
    raw = proc.stdout
    if len(raw) > MAX_IGNORED_OUTPUT_BYTES:
        raise GitError("Ignored path inventory is too large; audit incomplete")
    if raw and not raw.endswith(b"\0"):
        raise GitError("Truncated ignored path inventory")
    protected: list[str] = []
    considered = 0
    for item in raw.split(b"\0"):
        if not item:
            continue
        considered += 1
        path = item.decode("utf-8", "surrogateescape")
        if (
            path == contract_path or matches(IMMUTABLE_CONTROL_PATHS, path)
            or matches(contract.protect, path)
        ):
            protected.append(path)
    return sorted(set(protected)), considered

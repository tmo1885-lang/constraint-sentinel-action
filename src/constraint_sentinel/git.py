"""Read Git changes using NUL-delimited output, never shell interpolation."""
from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    """Git failed or returned ambiguous data; do not silently pass."""


@dataclass(frozen=True)
class Change:
    operation: str
    before: str | None
    after: str | None

    def paths(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(path for path in (self.before, self.after) if path is not None))


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False,
    )
    if result.returncode != 0:
        msg = result.stderr.decode("utf-8", "replace").strip()
        raise GitError(f"git {args[0]} failed: {msg[:600]}")
    return result.stdout


def repository_root(path: Path) -> Path:
    output = git(path.resolve(), "rev-parse", "--show-toplevel")
    return Path(output.decode("utf-8", "surrogateescape").strip()).resolve()


def commit_sha(repo: Path, ref: str) -> str:
    if not ref or "\x00" in ref or ref.startswith("-"):
        raise GitError("Invalid Git ref")
    sha = git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}")
    value = sha.decode("ascii", "strict").strip()
    if len(value) not in (40, 64) or not all(c in "0123456789abcdef" for c in value):
        raise GitError("Git did not return a valid commit")
    return value


def baseline_file(repo: Path, base_sha: str, contract_path: str) -> bytes:
    return git(repo, "show", f"{base_sha}:{contract_path}")


def parse_name_status(data: bytes) -> list[Change]:
    if not data:
        return []
    tokens = data.split(b"\x00")
    if tokens[-1] != b"":
        raise GitError("Truncated NUL-delimited Git diff")
    tokens.pop()
    changes = []
    i = 0
    while i < len(tokens):
        status = tokens[i].decode("ascii", "strict")
        i += 1
        kind = status[:1]
        if kind not in {"A", "C", "D", "M", "R", "T", "U", "X", "B"}:
            raise GitError(f"Unrecognized Git change status: {status!r}")
        need = 2 if kind in {"R", "C"} else 1
        if i + need > len(tokens) or any(not item for item in tokens[i:i + need]):
            raise GitError(f"Malformed entry for Git status {status!r}")
        paths = [p.decode("utf-8", "surrogateescape") for p in tokens[i:i + need]]
        i += need
        if kind in {"R", "C"}:
            changes.append(Change(kind, paths[0], paths[1]))
        elif kind == "D":
            changes.append(Change(kind, paths[0], None))
        else:
            changes.append(Change(kind, None if kind == "A" else paths[0], paths[0]))
    return changes


def collect_changes(repo: Path, base_sha: str, head_sha: str | None) -> list[Change]:
    args = ["diff", "--no-ext-diff", "--name-status", "-z", "--find-renames", "--find-copies", base_sha]
    if head_sha:
        args.append(head_sha)
    changes = parse_name_status(git(repo, *args))
    if head_sha is None:
        unknown = git(repo, "ls-files", "--others", "--exclude-standard", "-z")
        if unknown and not unknown.endswith(b"\x00"):
            raise GitError("Truncated untracked file list")
        for item in unknown.split(b"\x00"):
            if item:
                changes.append(Change("?", None, item.decode("utf-8", "surrogateescape")))
    return sorted(changes, key=lambda change: (change.after or change.before or "", change.operation))


def worktree_fingerprint(repo: Path, base_sha: str) -> str:
    """Fingerprint tracked diffs and nonignored untracked bytes before running tests.

    Used to detect check commands that change the candidate while validating it.
    This is NOT an attestation of the entire filesystem or external systems.
    """
    digest = hashlib.sha256()
    digest.update(b"tracked-git-diff\0")
    digest.update(git(repo, "diff", "--no-ext-diff", "--no-textconv", "--binary", base_sha))
    digest.update(b"untracked-files\0")
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z")
    if untracked and not untracked.endswith(b"\0"):
        raise GitError("Truncated untracked paths")
    for name in sorted(item for item in untracked.split(b"\0") if item):
        path = repo / name.decode("utf-8", "surrogateescape")
        digest.update(name + b"\0")
        try:
            if path.is_symlink():
                digest.update(b"link\0" + os.fsencode(os.readlink(path)))
            elif path.is_file():
                with path.open("rb") as handle:
                    while block := handle.read(1024 * 1024):
                        digest.update(block)
            else:
                raise GitError("Untracked path is neither a regular file nor a symlink")
        except OSError as exc:
            raise GitError(f"Cannot fingerprint untracked path: {path}") from exc
        digest.update(b"\0")
    return digest.hexdigest()


def index_visibility_flags(repo: Path) -> list[tuple[str, str]]:
    """Find tracked paths which Git may conceal from worktree diff.

    Git's assume-unchanged and skip-worktree bits can hide local modifications
    from ordinary git diff output. A post-change verifier must not pass when
    those flags are set: we cannot distinguish an intentionally sparse worktree
    from hidden edits using diff alone.

    The -v format is: one single-character flag, one space, NUL-terminated
    repository path. Lowercase flags indicate assume-unchanged; 'S' indicates
    skip-worktree. This reads the flags without mutating the Git index.
    """
    raw = git(repo, "ls-files", "-v", "-z")
    if raw and not raw.endswith(b"\x00"):
        raise GitError("Truncated Git index visibility output")
    found: list[tuple[str, str]] = []
    for entry in raw.split(b"\x00"):
        if not entry:
            continue
        if len(entry) < 3 or entry[1:2] != b" ":
            raise GitError("Unexpected Git index visibility record")
        tag = entry[:1].decode("ascii", "strict")
        path = entry[2:].decode("utf-8", "surrogateescape")
        if tag not in "HSRCK?hsrck":
            raise GitError(f"Unknown Git index visibility flag {tag!r}")
        if tag.islower() or tag == "S":
            found.append((path, "assume-unchanged" if tag.islower() and tag != "s"
                          else "skip-worktree" if tag == "S"
                          else "assume-unchanged and skip-worktree"))
    return sorted(found)

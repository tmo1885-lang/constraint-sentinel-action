"""Explicit owner-side task authorization with minimal CLI friction.

This helper commits the task contract before agent work. Only call it
from the owner's trusted working copy, never from the coding agent.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from .contract import ContractError, load_contract
from .git import repository_root


DEFAULT_TEST_PATHS = (
    "tests/**",
    "**/test_*.py",
    "**/*.test.js",
    "**/*.spec.ts",
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        reason = result.stderr.decode("utf-8", errors="replace").strip()
        raise ContractError(f"Git authorization failed: {reason}")
    return result.stdout.decode("utf-8", errors="replace").strip()


def approve_task(
    repo_path: Path, *, task_id: str, allow: list[str],
    protect: list[str], test_paths: list[str],
    replace: bool = False,
) -> str:
    """Write and commit exactly one preapproved contract on a clean branch.

    The returned SHA is only trustworthy when the owner retains control of
    this baseline. The command does not push or protect the branch.
    """
    repo = repository_root(repo_path)
    if _git(repo, "status", "--porcelain=v1", "--untracked-files=all", "-z"):
        raise ContractError("Refusing authorization: Git worktree/index is not clean")
    # Require a pre-existing commit; Git's user configuration and hook setup
    # remain the owner's responsibility.
    _git(repo, "rev-parse", "--verify", "HEAD")
    contract_dir = repo / ".sentinel"
    target = contract_dir / "contract.json"
    if contract_dir.is_symlink() or target.is_symlink():
        raise ContractError("Contract path must not be a symlink")
    if target.exists() and not replace:
        raise ContractError("Contract already exists; use --replace to explicitly reauthorize")

    content = {
        "schema_version": 1,
        "task_id": task_id,
        "allow": allow,
        "protect": protect,
        "test_paths": test_paths or list(DEFAULT_TEST_PATHS),
        "deny_test_deletions": True,
        "required_checks": [],
    }
    data = (json.dumps(content, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    load_contract(data)  # Fail closed before touching Git or the filesystem.
    if target.exists() and target.read_bytes() == data:
        # An explicitly repeated, identical approval is a successful no-op.
        return _git(repo, "rev-parse", "--verify", "HEAD")

    contract_dir.mkdir(exist_ok=True)
    # Create atomically so interrupted writes do not leave a partial policy.
    fd, temp_path = tempfile.mkstemp(prefix=".contract-", dir=contract_dir)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temp_path, target)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    _git(repo, "add", "--", ".sentinel/contract.json")
    _git(repo, "commit", "-m", f"Authorize Sentinel task: {task_id}",
         "--only", "--", ".sentinel/contract.json")
    return _git(repo, "rev-parse", "--verify", "HEAD")


PINNED_BETA_SHA = "8f3fb1c8cb7629f24f9d0baefad6ff298e205aa6"

CI_WORKFLOW = """name: Constraint Sentinel scope
on:
  pull_request:

permissions:
  contents: read

jobs:
  sentinel-scope:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          persist-credentials: false
      - name: Verify owner-approved Git task scope
        uses: tmo1885-lang/constraint-sentinel-action@{pinned_sha}
        with:
          base: ${{{{ github.event.pull_request.base.sha }}}}
"""


def setup_ci(repo_path: Path) -> str:
    """One-time owner-side setup: commit a read-only PR scope workflow."""
    repo = repository_root(repo_path)
    if _git(repo, "status", "--porcelain=v1", "--untracked-files=all", "-z"):
        raise ContractError("Refusing CI setup: Git worktree/index is not clean")
    _git(repo, "rev-parse", "--verify", "HEAD")
    folder = repo / ".github" / "workflows"
    path = folder / "sentinel-scope.yml"
    if (repo / ".github").is_symlink() or folder.is_symlink() or path.is_symlink():
        raise ContractError("CI workflow path must not be a symlink")
    if path.exists():
        raise ContractError("Sentinel CI workflow already exists; refusing overwrite")
    folder.mkdir(parents=True, exist_ok=True)
    # No runtime agent data or secrets are interpolated into shell commands.
    data = CI_WORKFLOW.format(pinned_sha=PINNED_BETA_SHA)
    path.write_text(data, encoding="utf-8")
    _git(repo, "add", "--", ".github/workflows/sentinel-scope.yml")
    _git(repo, "commit", "-m", "Install owner-managed Sentinel PR scope check",
         "--only", "--", ".github/workflows/sentinel-scope.yml")
    return _git(repo, "rev-parse", "--verify", "HEAD")

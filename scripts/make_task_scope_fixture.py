"""Generate a disposable task-ledger Action smoke fixture (no credentials)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# This script runs only in the trusted test job, never as candidate code.
from constraint_sentinel.task_ledger import start_task


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], text=True,
        capture_output=True, check=True,
    ).stdout.strip()


def main() -> None:
    destination = Path(sys.argv[1]).resolve()
    if destination.exists():
        raise RuntimeError("Refuse existing fixture directory")
    destination.mkdir(parents=True)
    candidate = destination / "candidate"
    candidate.mkdir()
    git(candidate, "init", "-q")
    git(candidate, "branch", "-M", "main")
    git(candidate, "config", "user.name", "Sentinel smoke owner")
    git(candidate, "config", "user.email", "owner@example.invalid")
    source = candidate / "src" / "cart.py"
    source.parent.mkdir()
    source.write_text("PRICE = 5\n", encoding="utf-8")
    (candidate / "payments.py").write_text("SAFE = True\n", encoding="utf-8")
    git(candidate, "add", ".")
    git(candidate, "commit", "-qm", "Approved repository baseline")
    base, _ = start_task(
        candidate, branch="task/smoke-cart", task_id="action-task-smoke",
        allow=["src/cart.py"], protect=["payments.py"], test_paths=[],
    )
    approved = destination / "trusted-approvals"
    git(candidate, "worktree", "add", "--quiet", "--detach",
        str(approved), "refs/heads/sentinel-approvals")
    source.write_text("PRICE = 6\n", encoding="utf-8")
    git(candidate, "add", "src/cart.py")
    git(candidate, "commit", "-qm", "Authorized agent edit")
    print(f"base={base}")
    print(f"head={git(candidate, 'rev-parse', 'HEAD')}")


if __name__ == "__main__":
    main()

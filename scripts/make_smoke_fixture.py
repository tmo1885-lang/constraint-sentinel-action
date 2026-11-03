"""Create a disposable Git fixture to test the standalone release Action.

Never use this against real repositories: requires a brand-new directory.
Prints the independently approved baseline commit SHA.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    )
    return r.stdout.strip()


def write(repo: Path, name: str, value: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/make_smoke_fixture.py NEW_DIRECTORY")
    repo = Path(sys.argv[1]).resolve()
    repo.mkdir(parents=True, exist_ok=False)
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Synthetic Release Test")
    git(repo, "config", "user.email", "fixture@example.invalid")
    write(repo, "src/cart/calc.py", "def total(a, b):\n    return a + b\n")
    write(repo, "src/payments/gateway.py", "gateway = 'original'\n")
    write(repo, "tests/test_cart.py", "def test_total():\n    assert 2 + 2 == 4\n")
    write(repo, ".gitignore", "src/payments/ignored-fixture.txt\n__pycache__/\n*.pyc\n")
    contract = {
        "schema_version": 1,
        "task_id": "public-beta-synthetic-validation",
        "allow": ["src/cart/**", "tests/**"],
        "protect": ["src/payments/**", "db/migrations/**"],
        "test_paths": ["tests/**"],
        "deny_test_deletions": True,
        "required_checks": [{
            "name": "isolated-fixture-smoke",
            "argv": ["python3", "-c", "print('synthetic fixture smoke passed')"],
            "timeout_seconds": 10,
        }],
    }
    write(repo, ".sentinel/contract.json", json.dumps(contract, indent=2) + "\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Owner-approved synthetic baseline")
    base = git(repo, "rev-parse", "HEAD")
    # Authorized changed source file, not staged.
    write(repo, "src/cart/calc.py", "def total(a, b):\n    return b + a\n")
    print(base)


if __name__ == "__main__":
    main()

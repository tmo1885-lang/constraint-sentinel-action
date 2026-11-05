#!/usr/bin/env python3
"""CS-ADDON-01 synthetic, owner-free fixture creator.

Creates only new disposable Git repositories under the supplied destination.
No network, application secrets, genuine customer data, or live agents.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


CASES = {
    "good": """def test_new_behavior():
    assert sum([2, 3]) == 5
""",
    "undiscovered": """class Feature:
    def test_new_behavior(self):
        assert sum([2, 3]) == 5
""",
    "skipped": """import pytest

@pytest.mark.skip(reason="intentional platform-specific synthetic skip")
def test_new_behavior():
    assert sum([2, 3]) == 5
""",
}


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args],
                            check=True, capture_output=True,
                            text=True, timeout=30)
    return result.stdout.strip()


def make_fixtures(root: Path) -> dict:
    if root.exists():
        raise ValueError("Trial destination must not already exist")
    root.mkdir(parents=True)
    owner = root / "owner"
    owner.mkdir()
    git(owner, "init", "-q", "-b", "main")
    git(owner, "config", "user.name", "CS-ADDON-01 synthetic owner")
    git(owner, "config", "user.email", "synthetic-owner@example.invalid")
    (owner / "README.md").write_text(
        "# Synthetic checkout\n\nOnly test data. No deployment or external effects.\n",
        encoding="utf-8",
    )
    (owner / "tests").mkdir()
    (owner / "tests" / "test_existing.py").write_text(
        "def test_existing_behavior():\n    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )
    git(owner, "add", "--", "README.md", "tests/test_existing.py")
    git(owner, "commit", "-qm", "Frozen synthetic owner baseline")
    base = git(owner, "rev-parse", "HEAD")

    manifest = {"base": base, "cases": {}}
    for name in ("good", "undiscovered", "skipped", "no_new"):
        dest = root / name
        subprocess.run(
            ["git", "clone", "--quiet", "--single-branch", "--branch", "main",
             str(owner), str(dest)],
            check=True, capture_output=True, timeout=30,
        )
        git(dest, "config", "user.name", "CS-ADDON-01 synthetic agent")
        git(dest, "config", "user.email", "synthetic-agent@example.invalid")
        git(dest, "switch", "-q", "-c", "task/" + name)
        if name == "no_new":
            target = dest / "README.md"
            target.write_text(target.read_text(encoding="utf-8")
                              + "\nHarmless documentation-only edit.\n",
                              encoding="utf-8")
            path = "README.md"
        else:
            path = "tests/test_added.py"
            (dest / path).write_text(CASES[name], encoding="utf-8")
        git(dest, "add", "--", path)
        git(dest, "commit", "-qm", "Synthetic " + name + " candidate")
        if git(dest, "status", "--porcelain"):
            raise RuntimeError("Fixture worktree not clean")
        manifest["cases"][name] = {
            "head": git(dest, "rev-parse", "HEAD"),
            "path": str(dest),
            "expected_r2_status": {
                "good": "pass",
                "undiscovered": "fail",
                "skipped": "unverified",
                "no_new": "not_applicable",
            }[name],
        }
    (root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(make_fixtures(args.output.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

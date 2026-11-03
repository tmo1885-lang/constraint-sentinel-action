"""Acceptance tests for an actual coding-agent patch.

The signed-off baseline contains these tests before the agent receives its task.
The agent should only modify src/constraint_sentinel/worktree.py.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from constraint_sentinel.contract import load_contract
from constraint_sentinel.git import collect_changes, git as real_git
from constraint_sentinel.worktree import recover_exact_test_moves


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True,
        capture_output=True, text=True,
    ).stdout.strip()


class OversizedGitBlobTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="sentinel-agent-acceptance-")
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.name", "Acceptance Fixture")
        _git(self.repo, "config", "user.email", "fixture@example.invalid")
        (self.repo / "tests").mkdir()
        self.old = self.repo / "tests/test_original.py"
        self.content = b"def test_a():\n    assert True\n" + b"# filler\n" * 1024
        self.old.write_bytes(self.content)
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-qm", "approved baseline")
        self.sha = _git(self.repo, "rev-parse", "HEAD")
        self.contract = load_contract(json.dumps({
            "schema_version": 1, "task_id": "oversize-move-guard",
            "allow": ["tests/**"], "protect": [],
            "test_paths": ["tests/**"], "deny_test_deletions": True,
            "required_checks": [],
        }).encode("utf-8"))
        self.new = self.repo / "tests/test_renamed.py"
        self.old.rename(self.new)

    def test_reject_oversized_blob_without_reading_git_show(self) -> None:
        changes = collect_changes(self.repo, self.sha, None)
        operations = sorted(c.operation for c in changes)
        self.assertEqual(operations, ["?", "D"])
        inspected_calls: list[str] = []

        def guarded_git(repo: Path, *args: str) -> bytes:
            inspected_calls.append(args[0])
            if args[0] == "show":
                self.fail("Oversized tracked test blob was read before checking size")
            return real_git(repo, *args)

        # The existing implementation loads the entire object and fails here.
        with patch("constraint_sentinel.worktree.MAX_RENAME_BYTES", 128):
            with patch("constraint_sentinel.worktree.git", side_effect=guarded_git):
                evaluated, recovered = recover_exact_test_moves(
                    self.repo, self.sha, self.contract, changes,
                )
        self.assertEqual(recovered, [])
        self.assertEqual(sorted(c.operation for c in evaluated), ["?", "D"])
        self.assertIn("cat-file", inspected_calls)

    def test_malformed_object_size_never_reads_blob(self) -> None:
        changes = collect_changes(self.repo, self.sha, None)
        for value in (b"oops\n", b"-1\n", b"0001\n", b"9999999999999999999\n"):
            with self.subTest(cat_file_output=value):
                def fake_git(repo: Path, *args: str) -> bytes:
                    if args[0] == "cat-file":
                        return value
                    if args[0] == "show":
                        self.fail("Unexpected blob read after invalid size")
                    return real_git(repo, *args)
                with patch("constraint_sentinel.worktree.MAX_RENAME_BYTES", 128):
                    with patch("constraint_sentinel.worktree.git", side_effect=fake_git):
                        evaluated, recovered = recover_exact_test_moves(
                            self.repo, self.sha, self.contract, changes,
                        )
                self.assertEqual(recovered, [])
                self.assertEqual(sorted(x.operation for x in evaluated), ["?", "D"])

    def test_exact_move_below_limit_still_recovers(self) -> None:
        changes = collect_changes(self.repo, self.sha, None)
        with patch("constraint_sentinel.worktree.MAX_RENAME_BYTES", len(self.content)):
            evaluated, recovered = recover_exact_test_moves(
                self.repo, self.sha, self.contract, changes,
            )
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["method"], "exact_content_match")
        self.assertEqual(evaluated[0].operation, "R")


if __name__ == "__main__":
    unittest.main()

"""Black-box owner-side authorization UX and fail-closed behavior."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from constraint_sentinel.cli import main


def git(repo: Path, *argv: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *argv],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, check=True,
    )
    return completed.stdout.strip()


class ApprovalUXTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="cs-ux01-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "UX fixture owner")
        git(self.repo, "config", "user.email", "owner@example.invalid")
        (self.repo / "hello.py").write_text("VALUE = 1\n", encoding="utf-8")
        git(self.repo, "add", "hello.py")
        git(self.repo, "commit", "-qm", "Initial committed repo")
        self.before = git(self.repo, "rev-parse", "HEAD")

    def approve(self, *extra: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main([
                "approve", "--repo", str(self.repo), "--task", "repair-13",
                "--allow", "hello.py", "--protect", "secrets/**", *extra,
            ])
        return code, out.getvalue()

    def setup_ci(self) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["setup", "--repo", str(self.repo)])
        return code, out.getvalue()

    def test_one_time_setup_commits_trusted_pr_workflow(self) -> None:
        code, output = self.setup_ci()
        self.assertEqual(code, 0)
        commit = git(self.repo, "rev-parse", "HEAD")
        self.assertIn(commit, output)
        self.assertEqual(
            git(self.repo, "show", "--pretty=", "--name-only", "HEAD"),
            ".github/workflows/sentinel-scope.yml",
        )
        workflow = (self.repo / ".github/workflows/sentinel-scope.yml").read_text()
        self.assertIn("on:\n  pull_request:", workflow)
        self.assertIn("github.event.pull_request.base.sha", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertIn(
            "@8f3fb1c8cb7629f24f9d0baefad6ff298e205aa6", workflow,
        )
        code, _ = self.approve()
        self.assertEqual(code, 0)
        self.assertNotEqual(commit, git(self.repo, "rev-parse", "HEAD"))

    def test_setup_refuses_dirty_repo_and_existing_workflow(self) -> None:
        (self.repo / "untracked.txt").write_text("not approved", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            code, _ = self.setup_ci()
        self.assertEqual(code, 2)
        self.assertFalse((self.repo / ".github").exists())
        (self.repo / "untracked.txt").unlink()
        code, _ = self.setup_ci()
        self.assertEqual(code, 0)
        first = git(self.repo, "rev-parse", "HEAD")
        with contextlib.redirect_stderr(io.StringIO()):
            code, _ = self.setup_ci()
        self.assertEqual(code, 2)
        self.assertEqual(first, git(self.repo, "rev-parse", "HEAD"))

    def test_approved_base_checks_agent_changes_without_manual_json(self) -> None:
        code, output = self.approve()
        self.assertEqual(code, 0)
        baseline = git(self.repo, "rev-parse", "HEAD")
        self.assertNotEqual(baseline, self.before)
        self.assertIn(baseline, output)
        self.assertEqual(git(self.repo, "show", "--pretty=", "--name-only", "HEAD"),
                         ".sentinel/contract.json")
        policy = json.loads((self.repo / ".sentinel/contract.json").read_text())
        self.assertEqual(policy["allow"], ["hello.py"])
        self.assertEqual(policy["protect"], ["secrets/**"])
        self.assertTrue(policy["deny_test_deletions"])
        (self.repo / "hello.py").write_text("VALUE = 2\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["check", "--repo", str(self.repo),
                                   "--base", baseline]), 0)
        secret = self.repo / "secrets" / "token.txt"
        secret.parent.mkdir()
        secret.write_text("synthetic only", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["check", "--repo", str(self.repo),
                                   "--base", baseline]), 1)

    def test_refuses_dirty_tree_without_modifying_anything(self) -> None:
        (self.repo / "hello.py").write_text("DIRTY\n", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            code, _ = self.approve()
        self.assertEqual(code, 2)
        self.assertFalse((self.repo / ".sentinel").exists())
        self.assertEqual(self.before, git(self.repo, "rev-parse", "HEAD"))

    def test_refuses_existing_contract_without_explicit_replace(self) -> None:
        code, _ = self.approve()
        self.assertEqual(code, 0)
        first = git(self.repo, "rev-parse", "HEAD")
        with contextlib.redirect_stderr(io.StringIO()):
            code, _ = self.approve()
        self.assertEqual(code, 2)
        self.assertEqual(first, git(self.repo, "rev-parse", "HEAD"))
        code, _ = self.approve("--replace")
        self.assertEqual(code, 0)
        self.assertEqual(first, git(self.repo, "rev-parse", "HEAD"),
                         "Identical explicit reapproval should be idempotent")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["approve", "--repo", str(self.repo),
                         "--task", "second-repair", "--allow", "hello.py",
                         "--replace"])
        self.assertEqual(code, 0)
        self.assertNotEqual(first, git(self.repo, "rev-parse", "HEAD"))

    def test_malformed_pattern_does_not_create_policy_or_commit(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            code, _ = self.approve("--allow", "../unsafe/**")
        self.assertEqual(code, 2)
        self.assertFalse((self.repo / ".sentinel").exists())
        self.assertEqual(self.before, git(self.repo, "rev-parse", "HEAD"))

    def test_refuses_staged_other_change(self) -> None:
        (self.repo / "hello.py").write_text("STAGED\n", encoding="utf-8")
        git(self.repo, "add", "hello.py")
        with contextlib.redirect_stderr(io.StringIO()):
            code, _ = self.approve()
        self.assertEqual(code, 2)
        self.assertEqual(self.before, git(self.repo, "rev-parse", "HEAD"))

    def test_rejects_invalid_task_before_filesystem_write(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["approve", "--repo", str(self.repo),
                             "--task", " ", "--allow", "hello.py"])
        self.assertEqual(code, 2)
        self.assertFalse((self.repo / ".sentinel").exists())


if __name__ == "__main__":
    unittest.main()

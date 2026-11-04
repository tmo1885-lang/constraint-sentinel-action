"""CS-UX-02 task-specific approval ledger: real Git operations, no network."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from constraint_sentinel import task_ledger
from constraint_sentinel.cli import main


def git(repo: Path, *args: str) -> str:
    cmd = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True,
        text=True, check=True,
    )
    return cmd.stdout.strip()


class TaskLedgerUXTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="cs-ux02-")
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "branch", "-M", "main")
        git(self.repo, "config", "user.name", "Owner")
        git(self.repo, "config", "user.email", "owner@example.invalid")
        for name in ("alpha.py", "beta.py"):
            (self.repo / name).write_text("x = 1\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "Base")
        self.base = git(self.repo, "rev-parse", "HEAD")

    def start(self, branch: str, allowed: str, *extra: str) -> int:
        with contextlib.redirect_stdout(io.StringIO()):
            return main([
                "task", "start", "--repo", str(self.repo),
                "--branch", branch, "--task", branch,
                "--allow", allowed, *extra,
            ])

    def check(self, *args: str, ref: str = "refs/heads/sentinel-approvals") -> tuple[int, dict]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            status = main([
                "task", "check", "--repo", str(self.repo),
                "--approval-ref", ref, "--format", "json", *args,
            ])
        return status, json.loads(buf.getvalue())

    def test_setup_task_ci_is_one_time_trusted_workflow(self) -> None:
        out = io.StringIO()
        full_sha = "8f3fb1c8cb7629f24f9d0baefad6ff298e205aa6"
        with contextlib.redirect_stdout(out):
            code = main([
                "task", "setup-ci", "--repo", str(self.repo),
                "--checker-sha", full_sha,
            ])
        self.assertEqual(code, 0)
        workflow = (self.repo / ".github/workflows/sentinel-task-scope.yml").read_text()
        self.assertIn("pull_request_target:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("path: candidate", workflow)
        self.assertIn("path: trusted-approvals", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("HEAD_REPOSITORY", workflow)
        self.assertIn("github.event.pull_request.head.ref", workflow)
        self.assertIn("github.event.pull_request.base.sha", workflow)
        self.assertIn(full_sha, workflow)
        self.assertNotIn("--run-checks", workflow)
        self.assertEqual(git(self.repo, "rev-parse", "main"),
                         git(self.repo, "rev-parse", "HEAD"))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([
                "task", "setup-ci", "--repo", str(self.repo),
                "--checker-sha", full_sha,
            ]), 2)

    def test_setup_task_ci_requires_sha_and_clean_repo(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([
                "task", "setup-ci", "--repo", str(self.repo),
                "--checker-sha", "untrusted-main",
            ]), 2)
        self.assertFalse((self.repo / ".github").exists())
        (self.repo / "already.txt").write_text("dirty", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([
                "task", "setup-ci", "--repo", str(self.repo),
                "--checker-sha", "8f3fb1c8cb7629f24f9d0baefad6ff298e205aa6",
            ]), 2)
        self.assertFalse((self.repo / ".github").exists())

    def test_task_start_leaves_main_unchanged_and_check_finds_ledger(self) -> None:
        self.assertEqual(self.start("task/alpha", "alpha.py"), 0)
        self.assertEqual(git(self.repo, "rev-parse", "main"), self.base)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.base)
        self.assertEqual(git(self.repo, "branch", "--show-current"), "task/alpha")
        self.assertFalse((self.repo / ".sentinel").exists())
        (self.repo / "alpha.py").write_text("x = 2\n", encoding="utf-8")
        code, result = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(result["scope"]["violations"], [])
        self.assertEqual(result["approval"]["task_branch"], "task/alpha")
        self.assertEqual(result["base_commit"], self.base)

    def test_different_parallel_tasks_have_independent_approvals(self) -> None:
        self.assertEqual(self.start("task/alpha", "alpha.py"), 0)
        git(self.repo, "switch", "-q", "main")
        self.assertEqual(self.start("task/beta", "beta.py"), 0)
        (self.repo / "beta.py").write_text("x = 2\n", encoding="utf-8")
        code, result = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(result["task_id"], "task/beta")
        git(self.repo, "restore", "--", "beta.py")
        (self.repo / "alpha.py").write_text("x = 2\n", encoding="utf-8")
        code, result = self.check()
        self.assertEqual(code, 1, "Alpha edits cannot use beta approval")
        self.assertEqual(result["scope"]["violations"][0]["rule"], "outside_scope")
        git(self.repo, "restore", "--", "alpha.py")
        git(self.repo, "switch", "-q", "task/alpha")
        (self.repo / "alpha.py").write_text("x = 2\n", encoding="utf-8")
        code, result = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(result["task_id"], "task/alpha")
        self.assertEqual(git(self.repo, "rev-parse", "main"), self.base)

    def test_protected_paths_and_outside_scope_fail(self) -> None:
        self.assertEqual(self.start(
            "task/alpha", "alpha.py", "--protect", "beta.py",
        ), 0)
        (self.repo / "beta.py").write_text("x = 2\n", encoding="utf-8")
        code, result = self.check()
        self.assertEqual(code, 1)
        self.assertIn("protected_path", {v["rule"] for v in result["scope"]["violations"]})

    def test_missing_approval_fail_closed(self) -> None:
        self.assertEqual(self.start("task/alpha", "alpha.py"), 0)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([
                "task", "check", "--repo", str(self.repo),
                "--approval-ref", "refs/heads/does-not-exist",
            ]), 2)

    def test_rejects_wrong_expected_base(self) -> None:
        self.assertEqual(self.start("task/alpha", "alpha.py"), 0)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([
                "task", "check", "--repo", str(self.repo),
                "--approval-ref", "refs/heads/sentinel-approvals",
                "--expected-base", "a" * 40,
            ]), 2)

    def test_dirty_tree_cannot_approve(self) -> None:
        (self.repo / "untracked.txt").write_text("already edited", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.start("task/alpha", "alpha.py"), 2)
        self.assertEqual(git(self.repo, "rev-parse", "main"), self.base)
        result = subprocess.run(
            ["git", "-C", str(self.repo), "show-ref", "--verify",
             "--quiet", "refs/heads/sentinel-approvals"],
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(git(self.repo, "branch", "--show-current"), "main")

    def test_invalid_branch_or_contract_refuses_without_ledger(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.start("task/../../oops", "alpha.py"), 2)
            self.assertEqual(self.start("task/safe", "../invalid/**"), 2)
        self.assertEqual(git(self.repo, "branch", "--list", "task/*"), "")
        self.assertEqual(self.base, git(self.repo, "rev-parse", "HEAD"))

    def test_duplicate_task_approval_refused(self) -> None:
        self.assertEqual(self.start("task/alpha", "alpha.py"), 0)
        git(self.repo, "switch", "-q", "main")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.start("task/alpha", "alpha.py"), 2)
        self.assertEqual(git(self.repo, "branch", "--show-current"), "main")

    def test_failed_publish_removes_new_approval_and_allows_retry(self) -> None:
        self.assertEqual(git(self.repo, "remote"), "")
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            self.assertEqual(self.start("task/alpha", "alpha.py", "--publish"), 2)
        self.assertIn("origin", errors.getvalue())
        self.assertEqual(git(self.repo, "branch", "--list", "task/*"), "")
        self.assertEqual(git(self.repo, "branch", "--show-current"), "main")
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.base)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(git(self.repo, "for-each-ref", "--format=%(refname)",
                             task_ledger.APPROVAL_REF), "")
        self.assertEqual(self.start("task/alpha", "alpha.py"), 0)
        code, result = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(result["task_id"], "task/alpha")

    def test_failed_publish_restores_existing_approval_and_allows_retry(self) -> None:
        self.assertEqual(self.start("task/alpha", "alpha.py"), 0)
        previous = git(self.repo, "rev-parse", task_ledger.APPROVAL_REF)
        previous_tree = git(self.repo, "ls-tree", "-r", previous)
        git(self.repo, "switch", "-q", "main")
        self.assertEqual(git(self.repo, "remote"), "")
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            self.assertEqual(self.start("task/beta", "beta.py", "--publish"), 2)
        self.assertIn("origin", errors.getvalue())
        self.assertEqual(git(self.repo, "branch", "--list", "task/beta"), "")
        self.assertEqual(git(self.repo, "branch", "--show-current"), "main")
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.base)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(git(self.repo, "rev-parse", task_ledger.APPROVAL_REF), previous)
        self.assertEqual(git(self.repo, "ls-tree", "-r", task_ledger.APPROVAL_REF),
                         previous_tree)
        self.assertEqual(self.start("task/beta", "beta.py"), 0)
        self.assertEqual(git(self.repo, "rev-parse", f"{task_ledger.APPROVAL_REF}^"),
                         previous)
        code, result = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(result["task_id"], "task/beta")
        git(self.repo, "switch", "-q", "task/alpha")
        code, result = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(result["task_id"], "task/alpha")

    def test_failed_publish_does_not_rewind_concurrent_approval(self) -> None:
        self.assert_failed_publish_preserves_concurrent_approval()

    def test_failed_publish_does_not_rewind_concurrent_existing_approval(self) -> None:
        self.assertEqual(self.start("task/alpha", "alpha.py"), 0)
        git(self.repo, "switch", "-q", "main")
        self.assert_failed_publish_preserves_concurrent_approval()

    def assert_failed_publish_preserves_concurrent_approval(self) -> None:
        real_git = task_ledger._git
        concurrent = None

        def advance_before_push(repo: Path, *args: str, **kwargs: bool) -> str | None:
            nonlocal concurrent
            if args[0] == "push":
                approved = git(repo, "rev-parse", task_ledger.APPROVAL_REF)
                tree = git(repo, "rev-parse", f"{approved}^{{tree}}")
                concurrent = git(repo, "commit-tree", tree, "-p", approved,
                                 "-m", "Concurrent owner approval")
                git(repo, "update-ref", task_ledger.APPROVAL_REF, concurrent, approved)
            return real_git(repo, *args, **kwargs)

        errors = io.StringIO()
        self.assertEqual(git(self.repo, "remote"), "")
        with mock.patch.object(task_ledger, "_git", side_effect=advance_before_push):
            with contextlib.redirect_stderr(errors):
                self.assertEqual(self.start("task/beta", "beta.py", "--publish"), 2)
        self.assertIsNotNone(concurrent)
        self.assertEqual(git(self.repo, "rev-parse", task_ledger.APPROVAL_REF), concurrent)
        self.assertIn("origin", errors.getvalue())
        self.assertIn("rollback failed", errors.getvalue())
        self.assertEqual(git(self.repo, "branch", "--list", "task/beta"), "")
        self.assertEqual(git(self.repo, "branch", "--show-current"), "main")

    def test_worktree_contract_cannot_change_approved_scope(self) -> None:
        self.assertEqual(self.start("task/alpha", "alpha.py"), 0)
        policy = self.repo / ".sentinel" / "contract.json"
        policy.parent.mkdir()
        policy.write_text(
            json.dumps({"schema_version":1,"task_id":"evil","allow":["**"],
                        "protect":[],"test_paths":["tests/**"],
                        "deny_test_deletions":True,"required_checks":[]}),
            encoding="utf-8",
        )
        code, result = self.check()
        self.assertEqual(code, 1)
        self.assertIn("protected_control", {v["rule"] for v in result["scope"]["violations"]})

    def test_external_owner_checkout_defeats_candidate_local_ref_tamper(self) -> None:
        self.assertEqual(self.start("task/alpha", "alpha.py"), 0)
        candidate = self.repo.parent / "candidate"
        git(self.repo, "switch", "-q", "main")
        git(self.repo, "branch", "-D", "task/alpha")
        git(self.repo, "switch", "-q", "main")
        git(self.repo, "branch", "task/alpha", self.base)
        git(self.repo, "clone", "--local", "--quiet", str(self.repo), str(candidate))
        git(candidate, "config", "user.name", "Agent")
        git(candidate, "config", "user.email", "agent@example.invalid")
        git(candidate, "switch", "-q", "-c", "task/alpha", "origin/task/alpha")
        (candidate / "beta.py").write_text("x = 2\n", encoding="utf-8")
        # Candidate may rewrite its own local tracking ref; trusted owner
        # checkout is resolved separately instead of using that ref.
        git(candidate, "update-ref", "refs/remotes/origin/sentinel-approvals", self.base)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = main([
                "task", "check", "--repo", str(candidate),
                "--approval-repo", str(self.repo),
                "--approval-ref", "refs/heads/sentinel-approvals",
                "--expected-base", self.base,
                "--expected-base-branch", "main",
                "--format", "json",
            ])
        self.assertEqual(rc, 1)
        data = json.loads(out.getvalue())
        self.assertEqual(data["approval"]["approval_source"], "separate_checkout")
        self.assertIn("outside_scope",
                      {v["rule"] for v in data["scope"]["violations"]})

    def test_expected_base_branch_mismatch_fails_closed(self) -> None:
        self.assertEqual(self.start("task/alpha", "alpha.py"), 0)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([
                "task", "check", "--repo", str(self.repo),
                "--approval-ref", "refs/heads/sentinel-approvals",
                "--expected-base-branch", "production",
            ]), 2)

    def test_commit_only_head_mode_still_uses_owner_ledger(self) -> None:
        self.assertEqual(self.start("task/alpha", "alpha.py"), 0)
        (self.repo / "alpha.py").write_text("x = 2\n", encoding="utf-8")
        git(self.repo, "add", "alpha.py")
        git(self.repo, "commit", "-qm", "Legit edit")
        code, result = self.check("--head", "HEAD", "--expected-base", self.base)
        self.assertEqual(code, 0)
        self.assertEqual(result["mode"], "commit_compare")
        self.assertEqual(result["head_commit"], git(self.repo, "rev-parse", "HEAD"))


if __name__ == "__main__":
    unittest.main()

"""Black-box tests using real disposable Git repositories; no network access."""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from constraint_sentinel.cli import main
from constraint_sentinel.contract import ContractError, load_contract
from constraint_sentinel.git import GitError, parse_name_status
from constraint_sentinel.patterns import compile_pattern, matches, validate_pattern


def run_git(repo: Path, *args: str) -> str:
    command = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True,
    )
    return command.stdout.strip()


def write(repo: Path, name: str, content: str) -> None:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def example_contract(**updates: object) -> dict:
    contract = {
        "schema_version": 1,
        "task_id": "cart-fix",
        "allow": ["src/cart/**", "tests/cart/**"],
        "protect": ["src/payments/**", "db/migrations/**"],
        "test_paths": ["tests/**", "**/test_*.py"],
        "deny_test_deletions": True,
        "required_checks": [],
    }
    contract.update(updates)
    return contract


class RealRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="sentinel-test-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q")
        run_git(self.repo, "config", "user.name", "Sentinel test fixture")
        run_git(self.repo, "config", "user.email", "fixture@example.invalid")
        write(self.repo, "src/cart/calc.py", "price = 100\n")
        write(self.repo, "src/payments/gateway.py", "mode = 'safe'\n")
        write(self.repo, "tests/cart/test_calc.py", "assert 1 + 1 == 2\n")
        write(self.repo, ".github/workflows/ci.yml", "name: checks\n")
        self.contract = example_contract()
        self.save_contract()
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "trusted baseline")
        self.base = run_git(self.repo, "rev-parse", "HEAD")

    def save_contract(self) -> None:
        write(self.repo, ".sentinel/contract.json", json.dumps(self.contract) + "\n")

    def check(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["check", "--repo", str(self.repo), "--base", self.base,
                         "--format", "json", *args])
        self.assertFalse(err.getvalue(), err.getvalue())
        return code, json.loads(out.getvalue())

    def test_allowed_change_passes(self) -> None:
        write(self.repo, "src/cart/calc.py", "price = 102\n")
        code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["coverage"]["pre_execution_blocking"], "not_provided")
        self.assertEqual(report["coverage"]["required_check_executable_integrity"],
                         "not_configured")
        self.assertEqual(len(report["scope"]["files"]), 1)

    def test_protected_payment_change_is_blocked(self) -> None:
        write(self.repo, "src/payments/gateway.py", "mode = 'unsafe'\n")
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertIn("protected_path", {v["rule"] for v in report["scope"]["violations"]})

    def test_assume_unchanged_cannot_hide_protected_write(self) -> None:
        write(self.repo, "src/payments/gateway.py", "mode = 'unsafe'\n")
        run_git(self.repo, "update-index", "--assume-unchanged", "src/payments/gateway.py")
        self.assertEqual(run_git(self.repo, "diff", "--name-only", "HEAD"), "")
        code, report = self.check()
        self.assertEqual(code, 1)
        findings = report["scope"]["violations"]
        self.assertIn(("git_index_visibility", "src/payments/gateway.py"),
                      {(v["rule"], v["path"]) for v in findings})

    def test_skip_worktree_cannot_hide_deleted_test(self) -> None:
        run_git(self.repo, "update-index", "--skip-worktree", "tests/cart/test_calc.py")
        (self.repo / "tests/cart/test_calc.py").unlink()
        code, report = self.check()
        self.assertEqual(code, 1)
        findings = report["scope"]["violations"]
        self.assertIn(("git_index_visibility", "tests/cart/test_calc.py"),
                      {(v["rule"], v["path"]) for v in findings})

    def test_git_index_visibility_is_worktree_only(self) -> None:
        run_git(self.repo, "update-index", "--assume-unchanged", "src/payments/gateway.py")
        code, report = self.check("--head", "HEAD")
        self.assertEqual(code, 0)
        self.assertEqual(report["mode"], "commit_compare")

    def test_out_of_scope_change_is_blocked(self) -> None:
        write(self.repo, "docs/notes.md", "not approved\n")
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(report["scope"]["violations"][0]["rule"], "outside_scope")

    def test_test_deletion_is_blocked_even_when_allowed(self) -> None:
        (self.repo / "tests/cart/test_calc.py").unlink()
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertIn("test_removed", {v["rule"] for v in report["scope"]["violations"]})

    def test_negative_control_weakened_test_is_not_semantically_detected(self) -> None:
        # This intentionally records a coverage gap; a path-only verifier
        # cannot know if test assertions were weakened in place.
        write(self.repo, "tests/cart/test_calc.py", "assert True\n")
        code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(report["coverage"]["semantic_intent"], "not_verified")

    def test_negative_control_git_ignored_files_are_not_audited(self) -> None:
        # Git's own exclude file is outside worktree diff, and the tool
        # must NOT claim to have checked ignored untracked paths.
        exclude = self.repo / ".git/info/exclude"
        exclude.write_text("src/payments/new-secret.json\n", encoding="utf-8")
        write(self.repo, "src/payments/new-secret.json", "local-fixture-only\n")
        code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(
            report["coverage"]["git_changes"], "tracked_and_untracked_nonignored_worktree"
        )

    def test_unstaged_test_rename_with_identical_content_is_allowed(self) -> None:
        (self.repo / "tests/cart/test_calc.py").rename(
            self.repo / "tests/cart/test_math.py"
        )
        code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(report["scope"]["status"], "pass")
        self.assertEqual(report["scope"]["files"][0]["operation"], "R")
        self.assertEqual(report["scope"]["recovered_renames"], [{
            "before": "tests/cart/test_calc.py",
            "after": "tests/cart/test_math.py",
            "method": "exact_content_match",
        }])

    def test_unstaged_test_rename_with_modified_contents_remains_flagged(self) -> None:
        (self.repo / "tests/cart/test_calc.py").unlink()
        write(self.repo, "tests/cart/test_math.py", "assert True\n")
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertIn("test_removed", {v["rule"] for v in report["scope"]["violations"]})

    def test_two_identical_unstaged_moves_fail_conservatively(self) -> None:
        write(self.repo, "tests/cart/test_a.py", "assert True\n")
        write(self.repo, "tests/cart/test_b.py", "assert True\n")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "add duplicate tests")
        self.base = run_git(self.repo, "rev-parse", "HEAD")
        (self.repo / "tests/cart/test_a.py").unlink()
        (self.repo / "tests/cart/test_b.py").unlink()
        write(self.repo, "tests/cart/test_c.py", "assert True\n")
        write(self.repo, "tests/cart/test_d.py", "assert True\n")
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertIn("test_removed", {v["rule"] for v in report["scope"]["violations"]})
        self.assertEqual(report["scope"]["recovered_renames"], [])

    def test_ignored_protected_file_audit_is_opt_in(self) -> None:
        (self.repo / ".git/info/exclude").write_text(
            "src/payments/new-secret.json\n", encoding="utf-8"
        )
        write(self.repo, "src/payments/new-secret.json", "synthetic\n")
        code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(report["coverage"]["ignored_untracked_paths"], "not_audited")
        code, report = self.check("--audit-ignored-protected")
        self.assertEqual(code, 1)
        self.assertEqual(report["coverage"]["ignored_untracked_paths"], "audited")
        self.assertIn(("ignored_protected_path", "src/payments/new-secret.json"),
                      {(v["rule"], v["path"]) for v in report["scope"]["violations"]})

    def test_ignored_protected_directory_audit(self) -> None:
        (self.repo / ".git/info/exclude").write_text(
            "src/payments/internal/\n", encoding="utf-8"
        )
        write(self.repo, "src/payments/internal/nested/new.txt", "synthetic\n")
        code, report = self.check("--audit-ignored-protected")
        self.assertEqual(code, 1)
        self.assertIn("src/payments/internal/nested/new.txt",
                      {v["path"] for v in report["scope"]["violations"]})

    def test_ignored_allowed_files_do_not_block_opt_in_audit(self) -> None:
        (self.repo / ".git/info/exclude").write_text(
            "src/cart/cache.json\n", encoding="utf-8"
        )
        write(self.repo, "src/cart/cache.json", "{}\n")
        code, report = self.check("--audit-ignored-protected")
        self.assertEqual(code, 0)
        self.assertEqual(report["coverage"]["ignored_untracked_paths"], "audited")

    def test_task_completion_remains_unverified_on_scope_pass(self) -> None:
        write(self.repo, "src/cart/calc.py", "total = 101\n")
        code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(report["scope"]["status"], "pass")
        self.assertEqual(report["task_completion"]["status"], "not_verified")
        self.assertEqual(report["checks"]["status"], "not_configured")

    def test_ignored_audit_reports_incomplete_on_inventory_limit(self) -> None:
        from unittest.mock import patch
        (self.repo / ".git/info/exclude").write_text(
            "src/payments/very-long-ignored-filename.json\n", encoding="utf-8"
        )
        write(self.repo, "src/payments/very-long-ignored-filename.json", "fixture\n")
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("constraint_sentinel.worktree.MAX_IGNORED_OUTPUT_BYTES", 8):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main([
                    "check", "--repo", str(self.repo), "--base", self.base,
                    "--audit-ignored-protected",
                ])
        self.assertEqual(code, 2)
        self.assertIn("audit incomplete", stderr.getvalue())

    def test_audit_ignored_is_not_available_for_commit_comparison(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main([
                "check", "--repo", str(self.repo), "--base", self.base,
                "--head", "HEAD", "--audit-ignored-protected",
            ])
        self.assertEqual(code, 2)
        self.assertIn("worktree", stderr.getvalue())

    def test_baseline_test_symlink_cannot_masquerade_as_regular_test_move(self) -> None:
        test = self.repo / "tests/cart/test_calc.py"
        test.unlink()
        test.symlink_to("fixture-target.txt")
        run_git(self.repo, "add", "-A")
        run_git(self.repo, "commit", "-qm", "tracked test symlink fixture")
        self.base = run_git(self.repo, "rev-parse", "HEAD")
        test.unlink()
        write(self.repo, "tests/cart/test_new.py", "fixture-target.txt")
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertIn("test_removed", {v["rule"] for v in report["scope"]["violations"]})
        self.assertEqual(report["scope"]["recovered_renames"], [])

    def test_staged_test_rename_to_helper_is_still_blocked(self) -> None:
        (self.repo / "tests/cart/test_calc.py").rename(self.repo / "tests/cart/helper.py")
        run_git(self.repo, "add", "-A")
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertIn("test_removed", {v["rule"] for v in report["scope"]["violations"]})

    def test_test_move_into_protected_path_is_still_blocked(self) -> None:
        (self.repo / "tests/cart/test_calc.py").rename(
            self.repo / "src/payments/test_calc.py"
        )
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertIn("protected_path", {v["rule"] for v in report["scope"]["violations"]})

    def test_ignored_protected_path_from_required_check_is_detected(self) -> None:
        (self.repo / ".git/info/exclude").write_text(
            "src/payments/fixture.json\n", encoding="utf-8"
        )
        self.contract["required_checks"] = [{
            "name": "synthetic-test-runner",
            "argv": [sys.executable, "-c",
                     "from pathlib import Path; Path('src/payments/fixture.json').write_text('fixture')"],
            "timeout_seconds": 2,
        }]
        self.save_contract()
        run_git(self.repo, "add", ".sentinel/contract.json")
        run_git(self.repo, "commit", "-qm", "trusted policy amendment")
        self.base = run_git(self.repo, "rev-parse", "HEAD")
        code, report = self.check("--audit-ignored-protected", "--run-checks")
        self.assertEqual(code, 1)
        self.assertIn("ignored_protected_path",
                      {v["rule"] for v in report["scope"]["violations"]})
        self.assertIn("validation_changed_worktree",
                      {v["rule"] for v in report["scope"]["violations"]})
        self.assertEqual(report["checks"]["status"], "pass")
        self.assertEqual(report["task_completion"]["status"], "not_verified")

    def test_ignored_nonprotected_paths_are_not_false_positives(self) -> None:
        (self.repo / ".git/info/exclude").write_text(
            "src/cart/tmp/\n", encoding="utf-8"
        )
        write(self.repo, "src/cart/tmp/cache.json", "fixture\n")
        code, report = self.check("--audit-ignored-protected")
        self.assertEqual(code, 0)
        self.assertEqual(report["scope"]["ignored_protected_paths"], [])

    def test_test_rename_to_nontest_is_blocked(self) -> None:
        target = self.repo / "tests/cart/helper.py"
        (self.repo / "tests/cart/test_calc.py").rename(target)
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertIn("test_removed", {v["rule"] for v in report["scope"]["violations"]})

    def test_move_test_to_another_test_path_is_allowed(self) -> None:
        (self.repo / "tests/cart/test_calc.py").rename(self.repo / "tests/cart/test_math.py")
        # Git only recognizes this as a rename after staging; otherwise it sees
        # a tracked deletion and a separate untracked addition.
        run_git(self.repo, "add", "-A")
        code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(report["scope"]["status"], "pass")

    def test_rename_into_protected_area_is_blocked(self) -> None:
        (self.repo / "src/cart/calc.py").rename(self.repo / "src/payments/calculation.py")
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertIn("protected_path", {v["rule"] for v in report["scope"]["violations"]})

    def test_contract_edit_cannot_self_authorize(self) -> None:
        self.contract["allow"] = ["**"]
        self.contract["protect"] = []
        self.save_contract()
        write(self.repo, "src/payments/gateway.py", "mode = 'unsafe'\n")
        code, report = self.check()
        self.assertEqual(code, 1)
        rules = {v["rule"] for v in report["scope"]["violations"]}
        self.assertIn("protected_control", rules)
        self.assertIn("protected_path", rules)
        raw_base = run_git(self.repo, "show", self.base + ":.sentinel/contract.json")
        self.assertEqual(report["contract_sha256"], __import__("hashlib").sha256((raw_base + "\n").encode()).hexdigest())

    def test_ci_workflow_changes_are_protected(self) -> None:
        write(self.repo, ".github/workflows/ci.yml", "name: disabled\n")
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertIn("protected_control", {v["rule"] for v in report["scope"]["violations"]})

    def test_untracked_allowed_file_is_checked(self) -> None:
        write(self.repo, "src/cart/new.py", "x = 1\n")
        code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(report["scope"]["files"][0]["operation"], "?")

    def test_untracked_outside_file_is_checked(self) -> None:
        write(self.repo, "notes.txt", "surprise\n")
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(report["scope"]["violations"][0]["rule"], "outside_scope")

    def test_space_and_unicode_paths(self) -> None:
        write(self.repo, "src/cart/résumé and notes.py", "ok = True\n")
        code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(report["scope"]["files"][0]["after"], "src/cart/résumé and notes.py")

    def test_newline_in_filename_is_not_parsed_as_two_files(self) -> None:
        write(self.repo, "src/cart/line\nbreak.py", "ok = True\n")
        code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(len(report["scope"]["files"]), 1)

    def test_scope_comparison_between_commits(self) -> None:
        write(self.repo, "src/cart/calc.py", "price = 300\n")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "candidate")
        code, report = self.check("--head", "HEAD")
        self.assertEqual(code, 0)
        self.assertEqual(report["mode"], "commit_compare")
        self.assertEqual(report["coverage"]["git_changes"], "tracked_commits")

    def test_required_check_unexecuted_does_not_pass(self) -> None:
        self.contract["required_checks"] = [{
            "name": "smoke", "argv": [sys.executable, "-c", "print('ok')"],
            "timeout_seconds": 2,
        }]
        self.save_contract()
        run_git(self.repo, "add", ".sentinel/contract.json")
        run_git(self.repo, "commit", "-qm", "trusted policy amendment")
        self.base = run_git(self.repo, "rev-parse", "HEAD")
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(report["checks"]["status"], "not_run")
        code, report = self.check("--run-checks")
        self.assertEqual(code, 0)
        self.assertEqual(report["checks"]["status"], "pass")
        self.assertNotIn("output_tail", report["checks"]["results"][0])

    def test_required_check_mutating_candidate_fails(self) -> None:
        self.contract["required_checks"] = [{
            "name": "mutating-check",
            "argv": [sys.executable, "-c",
                     "from pathlib import Path; Path('src/cart/calc.py').write_text('price = 987')"],
            "timeout_seconds": 2,
        }]
        self.save_contract()
        run_git(self.repo, "add", ".sentinel/contract.json")
        run_git(self.repo, "commit", "-qm", "trusted policy amendment")
        self.base = run_git(self.repo, "rev-parse", "HEAD")
        code, report = self.check("--run-checks")
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "fail")
        self.assertIn("validation_changed_worktree",
                      {v["rule"] for v in report["scope"]["violations"]})

    def _approve_structured_check(self, payload: dict, exit_code: int = 0) -> None:
        script = (
            "import json; print(json.dumps(" + repr(payload) + ")); "
            "raise SystemExit(" + str(exit_code) + ")"
        )
        self.contract["required_checks"] = [{
            "name": "test-integrity",
            "argv": [sys.executable, "-c", script],
            "timeout_seconds": 3,
            "report_format": "proof_of_done_v0",
        }]
        self.save_contract()
        run_git(self.repo, "add", ".sentinel/contract.json")
        run_git(self.repo, "commit", "-qm", "approve external check")
        self.base = run_git(self.repo, "rev-parse", "HEAD")

    def test_external_test_integrity_flags_weakened_test(self) -> None:
        self._approve_structured_check({
            "verdict": "FAIL", "filesChecked": 1,
            "findings": [{
                "ruleId": "POD005", "severity": "block",
                "file": "tests/cart/test_calc.py",
                "message": "This should not leak to a public report",
                "agentHint": "Sensitive sample text",
            }],
        }, exit_code=1)
        write(self.repo, "tests/cart/test_calc.py", "assert True\n")
        code, report = self.check("--run-checks")
        self.assertEqual(code, 1)
        self.assertEqual(report["scope"]["status"], "pass")
        self.assertEqual(report["checks"]["status"], "fail")
        self.assertEqual(report["coverage"]["required_check_executable_integrity"],
                         "not_attested")
        self.assertEqual(report["checks"]["results"][0]["summary"]["verdict"], "FAIL")
        self.assertEqual(
            report["checks"]["results"][0]["summary"]["findings"][0],
            {"rule_id": "POD005", "severity": "block", "path": "tests/cart/test_calc.py"},
        )
        self.assertNotIn("Sensitive sample text", json.dumps(report))
        self.assertEqual(report["task_completion"]["status"], "not_verified")

    def test_checker_output_is_not_an_authenticity_proof(self) -> None:
        # This is a deliberately documented negative control. A compromised
        # external checker can forge a consistent PASS; Sentinel cannot
        # authenticate executable integrity in v0.1.dev3.
        self._approve_structured_check({
            "verdict": "PASS", "filesChecked": 1, "findings": [],
        })
        write(self.repo, "tests/cart/test_calc.py", "assert True\n")
        code, report = self.check("--run-checks")
        self.assertEqual(code, 0)
        self.assertEqual(report["scope"]["status"], "pass")
        self.assertEqual(report["checks"]["status"], "pass")
        self.assertEqual(
            report["coverage"]["required_check_executable_integrity"],
            "not_attested",
        )
        self.assertEqual(report["task_completion"]["status"], "not_verified")

    def test_external_warning_is_disclosed_without_blocking(self) -> None:
        self._approve_structured_check({
            "verdict": "SUSPICIOUS", "filesChecked": 1,
            "findings": [{
                "ruleId": "POD004", "severity": "warn",
                "file": "tests/cart/test_calc.py",
            }],
        })
        code, report = self.check("--run-checks")
        self.assertEqual(code, 0)
        self.assertEqual(report["checks"]["status"], "pass_with_warnings")
        self.assertEqual(report["checks"]["results"][0]["status"], "warning")
        self.assertEqual(report["task_completion"]["status"], "not_verified")

    def test_invalid_external_json_fails_closed(self) -> None:
        self.contract["required_checks"] = [{
            "name": "test-integrity",
            "argv": [sys.executable, "-c", "print('not-json')"],
            "timeout_seconds": 3, "report_format": "proof_of_done_v0",
        }]
        self.save_contract()
        run_git(self.repo, "add", ".sentinel/contract.json")
        run_git(self.repo, "commit", "-qm", "approve check")
        self.base = run_git(self.repo, "rev-parse", "HEAD")
        code, report = self.check("--run-checks")
        self.assertEqual(code, 1)
        self.assertEqual(report["checks"]["results"][0]["status"], "error")
        self.assertIn("invalid JSON", report["checks"]["results"][0]["reason"])

    def test_structured_external_exit_verdict_mismatch_fails_closed(self) -> None:
        self._approve_structured_check({
            "verdict": "FAIL", "filesChecked": 1,
            "findings": [{"ruleId": "POD005", "severity": "block", "file": "tests/test_calc.py"}],
        }, exit_code=0)
        code, report = self.check("--run-checks")
        self.assertEqual(code, 1)
        self.assertEqual(report["checks"]["results"][0]["status"], "error")
        self.assertIn("does not match", report["checks"]["results"][0]["reason"])

    def test_trusted_check_expands_exact_base_commit_argument(self) -> None:
        self.contract["required_checks"] = [{
            "name": "trusted-baseline",
            "argv": [
                sys.executable, "-c",
                "import re,sys; assert re.fullmatch(r'[0-9a-f]{40,64}', sys.argv[1]); "
                "assert sys.argv[2] == 'END'",
                "{base_commit}", "END",
            ],
            "timeout_seconds": 3,
        }]
        self.save_contract()
        run_git(self.repo, "add", ".sentinel/contract.json")
        run_git(self.repo, "commit", "-qm", "approve base placeholder")
        self.base = run_git(self.repo, "rev-parse", "HEAD")
        code, report = self.check("--run-checks")
        self.assertEqual(code, 0)
        self.assertEqual(report["base_commit"], self.base)
        self.assertEqual(report["checks"]["status"], "pass")

    def test_failing_required_check_fails(self) -> None:
        self.contract["required_checks"] = [{
            "name": "smoke", "argv": [sys.executable, "-c", "raise SystemExit(7)"],
            "timeout_seconds": 2,
        }]
        self.save_contract()
        run_git(self.repo, "add", ".sentinel/contract.json")
        run_git(self.repo, "commit", "-qm", "trusted policy amendment")
        self.base = run_git(self.repo, "rev-parse", "HEAD")
        code, report = self.check("--run-checks")
        self.assertEqual(code, 1)
        self.assertEqual(report["checks"]["status"], "fail")
        self.assertEqual(report["checks"]["results"][0]["exit_code"], 7)

    def test_scope_failure_skips_check_execution(self) -> None:
        self.contract["required_checks"] = [{
            "name": "unsafe-command", "argv": [sys.executable, "-c",
                "open('should-not-exist','w').write('bad')"],
            "timeout_seconds": 2,
        }]
        self.save_contract()
        run_git(self.repo, "add", ".sentinel/contract.json")
        run_git(self.repo, "commit", "-qm", "trusted policy amendment")
        self.base = run_git(self.repo, "rev-parse", "HEAD")
        write(self.repo, "src/payments/gateway.py", "modified\n")
        code, report = self.check("--run-checks")
        self.assertEqual(code, 1)
        self.assertEqual(report["checks"]["status"], "skipped_due_to_scope_failure")
        self.assertFalse((self.repo / "should-not-exist").exists())

    def test_report_written_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as outdir:
            report_path = Path(outdir) / "audit.json"
            code, report = self.check("--report", str(report_path))
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(report_path.read_text()), report)

    def test_init_refuses_to_overwrite(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["init", "--repo", str(self.repo)])
        self.assertEqual(code, 2)
        self.assertIn("overwrite", err.getvalue())

    def test_head_with_checks_is_rejected(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["check", "--repo", str(self.repo),
                         "--base", self.base, "--head", "HEAD", "--run-checks"])
        self.assertEqual(code, 2)
        self.assertIn("worktree", err.getvalue())


class ContractValidationTests(unittest.TestCase):
    def test_unknown_field_fails_closed(self) -> None:
        data = example_contract()
        data["permisison_override"] = True
        with self.assertRaises(ContractError):
            load_contract(json.dumps(data).encode())

    def test_empty_allowlist_fails_closed(self) -> None:
        data = example_contract(allow=[])
        with self.assertRaises(ContractError):
            load_contract(json.dumps(data).encode())

    def test_duplicate_contract_keys_fail_closed(self) -> None:
        # JSON syntax permits duplicate keys in some parsers, but the policy
        # must not have two conflicting interpretations.
        raw = (b'{"schema_version":1,"task_id":"reviewed",'
               b'"allow":["src/cart/**"],"allow":["**"],'
               b'"test_paths":["tests/**"]}')
        with self.assertRaisesRegex(ContractError, "Duplicate"):
            load_contract(raw)

    def test_missing_test_patterns_cannot_claim_test_preservation(self) -> None:
        data = example_contract(test_paths=[])
        with self.assertRaises(ContractError):
            load_contract(json.dumps(data).encode())

    def test_external_checker_unknown_result_format_is_rejected(self) -> None:
        data = example_contract(required_checks=[{
            "name": "unknown-checker",
            "argv": ["echo", "test"],
            "timeout_seconds": 5,
            "report_format": "arbitrary-unreviewed-parser",
        }])
        with self.assertRaisesRegex(ContractError, "unsupported report_format"):
            load_contract(json.dumps(data).encode())

    def test_proof_of_done_parser_rejects_oversized_and_unknown_reports(self) -> None:
        from constraint_sentinel.checks import (
            POD_MAX_OUTPUT, _proof_of_done_summary,
        )
        with self.assertRaisesRegex(ValueError, "exceeded"):
            _proof_of_done_summary(b"x" * (POD_MAX_OUTPUT + 1), 0)
        with self.assertRaisesRegex(ValueError, "unknown verdict"):
            _proof_of_done_summary(
                b'{"verdict":"maybe","findings":[],"filesChecked":0}', 0,
            )
        with self.assertRaisesRegex(ValueError, "unknown rule id"):
            _proof_of_done_summary(
                b'{"verdict":"FAIL","findings":[{"ruleId":"SNEAK","severity":"block"}],"filesChecked":1}', 1,
            )

    def test_malformed_timeout_fails_closed(self) -> None:
        data = example_contract(required_checks=[{
            "name": "bad", "argv": ["echo", "ok"], "timeout_seconds": 0
        }])
        with self.assertRaises(ContractError):
            load_contract(json.dumps(data).encode())

    def test_bad_ref_and_corrupt_name_status(self) -> None:
        with self.assertRaises(GitError):
            parse_name_status(b"M\x00file_without_terminator")
        with self.assertRaises(GitError):
            parse_name_status(b"R100\x00old\x00")


class GlobTests(unittest.TestCase):
    def test_globs_anchor_to_path_boundaries(self) -> None:
        self.assertTrue(matches(("src/**",), "src/cart/item.py"))
        self.assertFalse(matches(("src/**",), "src2/cart/item.py"))
        self.assertFalse(matches(("src/*",), "src/cart/item.py"))
        self.assertTrue(matches(("src/*",), "src/item.py"))
        self.assertTrue(matches(("**/test_*.py",), "test_a.py"))
        self.assertTrue(matches(("**/test_*.py",), "tests/unit/test_a.py"))

    def test_traversal_and_ambiguous_globs_rejected(self) -> None:
        for value in ("../src/**", "src/../**", "/src/**", "src//**", "src\\**", "src/***.py"):
            with self.subTest(pattern=value), self.assertRaises(ValueError):
                validate_pattern(value)


if __name__ == "__main__":
    unittest.main()

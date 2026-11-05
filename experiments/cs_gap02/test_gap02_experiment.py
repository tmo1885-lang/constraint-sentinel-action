"""CS-GAP-02 offline controls; each case uses a new synthetic Git repository.

Only test this in a disposable filesystem. It executes the candidate test suites.
"""
from __future__ import annotations

import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


PROBE = Path(__file__).resolve().parent / "pytest_reachability_probe.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, text=True,
                          capture_output=True, timeout=10).stdout.strip()


class PytestEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="cs-gap02-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.baseline = self.root / "source"
        self.baseline.mkdir()
        git(self.baseline, "init", "-q", "-b", "main")
        git(self.baseline, "config", "user.name", "Gap02 synthetic owner")
        git(self.baseline, "config", "user.email", "owner@example.invalid")
        tests = self.baseline / "tests"
        tests.mkdir()
        (tests / "test_existing.py").write_text(
            "def test_already_present():\n    assert sum([3, 4]) == 7\n",
            encoding="utf-8",
        )
        (tests / "test_feature.py").write_text(
            "def test_original_behavior():\n    assert len('test') == 4\n",
            encoding="utf-8",
        )
        git(self.baseline, "add", ".")
        git(self.baseline, "commit", "-qm", "Two existing test cases")
        self.base_sha = git(self.baseline, "rev-parse", "HEAD")

    def candidate(self, addition: str, *, modify: str = "test_feature.py") -> Path:
        repo = self.root / "candidate"
        subprocess.run(["git", "clone", "-q", str(self.baseline), str(repo)],
                       check=True, timeout=10)
        git(repo, "config", "user.name", "Gap02 synthetic agent")
        git(repo, "config", "user.email", "agent@example.invalid")
        git(repo, "checkout", "-q", "-b", "task/add-regression")
        path = repo / "tests" / modify
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.write_text(path.read_text(encoding="utf-8") + "\n\n" + addition,
                            encoding="utf-8")
        else:
            path.write_text(addition, encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "Candidate added new regression test")
        return repo

    def run_probe(self, repo: Path, *, head: str = "HEAD",
                  extra: tuple[str, ...] = ()) -> tuple[int, dict | None, str]:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        result = subprocess.run(
            [sys.executable, str(PROBE), "--repo", str(repo), "--base", self.base_sha,
             "--head", head, *extra], capture_output=True, text=True, timeout=60, env=env,
        )
        return (result.returncode, json.loads(result.stdout) if result.stdout.strip() else None,
                result.stderr)

    def normal_pytest(self, repo: Path) -> tuple[int, str]:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                 "tests"], cwd=repo, capture_output=True, text=True,
                                timeout=20, env=env)
        return result.returncode, result.stdout + result.stderr

    def test_real_top_level_new_test(self) -> None:
        repo = self.candidate("def test_new_behavior():\n    assert sum([2, 3]) == 5\n")
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 0, stderr)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(len(report["accepted_new_cases"]), 1)
        self.assertEqual(report["unexecuted_or_unverified"], [])

    def test_uncollected_method_in_non_pytest_class(self) -> None:
        repo = self.candidate("class Feature:\n    def test_new_behavior(self):\n        assert 2 + 2 == 4\n")
        rc, out = self.normal_pytest(repo)
        self.assertEqual(rc, 0, out)
        self.assertIn("2 passed", out)
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 1, stderr)
        self.assertEqual(report["unexecuted_or_unverified"][0]["reason"], "not_collected")

    def test_new_pytest_class_method_passes(self) -> None:
        repo = self.candidate("class TestFeature:\n    def test_new_behavior(self):\n        assert 2 + 2 == 4\n")
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 0, stderr)
        self.assertEqual(len(report["accepted_new_cases"]), 1)

    def test_parametrized_all_cases_execute(self) -> None:
        repo = self.candidate(
            "import pytest\n\n@pytest.mark.parametrize('amount', [2, 3, 4])\n"
            "def test_amount(amount):\n    assert amount > 1\n"
        )
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 0, stderr)
        self.assertEqual(len(report["accepted_new_cases"]), 3)
        self.assertEqual(report["collected_count"], 5)

    def test_parametrized_one_case_skipped_reports_incomplete(self) -> None:
        repo = self.candidate(
            "import pytest\n\n@pytest.mark.parametrize('amount', [2, 3, 4])\n"
            "def test_amount(amount):\n    if amount == 3:\n"
            "        pytest.skip('platform cannot run this case')\n"
            "    assert amount > 1\n"
        )
        rc, out = self.normal_pytest(repo)
        self.assertEqual(rc, 0, out)
        self.assertIn("1 skipped", out)
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 3, stderr)
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(len(report["intentionally_skipped_cases"]), 1)
        self.assertEqual(len(report["accepted_new_cases"]), 2)
        # Intentional skip is unverified execution evidence, not a defect.
        strict_rc, strict_report, _ = self.run_probe(repo, extra=("--skip-policy", "require"))
        self.assertEqual(strict_rc, 1)
        self.assertEqual(strict_report["status"], "fail")

    def test_skip_decorator_not_counted_as_execution(self) -> None:
        repo = self.candidate(
            "import pytest\n\n@pytest.mark.skip(reason='intentional')\n"
            "def test_new_skipped():\n    assert 2 + 2 == 4\n"
        )
        rc, out = self.normal_pytest(repo)
        self.assertEqual(rc, 0, out)
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 3, stderr)
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(report["intentionally_skipped_cases"][0]["phase"], "setup")

    def test_xfail_is_executed_not_passing_proof(self) -> None:
        repo = self.candidate(
            "import pytest\n\n@pytest.mark.xfail(reason='known bug', strict=True)\n"
            "def test_known_problem():\n    assert 1 == 2\n"
        )
        rc, out = self.normal_pytest(repo)
        self.assertEqual(rc, 0, out)
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 0, stderr)
        self.assertEqual(report["accepted_new_cases"][0]["category"], "expected_failure_executed")

    def test_runtime_skip_is_not_counted_as_execution(self) -> None:
        repo = self.candidate(
            "import pytest\n\ndef test_new_runtime_skipped():\n"
            "    pytest.skip('cannot run')\n"
        )
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 3, stderr)
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(report["intentionally_skipped_cases"][0]["phase"], "call")

    def test_collection_import_error_fails_closed(self) -> None:
        repo = self.candidate(
            "import nonexistent_gap02_module_123\n\n"
            "def test_never_runs():\n    assert 1 == 1\n"
        )
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 1, stderr)
        self.assertNotEqual(report["pytest_exit"], 0)
        self.assertTrue(report["collection_errors"])

    def test_no_new_test_definition_requires_explicit_policy(self) -> None:
        repo = self.candidate("# changed this file but added no new test\n")
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 0, stderr)
        self.assertEqual(report["status"], "not_applicable")
        self.assertEqual(report["new_definitions"], [])
        strict_rc, strict_report, stderr = self.run_probe(
            repo, extra=("--require-new-tests",))
        self.assertEqual(strict_rc, 1, stderr)
        self.assertEqual(strict_report["status"], "fail")

    def test_dirty_candidate_refuses_evidence(self) -> None:
        repo = self.candidate("def test_new():\n    assert 3 > 2\n")
        (repo / "tests" / "unexpected.txt").write_text("dirty", encoding="utf-8")
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 2)
        self.assertIsNone(report)
        self.assertIn("dirty", stderr)

    def test_wrong_head_refuses_evidence(self) -> None:
        repo = self.candidate("def test_new():\n    assert 3 > 2\n")
        rc, report, stderr = self.run_probe(repo, head=self.base_sha)
        self.assertEqual(rc, 2)
        self.assertIsNone(report)

    def test_tests_mutating_worktree_refuse_evidence(self) -> None:
        repo = self.candidate(
            "from pathlib import Path\n\n"
            "def test_new_writes_untracked_file():\n"
            "    Path('new-side-effect.txt').write_text('unexpected')\n"
            "    assert True\n"
        )
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 2)
        self.assertIsNone(report)
        self.assertIn("changed", stderr)


    def test_nested_directory_new_test_executes(self) -> None:
        # Pytest test files in nested tests/unit directories should be supported.
        repo = self.candidate("def test_nested_behavior():\n    assert 7 * 6 == 42\n",
                              modify="unit/test_nested.py")
        rc, stdout = self.normal_pytest(repo)
        self.assertEqual(rc, 0, stdout)
        self.assertIn("3 passed", stdout)
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 0, stderr)
        self.assertEqual(len(report["new_definitions"]), 1)
        self.assertEqual(report["new_definitions"][0],
                         "tests/unit/test_nested.py::test_nested_behavior")
        self.assertEqual(len(report["accepted_new_cases"]), 1)

    def test_existing_parameter_matrix_expands_but_ast_delta_empty(self) -> None:
        old = self.baseline / "tests" / "test_feature.py"
        old.write_text(
            "import pytest\n\n@pytest.mark.parametrize('amount', [1, 2])\n"
            "def test_original_behavior(amount):\n    assert amount > 0\n",
            encoding="utf-8",
        )
        git(self.baseline, "add", ".")
        git(self.baseline, "commit", "-qm", "Preexisting two-parameter matrix")
        self.base_sha = git(self.baseline, "rev-parse", "HEAD")
        repo = self.root / "candidate"
        subprocess.run(["git", "clone", "-q", str(self.baseline), str(repo)],
                       check=True, timeout=10)
        git(repo, "config", "user.name", "Gap02 synthetic agent")
        git(repo, "config", "user.email", "agent@example.invalid")
        git(repo, "checkout", "-q", "-b", "task/extra-param")
        path = repo / "tests" / "test_feature.py"
        path.write_text(path.read_text().replace("[1, 2]", "[1, 2, 3]"), encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "Extend same test to one additional parameter")
        rc, output = self.normal_pytest(repo)
        self.assertEqual(rc, 0, output)
        self.assertIn("4 passed", output)
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 0, stderr)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["new_definitions"], [])
        self.assertEqual(len(report["new_case_ids"]), 1)
        self.assertTrue(report["new_case_ids"][0].endswith("[3]"))
        self.assertEqual(len(report["accepted_new_cases"]), 1)
        # The case itself is new although the function definition is not.

    def test_expanded_existing_parameter_with_skip_is_unverified(self) -> None:
        old = self.baseline / "tests" / "test_feature.py"
        old.write_text(
            "import pytest\n\n@pytest.mark.parametrize('amount', [1, 2])\n"
            "def test_original_behavior(amount):\n    assert amount > 0\n",
            encoding="utf-8")
        git(self.baseline, "add", ".")
        git(self.baseline, "commit", "-qm", "Preexisting two-parameter matrix")
        self.base_sha = git(self.baseline, "rev-parse", "HEAD")
        repo = self.root / "candidate"
        subprocess.run(["git", "clone", "-q", str(self.baseline), str(repo)],
                       check=True, timeout=10)
        git(repo, "config", "user.name", "Gap02 synthetic agent")
        git(repo, "config", "user.email", "agent@example.invalid")
        git(repo, "checkout", "-q", "-b", "task/extra-param-skip")
        path = repo / "tests" / "test_feature.py"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "[1, 2]", "[1, 2, pytest.param(3, marks=pytest.mark.skip(reason='platform'))]"),
            encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "Add intentionally skipped parameter")
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 3, stderr)
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(len(report["new_case_ids"]), 1)
        self.assertEqual(len(report["intentionally_skipped_cases"]), 1)
        self.assertFalse(report["accepted_new_cases"])

    def test_unexpected_xpass_not_treated_as_proven(self) -> None:
        repo = self.candidate(
            "import pytest\n\n@pytest.mark.xfail(reason='known bug', strict=False)\n"
            "def test_unexpected_pass():\n    assert 2 + 3 == 5\n"
        )
        rc, output = self.normal_pytest(repo)
        self.assertEqual(rc, 0, output)
        self.assertIn("1 xpassed", output)
        rc, report, stderr = self.run_probe(repo)
        self.assertEqual(rc, 1, stderr)
        self.assertEqual(report["unexecuted_or_unverified"][0]["reason"], "call_passed")
        self.assertIsNotNone(report["unexecuted_or_unverified"][0]["wasxfail"])


if __name__ == "__main__":
    unittest.main()

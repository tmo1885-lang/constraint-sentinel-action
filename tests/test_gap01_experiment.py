"""CS-GAP-01 controlled Git/test-discovery regressions; synthetic offline only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROBE = Path(os.environ["GAP01_PROBE"]) if "GAP01_PROBE" in os.environ else (
    Path(__file__).resolve().parents[1] / "experiments" / "cs_gap01" /
    "test_reachability_probe.py"
)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True,
        text=True, check=True, timeout=10,
    ).stdout.strip()


class TestDiscoveryEvidence(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="cs-gap01-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base_repo = self.root / "base"
        self.base_repo.mkdir()
        git(self.base_repo, "init", "-q", "-b", "main")
        git(self.base_repo, "config", "user.name", "Synthetic QA Owner")
        git(self.base_repo, "config", "user.email", "synthetic@example.invalid")
        tests = self.base_repo / "tests"
        tests.mkdir()
        (tests / "test_other.py").write_text(
            "import unittest\nclass Other(unittest.TestCase):\n"
            "    def test_existing_other(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        (tests / "test_feature.py").write_text(
            "import unittest\nclass Feature(unittest.TestCase):\n"
            "    def test_existing_feature(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        git(self.base_repo, "add", ".")
        git(self.base_repo, "commit", "-qm", "Two already-discovered baseline tests")
        self.base_sha = git(self.base_repo, "rev-parse", "HEAD")

    def candidate(self, mode: str) -> Path:
        repo = self.root / mode
        subprocess.run(["git", "clone", "-q", "--branch", "main", "--single-branch",
                        str(self.base_repo), str(repo)], check=True, timeout=10)
        git(repo, "config", "user.name", "Synthetic Agent")
        git(repo, "config", "user.email", "agent@example.invalid")
        git(repo, "switch", "-q", "-c", "task/feature")
        path = repo / "tests" / "test_feature.py"
        data = path.read_text(encoding="utf-8")
        if mode == "undiscovered":
            data += "\n\ndef test_new_requirement():\n    assert True\n"
        elif mode == "discovered":
            data = data.replace(
                "        self.assertTrue(True)\n",
                "        self.assertTrue(True)\n\n"
                "    def test_new_requirement(self):\n"
                "        self.assertTrue(True)\n",
            )
        elif mode == "renamed":
            data = data.replace("def test_existing_feature(self):",
                                "def test_new_requirement(self):")
        else:
            raise ValueError(mode)
        path.write_text(data, encoding="utf-8")
        git(repo, "add", "tests/test_feature.py")
        git(repo, "commit", "-qm", "Synthetic " + mode)
        return repo

    def probe(self, repo: Path, *, head: str = "HEAD") -> tuple[int, dict | None]:
        r = subprocess.run(
            [sys.executable, str(PROBE), "--repo", str(repo),
             "--base", self.base_sha, "--head", head],
            text=True, capture_output=True, timeout=30,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return r.returncode, json.loads(r.stdout) if r.stdout.strip() else None

    def normal_count(self, repo: Path) -> tuple[int, str]:
        r = subprocess.run(
            [sys.executable, "-m", "unittest", "discover",
             "-s", "tests", "-v"], cwd=repo, capture_output=True,
            text=True, timeout=20,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return r.returncode, r.stderr

    def test_new_function_not_discovered_even_when_suite_green(self) -> None:
        repo = self.candidate("undiscovered")
        exit_code, output = self.normal_count(repo)
        self.assertEqual(exit_code, 0)
        self.assertIn("Ran 2 tests", output)
        rc, report = self.probe(repo)
        self.assertEqual(rc, 1)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["executed_count"], 2)
        self.assertEqual(len(report["new_tests_not_executed"]), 1)
        self.assertIn("test_feature.test_new_requirement",
                      report["new_tests_not_executed"])

    def test_discovered_new_test_passes(self) -> None:
        repo = self.candidate("discovered")
        exit_code, output = self.normal_count(repo)
        self.assertEqual(exit_code, 0)
        self.assertIn("Ran 3 tests", output)
        rc, report = self.probe(repo)
        self.assertEqual(rc, 0)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["new_tests_not_executed"], [])
        self.assertEqual(report["executed_count"], 3)

    def test_valid_test_rename_does_not_require_count_growth(self) -> None:
        repo = self.candidate("renamed")
        exit_code, output = self.normal_count(repo)
        self.assertEqual(exit_code, 0)
        self.assertIn("Ran 2 tests", output)
        rc, report = self.probe(repo)
        self.assertEqual(rc, 0)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["executed_count"], 2)

    def test_worktree_tamper_refuses_evidence(self) -> None:
        repo = self.candidate("discovered")
        (repo / "tests" / "unexpected.py").write_text("x = 1\n", encoding="utf-8")
        rc, report = self.probe(repo)
        self.assertEqual(rc, 2)
        self.assertIsNone(report)

    def test_wrong_head_refuses_evidence(self) -> None:
        repo = self.candidate("discovered")
        rc, report = self.probe(repo, head=self.base_sha)
        self.assertEqual(rc, 2)
        self.assertIsNone(report)


if __name__ == "__main__":
    unittest.main()

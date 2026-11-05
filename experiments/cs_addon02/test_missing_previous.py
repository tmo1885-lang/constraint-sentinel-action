"""CS-ADDON-02: real-gap regression controls; offline disposable Git only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PROBE = Path(__file__).resolve().parents[1] / "cs_gap02" / "pytest_reachability_probe.py"

def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          text=True, capture_output=True, timeout=12).stdout.strip()

class MissingPreviousCases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cs-addon02-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.owner = self.root / "owner"
        self.owner.mkdir()
        git(self.owner, "init", "-q", "-b", "main")
        git(self.owner, "config", "user.name", "Synthetic Owner")
        git(self.owner, "config", "user.email", "owner@example.invalid")
        (self.owner / "tests").mkdir()
        (self.owner / "tests/test_existing.py").write_text(
            "def test_still_runs():\n    assert 2 + 3 == 5\n", encoding="utf-8")
        (self.owner / "tests/test_covered.py").write_text(
            "import pytest\n@pytest.mark.parametrize('n', [1, 2, 3])\n"
            "def test_required(n):\n    assert n > 0\n", encoding="utf-8")
        (self.owner / "README.md").write_text("# Synthetic\n", encoding="utf-8")
        git(self.owner, "add", ".")
        git(self.owner, "commit", "-qm", "Two test modules")
        self.base = git(self.owner, "rev-parse", "HEAD")

    def candidate(self, mode):
        repo = self.root / mode
        subprocess.run(["git", "clone", "-q", str(self.owner), str(repo)],
                       check=True, capture_output=True, timeout=15)
        git(repo, "config", "user.name", "Synthetic QA")
        git(repo, "config", "user.email", "qa@example.invalid")
        git(repo, "switch", "-q", "-c", "trial/" + mode)
        if mode == "documentation":
            (repo / "README.md").write_text("# Synthetic\n\nUpdated.\n", encoding="utf-8")
        elif mode == "config":
            # Hides three preexisting test cases without touching their file.
            (repo / "pytest.ini").write_text(
                "[pytest]\npython_functions = test_still_runs\n", encoding="utf-8")
        else:
            path = repo / "tests/test_covered.py"
            source = path.read_text(encoding="utf-8")
            new_name = ("helper_required" if mode == "lost"
                        else "test_rebranded")
            path.write_text(source.replace("def test_required", "def " + new_name),
                            encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "Synthetic " + mode)
        return repo

    def check(self, mode):
        repo = self.candidate(mode)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        p = subprocess.run([sys.executable, str(PROBE), "--repo", str(repo),
                            "--base", self.base, "--head", "HEAD"],
                           capture_output=True, text=True, env=env, timeout=45)
        self.assertTrue(p.stdout.strip(), p.stderr)
        self.assertFalse(git(repo, "status", "--porcelain"))
        return p.returncode, json.loads(p.stdout)

    def test_disappeared_existing_cases_are_not_silent(self):
        code, report = self.check("lost")
        self.assertEqual((code, report["status"]), (3, "unverified"))
        self.assertEqual((report["baseline_collected_count"],
                          report["collected_count"]), (4, 1))
        self.assertEqual(len(report["previously_collected_cases_missing"]), 3)
        self.assertEqual(report["new_case_ids"], [])
        self.assertTrue(all(x["reason"] == "previously_collected_case_missing"
                            for x in report["unexecuted_or_unverified"]))

    def test_valid_rename_warns_not_fails(self):
        code, report = self.check("renamed")
        self.assertEqual((code, report["status"]), (3, "unverified"))
        self.assertEqual(report["baseline_collected_count"],
                         report["collected_count"])
        self.assertEqual(len(report["new_case_ids"]), 3)
        self.assertEqual(len(report["accepted_new_cases"]), 3)
        self.assertEqual(len(report["previously_collected_cases_missing"]), 3)

    def test_docs_only_still_not_applicable(self):
        code, report = self.check("documentation")
        self.assertEqual((code, report["status"]), (0, "not_applicable"))
        self.assertEqual(report["previously_collected_cases_missing"], [])

    def test_configuration_only_collection_loss_is_not_silent(self):
        code, report = self.check("config")
        self.assertEqual((report["baseline_collected_count"],
                          report["collected_count"]), (4, 1))
        self.assertEqual((code, report["status"]), (3, "unverified"))
        self.assertEqual(len(report["previously_collected_cases_missing"]), 3)
        self.assertEqual(report["new_case_ids"], [])

if __name__ == "__main__":
    unittest.main()

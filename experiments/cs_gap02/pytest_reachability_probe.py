#!/usr/bin/env python3
"""CS-GAP-02: synthetic/offline pytest test-identity reachability witness.

This is NOT a sandbox. It executes candidate test code and must not be run
against untrusted PRs on a privileged runner. It does not prove test quality.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


# Executed in a separate interpreter with Python isolation enabled. Pytest
# executes user candidate tests anyway; isolation does not sandbox test code.
RUNNER = r'''
import json
import os
from pathlib import Path
import sys
import pytest

root = Path(sys.argv[1]).resolve()
mode = sys.argv[2]
assert mode in ("run", "collect")
os.chdir(root)
sys.path[:0] = [str(root), str(root / "src")]

class Recorder:
    def __init__(self):
        self.collected = []
        self.events = []
        self.collection_errors = []

    def pytest_collection_finish(self, session):
        self.collected = [item.nodeid for item in session.items]

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append(str(report.longrepr)[:800])

    def pytest_runtest_logreport(self, report):
        if report.when not in ("setup", "call", "teardown"):
            return
        wasxfail = getattr(report, "wasxfail", None)
        self.events.append({
            "nodeid": report.nodeid,
            "phase": report.when,
            "outcome": report.outcome,
            "wasxfail": str(wasxfail) if wasxfail else None,
            "skip_reason": str(report.longrepr)[-500:] if report.outcome == "skipped" else None,
        })

witness = Recorder()
# Do not load third-party site-wide pytest plugins; the project's own
# conftest.py can still run and must be treated as untrusted candidate code.
code = pytest.main(["-q", "-p", "no:cacheprovider"] +
                   (["--collect-only"] if mode == "collect" else []) +
                   ["tests"], plugins=[witness])
print("__CS_GAP02_RESULT__" + json.dumps({
    "pytest_exit": int(code),
    "collected": witness.collected,
    "events": witness.events,
    "collection_errors": witness.collection_errors,
}, sort_keys=True))
'''


def git(repo: Path, *args: str, optional: bool = False) -> bytes | None:
    proc = subprocess.run(["git", "-C", str(repo), *args], check=False,
                          capture_output=True, timeout=10)
    if proc.returncode:
        if optional:
            return None
        raise RuntimeError("Git command failed: " + proc.stderr[:250].decode("utf-8", "replace"))
    return proc.stdout


def extract_new_defs(source: bytes | None, path: str) -> set[str]:
    if source is None:
        return set()
    tree = ast.parse(source, filename=path)
    identities = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            identities.add(f"{path}::{node.name}")
        if isinstance(node, ast.ClassDef):
            for method in node.body:
                if (isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and method.name.startswith("test_")):
                    identities.add(f"{path}::{node.name}::{method.name}")
    return identities


def _run_pytest(repo: Path, mode: str, env: dict[str, str]) -> dict:
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", RUNNER, str(repo), mode],
        cwd=repo, env=env, capture_output=True, text=True, timeout=45,
    )
    marker = "__CS_GAP02_RESULT__"
    payloads = [line[len(marker):] for line in result.stdout.splitlines()
                if line.startswith(marker)]
    if result.returncode or len(payloads) != 1:
        raise RuntimeError(f"pytest {mode} witness failed or report missing: "
                           + result.stderr[-250:])
    return json.loads(payloads[0])


def _baseline_checkout(repo: Path, base: str, directory: Path) -> Path:
    # Independent temporary checkout: baseline collection must not run against
    # the candidate tree or mutate the accepted source. Not an OS sandbox.
    dest = directory / "baseline"
    for argv in (["git", "clone", "--quiet", "--no-local", "--no-checkout",
                  str(repo), str(dest)],
                 ["git", "-C", str(dest), "checkout", "--quiet", "--detach", base]):
        proc = subprocess.run(argv, capture_output=True, timeout=25, check=False)
        if proc.returncode:
            raise RuntimeError("Baseline checkout unavailable: "
                               + proc.stderr[-200:].decode("utf-8", "replace"))
    return dest


def _def_for_case(nodeid: str) -> str:
    return nodeid.split("[", 1)[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--skip-policy", choices=("warn", "require"), default="warn",
                        help="warn: explicit UNVERIFIED (exit 3) instead of FAIL for skips")
    parser.add_argument("--require-new-tests", action="store_true",
                        help="FAIL if no new pytest case identities or test definitions")
    args = parser.parse_args()
    repo = args.repo.resolve()

    try:
        base = git(repo, "rev-parse", "--verify", args.base + "^{commit}").decode().strip()
        head = git(repo, "rev-parse", "--verify", args.head + "^{commit}").decode().strip()
        current = git(repo, "rev-parse", "HEAD").decode().strip()
        if head != current:
            raise RuntimeError("requested candidate head differs from checked-out HEAD")
        if git(repo, "status", "--porcelain", "-z"):
            raise RuntimeError("dirty candidate worktree before run")
        if git(repo, "merge-base", base, head).decode().strip() != base:
            raise RuntimeError("candidate does not descend from approved base")

        changed = git(repo, "diff", "--name-only", "--no-ext-diff", "-z", base, head)
        paths = [p.decode("utf-8") for p in changed.split(b"\0") if p]
        changed_test_paths = {
            p for p in paths if Path(p).parts[:1] == ("tests",)
            and Path(p).name.startswith("test_") and p.endswith(".py")
        }
        new_defs: set[str] = set()
        for path in changed_test_paths:
            before = git(repo, "show", f"{base}:{path}", optional=True)
            after = git(repo, "show", f"{head}:{path}", optional=True)
            new_defs.update(extract_new_defs(after, path) - extract_new_defs(before, path))

        env = os.environ.copy()
        for key in list(env):
            if any(s in key.upper() for s in ("TOKEN", "SECRET", "PASSWORD", "API_KEY")):
                env.pop(key, None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        with tempfile.TemporaryDirectory(prefix="cs-gap02-baseline-") as tmp:
            baseline_repo = _baseline_checkout(repo, base, Path(tmp))
            baseline_event = _run_pytest(baseline_repo, "collect", env)
        if (baseline_event["pytest_exit"] != 0
                or baseline_event["collection_errors"]):
            raise RuntimeError("baseline pytest collection failed; cannot compare cases")
        event = _run_pytest(repo, "run", env)
        baseline_ids = set(baseline_event["collected"])
        candidate_ids = set(event["collected"])
        # A new parameter in an existing function is visible as a new node ID.
        added_ids = {n for n in candidate_ids - baseline_ids
                     if n.split("::", 1)[0] in changed_test_paths}
        # A previously collected test that vanishes is not automatically a
        # defect (it may be an authorized rename/removal), but an evidence
        # verifier must not silently describe lost coverage as NOT_APPLICABLE.
        # Compare the entire collection: changes to pytest.ini, conftest.py,
        # or collection hooks can remove tests without touching a test file.
        # Such differences are review warnings, NOT hard enforcement failures.
        dropped_ids = sorted(baseline_ids - candidate_ids)
        # Catch a newly introduced test function/method even when pytest fails
        # to collect it, and validate every parameterized instance collected.
        expected_ids = added_ids | {
            nodeid for nodeid in candidate_ids
            if _def_for_case(nodeid) in new_defs
        }
        missing_defs = sorted(d for d in new_defs
                              if not any(_def_for_case(n) == d
                                         for n in candidate_ids))

        events_by_id: dict[str, list[dict]] = {}
        for entry in event["events"]:
            events_by_id.setdefault(entry["nodeid"], []).append(entry)
        accepted: list[dict] = []
        skips: list[dict] = []
        failures: list[dict] = [
            {"definition": d, "reason": "not_collected"} for d in missing_defs
        ]
        for nodeid in sorted(expected_ids):
            phases = events_by_id.get(nodeid, [])
            calls = [e for e in phases if e["phase"] == "call"]
            if calls and calls[0]["outcome"] == "passed" and not calls[0]["wasxfail"]:
                accepted.append({"nodeid": nodeid, "category": "call_passed"})
            elif calls and calls[0]["outcome"] == "skipped" and calls[0]["wasxfail"]:
                accepted.append({"nodeid": nodeid, "category": "expected_failure_executed"})
            else:
                skip_event = next((e for e in phases if e["outcome"] == "skipped"
                                   and not e["wasxfail"]), None)
                if skip_event:
                    skips.append({"nodeid": nodeid, "reason": "intentionally_skipped",
                                  "phase": skip_event["phase"],
                                  "explanation": skip_event.get("skip_reason")})
                else:
                    call = calls[0] if calls else None
                    failures.append({"nodeid": nodeid,
                                     "reason": ("call_" + call["outcome"]
                                                if call else "no_call_phase"),
                                     "wasxfail": call["wasxfail"] if call else None})

        if git(repo, "status", "--porcelain", "-z"):
            raise RuntimeError("candidate worktree changed during pytest execution")
        no_new = not expected_ids and not new_defs
        if (failures or event["pytest_exit"] != 0 or event["collection_errors"]
                or (no_new and args.require_new_tests)
                or (skips and args.skip_policy == "require")):
            status, rc = "fail", 1
        elif skips or dropped_ids:
            # A deleted/renamed previously collected case warrants review,
            # not an automatic claim of a test regression or a passing suite.
            status, rc = "unverified", 3
        elif no_new:
            status, rc = "not_applicable", 0
        else:
            status, rc = "pass", 0
        report = {
            "experiment": "CS-GAP-02-R2",
            "status": status,
            "base": base,
            "candidate": head,
            "changed_paths": paths,
            "new_definitions": sorted(new_defs),
            "baseline_collected_count": len(baseline_ids),
            "collected_count": len(candidate_ids),
            "new_case_ids": sorted(added_ids),
            "verified_case_ids": sorted(expected_ids),
            "previously_collected_cases_missing": dropped_ids,
            "pytest_exit": event["pytest_exit"],
            "collection_errors": event["collection_errors"],
            "accepted_new_cases": accepted,
            "intentionally_skipped_cases": skips,
            "unexecuted_or_unverified": (failures + skips + [
                {"nodeid": n, "reason": "previously_collected_case_missing"}
                for n in dropped_ids
            ]),
            "skip_policy": args.skip_policy,
            "require_new_tests": args.require_new_tests,
            "scope": "pytest-only synthetic test identity witness; no sandbox; no correctness proof",
        }
        encoded = json.dumps(report, sort_keys=True, indent=2)
        print(encoded)
        if args.report:
            args.report.write_text(encoded + "\n", encoding="utf-8")
        return rc
    except (OSError, ValueError, RuntimeError, SyntaxError, subprocess.TimeoutExpired,
            UnicodeError, json.JSONDecodeError) as exc:
        print("CS-GAP-02 evidence unavailable: " + str(exc)[:500], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

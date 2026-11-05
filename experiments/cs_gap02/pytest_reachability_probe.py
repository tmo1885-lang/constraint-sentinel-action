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


# Executed in a separate interpreter with Python isolation enabled. Pytest
# executes user candidate tests anyway; isolation does not sandbox test code.
RUNNER = r'''
import json
import os
from pathlib import Path
import sys
import pytest

root = Path(sys.argv[1]).resolve()
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
        })

witness = Recorder()
# Do not load third-party site-wide pytest plugins; the project's own
# conftest.py can still run and must be treated as untrusted candidate code.
code = pytest.main(["-q", "-p", "no:cacheprovider", "tests"], plugins=[witness])
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--report", type=Path)
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
        new = set()
        for path in paths:
            if (Path(path).parts[:1] == ("tests",) and Path(path).name.startswith("test_")
                    and path.endswith(".py")):
                before = git(repo, "show", f"{base}:{path}", optional=True)
                after = git(repo, "show", f"{head}:{path}", optional=True)
                new.update(extract_new_defs(after, path) - extract_new_defs(before, path))

        # Failing when zero NEW test identities are added is intentional for
        # this declared 'add a regression test' experimental policy.
        env = os.environ.copy()
        for key in list(env):
            if any(s in key.upper() for s in ("TOKEN", "SECRET", "PASSWORD", "API_KEY")):
                env.pop(key, None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        result = subprocess.run([sys.executable, "-I", "-B", "-c", RUNNER, str(repo)],
                                cwd=repo, env=env, capture_output=True, text=True, timeout=45)
        marker = "__CS_GAP02_RESULT__"
        payloads = [line[len(marker):] for line in result.stdout.splitlines() if line.startswith(marker)]
        if result.returncode or len(payloads) != 1:
            raise RuntimeError("pytest subprocess did not produce exactly one witness report; "
                               + result.stderr[-250:])
        event = json.loads(payloads[0])
        collected = event["collected"]
        events = event["events"]
        grouped = {}
        for item in collected:
            simple = item.split("[", 1)[0]
            grouped.setdefault(simple, []).append(item)

        incomplete = []
        accepted = []
        for definition in sorted(new):
            nodeids = grouped.get(definition, [])
            if not nodeids:
                incomplete.append({"definition": definition, "reason": "not_collected"})
                continue
            for nodeid in nodeids:
                phases = [e for e in events if e["nodeid"] == nodeid]
                call = [e for e in phases if e["phase"] == "call"]
                if not call:
                    incomplete.append({"definition": definition, "nodeid": nodeid,
                                       "reason": "no_call_phase"})
                elif call[0]["outcome"] == "passed" and not call[0]["wasxfail"]:
                    accepted.append({"nodeid": nodeid, "category": "call_passed"})
                elif call[0]["outcome"] == "skipped" and call[0]["wasxfail"]:
                    # XFAIL was executed, but is not evidence of a passing assertion.
                    accepted.append({"nodeid": nodeid, "category": "expected_failure_executed"})
                else:
                    incomplete.append({"definition": definition, "nodeid": nodeid,
                                       "reason": "call_" + call[0]["outcome"],
                                       "wasxfail": call[0]["wasxfail"]})

        if git(repo, "status", "--porcelain", "-z"):
            raise RuntimeError("candidate worktree changed during pytest execution")
        status = ("pass" if new and not incomplete and event["pytest_exit"] == 0
                  and not event["collection_errors"] else "fail")
        report = {
            "experiment": "CS-GAP-02",
            "status": status,
            "base": base,
            "candidate": head,
            "changed_paths": paths,
            "new_definitions": sorted(new),
            "collected_count": len(collected),
            "pytest_exit": event["pytest_exit"],
            "collection_errors": event["collection_errors"],
            "accepted_new_cases": accepted,
            "unexecuted_or_unverified": incomplete,
            "scope": "pytest-only synthetic test identity witness; no sandbox; no correctness proof",
        }
        encoded = json.dumps(report, sort_keys=True, indent=2)
        print(encoded)
        if args.report:
            args.report.write_text(encoded + "\n", encoding="utf-8")
        return 0 if status == "pass" else 1
    except (OSError, ValueError, RuntimeError, SyntaxError, subprocess.TimeoutExpired,
            UnicodeError, json.JSONDecodeError) as exc:
        print("CS-GAP-02 evidence unavailable: " + str(exc)[:500], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

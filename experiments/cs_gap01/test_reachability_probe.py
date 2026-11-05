#!/usr/bin/env python3
"""CS-GAP-01: experimental test-reachability witness, not a security gate.

In a disposable checkout, compare new Python test functions in a Git candidate
against tests actually discovered and executed by standard unittest.
This does not establish assertion quality, runtime integrity, or sandboxing.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys


RUNNER = r"""
import io
import json
from pathlib import Path
import sys
import unittest

root = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(root), str(root / "src"), str(root / "tests")]
loader = unittest.TestLoader()
suite = loader.discover(start_dir=str(root / "tests"), pattern="test_*.py",
                        top_level_dir=str(root / "tests"))

def flatten(node):
    for item in node:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item.id()

ids = list(flatten(suite))
stream = io.StringIO()
outcome = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
print("__CS_GAP01_RESULT__" + json.dumps({
    "discovered": ids,
    "executed": outcome.testsRun,
    "errors": len(outcome.errors),
    "failures": len(outcome.failures),
    "skips": len(outcome.skipped),
    "skipped_ids": [test.id() for test, reason in outcome.skipped],
    "loader_errors": loader.errors,
    "successful": outcome.wasSuccessful(),
    "output_excerpt": stream.getvalue()[-2500:],
}, sort_keys=True))
"""


def git(repo: Path, *argv: str, optional: bool = False) -> bytes | None:
    r = subprocess.run(["git", "-C", str(repo), *argv],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=10)
    if r.returncode:
        if optional:
            return None
        raise RuntimeError("Git command failed: " + r.stderr[:300].decode(
            "utf-8", "replace"))
    return r.stdout


def test_defs(data: bytes | None, module: str) -> set[str]:
    if not data:
        return set()
    tree = ast.parse(data, filename=module)
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                found.add(f"{module}.{node.name}")
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if (isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and child.name.startswith("test_")):
                    found.add(f"{module}.{node.name}.{child.name}")
    return found


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--base", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    repo = args.repo.resolve()
    try:
        base = git(repo, "rev-parse", "--verify", args.base + "^{commit}").decode().strip()
        head = git(repo, "rev-parse", "--verify", args.head + "^{commit}").decode().strip()
        checked_out = git(repo, "rev-parse", "HEAD").decode().strip()
        if head != checked_out:
            raise RuntimeError("checked-out candidate does not match approved head")
        if git(repo, "status", "--porcelain", "-z"):
            raise RuntimeError("candidate worktree is dirty before test execution")
        if git(repo, "merge-base", base, head).decode().strip() != base:
            raise RuntimeError("candidate is not descended from approved base")

        changed = git(repo, "diff", "--name-only", "-z", base, head)
        paths = [s.decode("utf-8") for s in changed.split(b"\0") if s]
        new_tests: set[str] = set()
        for path in paths:
            if not (path.startswith("tests/test_") and path.endswith(".py")):
                continue
            module = Path(path).stem
            before = git(repo, "show", f"{base}:{path}", optional=True)
            after = git(repo, "show", f"{head}:{path}", optional=True)
            new_tests.update(test_defs(after, module) - test_defs(before, module))

        # Trusted runner is in this external file. The candidate test suite
        # executes in a subprocess; this is NOT an OS-level sandbox.
        env = os.environ.copy()
        for key in list(env):
            if ("TOKEN" in key.upper() or "SECRET" in key.upper()
                    or "API_KEY" in key.upper() or "PASSWORD" in key.upper()):
                env.pop(key, None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c", RUNNER, str(repo)],
            cwd=repo, env=env, capture_output=True, text=True, timeout=40,
        )
        marker = "__CS_GAP01_RESULT__"
        payloads = [s.partition(marker)[2] for s in result.stdout.splitlines()
                    if s.startswith(marker)]
        if result.returncode or len(payloads) != 1:
            raise RuntimeError("unittest evidence subprocess failed or omitted report")
        evidence = json.loads(payloads[0])
        observed = set(evidence["discovered"])
        skipped_ids = set(evidence["skipped_ids"])
        # unittest counts skipped tests in testsRun, but their bodies did not execute.
        executed_ids = observed - skipped_ids
        missing = sorted(new_tests - executed_ids)
        status = ("pass" if new_tests and not missing
                  and evidence["successful"] and evidence["executed"] > 0
                  and evidence["errors"] == 0 and evidence["failures"] == 0
                  and not evidence["loader_errors"] else "fail")
        if git(repo, "status", "--porcelain", "-z"):
            status = "fail"
            integrity_note = "test execution modified candidate visible Git state"
        else:
            integrity_note = "visible Git worktree unchanged by test execution"
        report = {
            "experiment": "CS-GAP-01",
            "status": status,
            "base": base,
            "candidate": head,
            "changed_paths": paths,
            "new_test_definitions": sorted(new_tests),
            "new_tests_not_executed": missing,
            "discovered_tests": sorted(observed),
            "skipped_tests": sorted(skipped_ids),
            "reported_tests_run": evidence["executed"],
            "executed_count": evidence["executed"] - len(skipped_ids),
            "unittest_success": evidence["successful"],
            "integrity_note": integrity_note,
            "limitations": "unittest-only; AST direct Python test definitions; "
                           "no assertion semantics, dynamic tests, side-effect controls "
                           "or executable attestation",
        }
        encoded = json.dumps(report, indent=2, sort_keys=True)
        print(encoded)
        if args.report:
            args.report.write_text(encoded + "\n", encoding="utf-8")
        return 0 if status == "pass" else 1
    except (OSError, ValueError, RuntimeError, SyntaxError,
            subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print("CS-GAP-01 evidence unavailable: " + str(exc)[:400], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

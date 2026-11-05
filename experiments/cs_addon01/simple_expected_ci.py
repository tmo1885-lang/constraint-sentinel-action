#!/usr/bin/env python3
"""Minimal project-specific pytest CI: owner states an exact required test ID.

A straightforward alternative to the automatic case discovery in CS-GAP-02 R2.
The expectation must be declared externally for each relevant task.
Synthetic, unprivileged test use only; not a runtime sandbox.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--expected-node-id", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=10
        ).stdout.strip()
        if sha != args.head:
            raise ValueError("Candidate commit differs from owner-provided SHA")
        if subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True, text=True, check=True, timeout=10
        ).stdout.strip():
            raise ValueError("Candidate has uncommitted edits")
        if not args.expected_node_id:
            result = {
                "status": "NOT_APPLICABLE",
                "source": sha,
                "reason": "No test ID required by this project-specific comparator",
            }
        else:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(repo / "src")
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
            for key in list(env):
                if any(x in key.upper() for x in ("SECRET", "TOKEN", "PASSWORD", "API_KEY")):
                    env.pop(key, None)
            with tempfile.TemporaryDirectory(prefix="cs-addon01-simple-") as d:
                xml = Path(d) / "pytest-results.xml"
                r = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                     "--junitxml=" + str(xml), args.expected_node_id],
                    cwd=repo, env=env, capture_output=True, text=True, timeout=40
                )
                tests = skipped = errors = failures = 0
                if xml.exists():
                    data = ET.parse(xml).getroot()
                    suite = data if data.tag == "testsuite" else data.find("testsuite")
                    if suite is not None:
                        tests = int(suite.attrib.get("tests", "0"))
                        skipped = int(suite.attrib.get("skipped", "0"))
                        errors = int(suite.attrib.get("errors", "0"))
                        failures = int(suite.attrib.get("failures", "0"))
                if r.returncode or not tests or errors or failures:
                    status = "FAIL"
                elif skipped:
                    status = "UNVERIFIED"
                else:
                    status = "PASS"
                result = {
                    "status": status,
                    "source": sha,
                    "expected_node_id": args.expected_node_id,
                    "pytest_exit": r.returncode,
                    "reported_tests": tests,
                    "skipped": skipped,
                    "errors": errors,
                    "failures": failures,
                }
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired, ET.ParseError) as exc:
        print("Expected-ID CI unavailable: " + str(exc)[:300], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

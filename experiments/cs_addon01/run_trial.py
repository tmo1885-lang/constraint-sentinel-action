#!/usr/bin/env python3
"""CS-ADDON-01: executable, unprivileged, warn-only AQG + R2 comparison.

Generates four first-party synthetic Git candidate checkouts and runs a pinned
AQG release, an exact-ID project-specific pytest check, and the experimental
CS-GAP-02 R2 witness independently. No code in the AQG repository is changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from fixtures import make_fixtures

AQG_COMMIT = "d3e7e466d784f25e5ccf9488a8749bd6c9851743"
EXPECTED = {
    "good": ("PASS", "PASS"),
    "undiscovered": ("FAIL", "FAIL"),
    "skipped": ("UNVERIFIED", "UNVERIFIED"),
    "no_new": ("NOT_APPLICABLE", "NOT_APPLICABLE"),
}
R2_RC = {"pass": 0, "fail": 1, "unverified": 3, "not_applicable": 0}


def execute(argv: list[str], *, cwd: Path | None = None) -> tuple[int, str, str, int]:
    start = time.perf_counter()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    # Synthetic first-party source only, but avoid passing secret-named variables.
    for key in list(env):
        if any(x in key.upper() for x in ("SECRET", "TOKEN", "PASSWORD", "API_KEY")):
            env.pop(key, None)
    p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                       text=True, timeout=85)
    return p.returncode, p.stdout, p.stderr, round((time.perf_counter() - start) * 1000)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aqg-root", required=True, type=Path)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    src = Path(__file__).resolve().parent
    probe = (src.parent / "cs_gap02" / "pytest_reachability_probe.py").resolve()
    aqg = args.aqg_root.resolve()
    pinned = subprocess.run(["git", "-C", str(aqg), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True,
                            timeout=10).stdout.strip()
    if pinned != AQG_COMMIT:
        raise ValueError("Expected reviewed AQG commit " + AQG_COMMIT)
    if not probe.is_file():
        raise FileNotFoundError("R2 research probe missing from stacked branch")
    probe_sha256 = hashlib.sha256(probe.read_bytes()).hexdigest()
    root = args.workdir.resolve()
    manifest = make_fixtures(root)
    evidence = {
        "experiment": "CS-ADDON-01",
        "aqg_pinned_commit": pinned,
        "probe_sha256": probe_sha256,
        "mode": "WARN_ONLY",
        "advisory_only": True,
        "base": manifest["base"],
        "cases": {},
        "limitations": (
            "Independent synthetic Git repos only; candidate test execution "
            "has no OS sandbox and never establishes semantic task correctness."
        ),
    }

    for case, meta in manifest["cases"].items():
        candidate = Path(meta["path"])
        base = manifest["base"]
        head = meta["head"]
        aqg_file = root / f"{case}-aqg.json"
        r2_file = root / f"{case}-r2.json"
        simple_file = root / f"{case}-simple.json"
        companion_file = root / f"{case}-companion.json"

        aqg_cmd = [
            sys.executable, str(aqg / "scripts" / "run_quality_gates.py"),
            "--config", str(src / "aqg-config.json"),
            "--repo", str(candidate),
            "--pr-body-file", str(src / "pr-evidence.md"),
            "--output-json", str(aqg_file),
        ]
        aqg_rc, aqg_stdout, aqg_stderr, aqg_ms = execute(aqg_cmd)
        if aqg_rc != 0 or not aqg_file.is_file():
            raise AssertionError(f"AQG fixture {case} unavailable: "
                                 + aqg_stderr[-300:] + aqg_stdout[-300:])
        aqg_report = json.loads(aqg_file.read_text(encoding="utf-8"))
        if aqg_report.get("ok") is not True:
            raise AssertionError(f"AQG rejected selected fixture {case}")

        r2_cmd = [
            sys.executable, str(probe), "--repo", str(candidate),
            "--base", base, "--head", head, "--skip-policy", "warn",
            "--report", str(r2_file),
        ]
        r2_rc, r2_stdout, r2_stderr, r2_ms = execute(r2_cmd)
        if not r2_file.is_file():
            raise AssertionError(f"R2 report {case} missing: " + r2_stderr[-300:])
        r2_report = json.loads(r2_file.read_text(encoding="utf-8"))
        if r2_report.get("status") != meta["expected_r2_status"]:
            raise AssertionError(f"R2 {case} unexpectedly returned "
                                 + str(r2_report.get("status")))
        if r2_rc != R2_RC[r2_report["status"]]:
            raise AssertionError(f"R2 {case} exit/status mismatch")

        simple_cmd = [
            sys.executable, str(src / "simple_expected_ci.py"),
            "--repo", str(candidate), "--head", head,
            "--output", str(simple_file),
        ]
        if case != "no_new":
            simple_cmd.extend([
                "--expected-node-id", "tests/test_added.py::test_new_behavior"
            ])
        simple_rc, simple_stdout, simple_stderr, simple_ms = execute(simple_cmd)
        if simple_rc != 0 or not simple_file.is_file():
            raise AssertionError(f"Simple comparator {case} unavailable: "
                                 + simple_stderr[-300:] + simple_stdout[-300:])
        simple_report = json.loads(simple_file.read_text(encoding="utf-8"))

        adapter_cmd = [
            sys.executable, str(src / "adapter.py"),
            "--aqg-json", str(aqg_file),
            "--r2-json", str(r2_file), "--base", base, "--head", head,
            "--r2-exit", str(r2_rc), "--output", str(companion_file),
        ]
        adapter_rc, _, adapter_stderr, _ = execute(adapter_cmd)
        if adapter_rc != 0:
            raise AssertionError(f"Companion normalization failed {case}: "
                                 + adapter_stderr[-300:])
        companion = json.loads(companion_file.read_text(encoding="utf-8"))
        expected_simple, expected_r2 = EXPECTED[case]
        if (simple_report["status"] != expected_simple or
                companion["sentinel_evidence_status"] != expected_r2 or
                companion["aqg_status"] != "PASS" or
                not companion["advisory_only"]):
            raise AssertionError(f"Comparator disagreement in {case}")

        diff = subprocess.run(["git", "-C", str(candidate), "status",
                               "--porcelain"], capture_output=True,
                              text=True, check=True, timeout=10)
        if diff.stdout.strip():
            raise AssertionError(f"Candidate worktree modified by checker {case}")

        evidence["cases"][case] = {
            "candidate_head": head,
            "aqg_status": companion["aqg_status"],
            "simple_expected_id_status": simple_report["status"],
            "sentinel_evidence_status": companion["sentinel_evidence_status"],
            "advisory_review_outcome": companion["review_outcome"],
            "new_case_count": companion["new_case_count"],
            "aqg_ms": aqg_ms,
            "simple_ms": simple_ms,
            "r2_ms": r2_ms,
            "candidate_worktree_clean": True,
        }
        print(
            f"{case}: AQG={companion['aqg_status']}, "
            f"fixed-ID={simple_report['status']}, "
            f"R2={companion['sentinel_evidence_status']}, "
            f"warn-only={companion['advisory_only']}; "
            f"ms AQG={aqg_ms}/fixed-ID={simple_ms}/R2={r2_ms}",
            flush=True,
        )
        if case in ("undiscovered", "skipped"):
            print("::warning title=CS-ADDON-01 advisory::"
                  + case + " requires review; research check is nonblocking",
                  flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("CS-ADDON-01: all four expected synthetic comparisons verified "
          "(not a production quality gate)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

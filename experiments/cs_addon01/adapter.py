#!/usr/bin/env python3
"""CS-ADDON-01: warning-only AQG + R2 result adapter (research, not a gate).

Does not execute candidate code. Does not alter AQG or Sentinel. Reads two
already-produced JSON reports, checks the R2 source identities, and preserves
the evidence distinction between PASS, FAIL, UNVERIFIED and NOT_APPLICABLE.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

R2_EXITS = {"pass": 0, "fail": 1, "unverified": 3, "not_applicable": 0}
R2_LABELS = {
    "pass": "PASS",
    "fail": "FAIL",
    "unverified": "UNVERIFIED",
    "not_applicable": "NOT_APPLICABLE",
}


def combine(aqg: dict, r2: dict, *, base: str, head: str, r2_exit: int) -> dict:
    """Normalize evidence, never converting incomplete or failed R2 to PASS."""
    if type(aqg.get("ok")) is not bool:
        raise ValueError("AQG report lacks boolean ok")
    if not isinstance(aqg.get("gates"), dict) or not aqg["gates"]:
        raise ValueError("AQG report lacks gate results")
    if r2.get("experiment") != "CS-GAP-02-R2":
        raise ValueError("Unexpected R2 evidence schema")
    status = r2.get("status")
    if status not in R2_EXITS:
        raise ValueError("Unknown R2 status")
    if R2_EXITS[status] != r2_exit:
        raise ValueError("R2 exit does not match its declared status")
    if r2.get("base") != base or r2.get("candidate") != head:
        raise ValueError("R2 evidence source identity mismatch")
    if not isinstance(r2.get("changed_paths"), list):
        raise ValueError("R2 missing changed-path evidence")
    if not isinstance(r2.get("new_case_ids"), list):
        raise ValueError("R2 missing new-case inventory")
    if not isinstance(r2.get("unexecuted_or_unverified"), list):
        raise ValueError("R2 missing incomplete-case inventory")
    dropped = r2.get("previously_collected_cases_missing")
    if not isinstance(dropped, list):
        raise ValueError("R2 missing previously-collected-case inventory")
    if status == "pass" and (r2["unexecuted_or_unverified"] or dropped):
        raise ValueError("R2 claims PASS with unresolved cases")
    if status == "not_applicable" and (r2["new_case_ids"] or dropped):
        raise ValueError("R2 claims NOT_APPLICABLE with changed execution coverage")
    aqg_status = "PASS" if aqg["ok"] else "FAIL"
    r2_status = R2_LABELS[status]
    return {
        "experiment": "CS-ADDON-01",
        "mode": "WARN_ONLY",
        "advisory_only": True,
        "aqg_status": aqg_status,
        "aqg_gate_statuses": {
            key: value.get("status", "unknown")
            for key, value in sorted(aqg["gates"].items())
            if isinstance(value, dict)
        },
        "sentinel_evidence_status": r2_status,
        "review_outcome": "REVIEW_REQUIRED" if not aqg["ok"] or status in (
            "fail", "unverified") else (
            "NO_NEW_TEST_EVIDENCE_CLAIM" if status == "not_applicable"
            else "EVIDENCE_OBSERVED"
        ),
        "source": {
            "approved_base": base,
            "candidate_commit": head,
            "r2_bound_to_exact_commits": True,
            "aqg_commit_binding_independently_verified": False,
        },
        "new_case_count": len(r2["new_case_ids"]),
        "new_case_ids": r2["new_case_ids"],
        "previously_collected_cases_missing": dropped,
        "unexecuted_or_unverified": r2["unexecuted_or_unverified"],
        "task_completion": "NOT_VERIFIED",
        "limitations": (
            "Only synthetic first-party pytest fixtures; candidate tests execute "
            "without an OS sandbox. This report is not a production or merge gate."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aqg-json", type=Path, required=True)
    p.add_argument("--r2-json", type=Path, required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--r2-exit", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        aqg = json.loads(args.aqg_json.read_text(encoding="utf-8"))
        r2 = json.loads(args.r2_json.read_text(encoding="utf-8"))
        report = combine(aqg, r2, base=args.base, head=args.head,
                         r2_exit=args.r2_exit)
        text = json.dumps(report, indent=2, sort_keys=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("CS-ADDON-01 adapter evidence unavailable: "
              + str(exc)[:400], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

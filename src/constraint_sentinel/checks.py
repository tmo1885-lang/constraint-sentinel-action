"""Run trusted-base checks. Consume structured evidence, never raw private output.

Check argv is loaded from the trusted baseline, not the candidate. Exact
placeholders are expanded into already-verified values with shell=False.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .contract import RequiredCheck


POD_MAX_OUTPUT = 256 * 1024
POD_MAX_RECORDED_FINDINGS = 50


def _expanded_argv(check: RequiredCheck, repo: Path, base_sha: str) -> list[str]:
    return [
        arg.replace("{base_commit}", base_sha).replace("{repo_root}", str(repo))
        for arg in check.argv
    ]


def _proof_of_done_summary(stdout: bytes, exit_code: int) -> dict[str, Any]:
    """Parse v0.5's JSON verdict; do not disclose agent hints or raw messages."""
    if len(stdout) > POD_MAX_OUTPUT:
        raise ValueError("Proof of Done output exceeded the structured-report limit")
    try:
        data = json.loads(stdout)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Proof of Done returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("Proof of Done report must be a JSON object")
    verdict = data.get("verdict")
    findings = data.get("findings")
    if verdict not in ("PASS", "SUSPICIOUS", "FAIL"):
        raise ValueError("Proof of Done returned an unknown verdict")
    if not isinstance(findings, list):
        raise ValueError("Proof of Done findings must be an array")
    if (verdict == "FAIL") != (exit_code != 0):
        raise ValueError("Proof of Done process exit does not match its verdict")
    if exit_code not in (0, 1):
        raise ValueError("Proof of Done returned an unsupported exit code")
    files = data.get("filesChecked")
    if type(files) is not int or files < 0:
        raise ValueError("Proof of Done filesChecked must be a nonnegative integer")

    safe_findings: list[dict[str, str]] = []
    for raw in findings[:POD_MAX_RECORDED_FINDINGS]:
        if not isinstance(raw, dict):
            raise ValueError("Proof of Done finding is not an object")
        rule_id = raw.get("ruleId")
        severity = raw.get("severity")
        path = raw.get("file")
        if not isinstance(rule_id, str) or not re.fullmatch(r"POD\d{3}", rule_id):
            raise ValueError("Proof of Done returned unknown rule id")
        if severity not in ("block", "warn", "info"):
            raise ValueError("Proof of Done finding severity is invalid")
        if path is not None and not isinstance(path, str):
            raise ValueError("Proof of Done finding path is invalid")
        # Include just the metadata a developer can use to locate a finding.
        # Do not expose untrusted message text, source snippets or agent hints.
        safe_findings.append({
            "rule_id": rule_id, "severity": severity,
            "path": (path or "")[:300],
        })
    if len(findings) > POD_MAX_RECORDED_FINDINGS:
        # Truncation is disclosed, not silently interpreted as complete.
        truncated = True
    else:
        truncated = False

    return {
        "verdict": verdict,
        "files_checked": files,
        "findings_total": len(findings),
        "findings": safe_findings,
        "findings_truncated": truncated,
    }


def run_checks(
    repo: Path,
    required: tuple[RequiredCheck, ...],
    *,
    base_sha: str = "",
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for check in required:
        try:
            command = _expanded_argv(check, repo, base_sha)
            # These commands are baseline-approved. They still may execute
            # untrusted candidate code: use least-privilege isolated CI.
            completed = subprocess.run(
                command, cwd=repo, shell=False, capture_output=True,
                timeout=check.timeout_seconds, check=False,
            )
            if check.report_format == "proof_of_done_v0":
                try:
                    summary = _proof_of_done_summary(
                        completed.stdout, completed.returncode,
                    )
                except ValueError as exc:
                    results.append({
                        "name": check.name, "status": "error",
                        "exit_code": completed.returncode,
                        "reason": str(exc),
                    })
                    continue
                verdict = summary["verdict"]
                status = (
                    "fail" if verdict == "FAIL" else
                    "warning" if verdict == "SUSPICIOUS" else "pass"
                )
                results.append({
                    "name": check.name, "status": status,
                    "exit_code": completed.returncode,
                    "report_format": check.report_format,
                    "summary": summary,
                })
            else:
                results.append({
                    "name": check.name,
                    "status": "pass" if completed.returncode == 0 else "fail",
                    "exit_code": completed.returncode,
                    # Arbitrary test outputs may contain secrets. Omit them.
                })
        except subprocess.TimeoutExpired:
            results.append({
                "name": check.name, "status": "timeout", "exit_code": None,
            })
        except OSError as exc:
            results.append({
                "name": check.name, "status": "error",
                "reason": f"Required command unavailable: {type(exc).__name__}",
                "exit_code": None,
            })
    return results

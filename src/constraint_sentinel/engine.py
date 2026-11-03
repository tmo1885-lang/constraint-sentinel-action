"""Deterministic checks of Git changes against a trusted task contract."""
from __future__ import annotations

from typing import Any

from .contract import Contract
from .git import Change
from .patterns import matches
from .test_identity import preserves_test_identity


IMMUTABLE_CONTROL_PATHS = (".sentinel/**", ".github/workflows/**")


def evaluate_scope(
    contract: Contract, changes: list[Change], *, contract_path: str,
    index_flags: tuple[tuple[str, str], ...] = (),
    recovered_renames: tuple[dict[str, str], ...] = (),
    ignored_protected: tuple[str, ...] = (),
) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    for path in ignored_protected:
        violations.append({
            "rule": "ignored_protected_path",
            "path": path,
            "detail": "Protected, ignored untracked path exists; creation time is unknown",
        })
    for path, flag in index_flags:
        violations.append({
            "rule": "git_index_visibility",
            "path": path,
            "detail": f"Git index {flag} flag may conceal changes; clear it before verification",
        })
    files: list[dict[str, Any]] = []
    for change in changes:
        affected = change.paths()
        files.append({"operation": change.operation, "before": change.before, "after": change.after})
        if change.operation in {"U", "X", "B"}:
            violations.append({
                "rule": "unresolved_git_state", "path": change.after or change.before or "",
                "detail": "Unmerged or unknown Git state cannot be verified",
            })
        for path in affected:
            if path == contract_path or matches(IMMUTABLE_CONTROL_PATHS, path):
                violations.append({
                    "rule": "protected_control", "path": path,
                    "detail": "Task contracts and CI workflows require a separate trusted change",
                })
            elif matches(contract.protect, path):
                violations.append({
                    "rule": "protected_path", "path": path,
                    "detail": "Path matches a protected pattern",
                })
            elif not matches(contract.allow, path):
                violations.append({
                    "rule": "outside_scope", "path": path,
                    "detail": "Path is not covered by the approved allowlist",
                })
        if contract.deny_test_deletions and change.before and matches(contract.test_paths, change.before):
            if change.operation == "D" or (
                change.operation == "R" and (
                    change.after is None or not matches(contract.test_paths, change.after)
                    or not preserves_test_identity(change.before, change.after)
                )
            ):
                violations.append({
                    "rule": "test_removed", "path": change.before,
                    "detail": "A test was deleted or moved out of configured test paths",
                })
    # Repeat findings are unhelpful to people reading or parsing the report.
    unique = list({(v["rule"], v["path"]): v for v in violations}.values())
    unique.sort(key=lambda v: (v["path"], v["rule"]))
    return {
        "status": "fail" if unique else "pass",
        "files": files,
        "violations": unique,
        "recovered_renames": list(recovered_renames),
        "ignored_protected_paths": list(ignored_protected),
    }


def make_report(
    contract: Contract, scope: dict[str, Any], check_results: list[dict[str, Any]],
    *, base_sha: str, head_sha: str | None, mode: str, checks_requested: bool,
    ignored_audit_enabled: bool = False,
) -> dict[str, Any]:
    if scope["violations"]:
        status = "fail"
    elif contract.required_checks and not checks_requested:
        status = "unverified"
    elif any(item["status"] not in ("pass", "warning") for item in check_results):
        status = "fail"
    else:
        status = "pass"
    if not contract.required_checks:
        checks_status = "not_configured"
    elif check_results:
        checks_status = (
            "fail" if any(item["status"] not in ("pass", "warning") for item in check_results)
            else "pass_with_warnings" if any(item["status"] == "warning" for item in check_results)
            else "pass"
        )
    elif not checks_requested:
        checks_status = "not_run"
    elif scope["violations"]:
        checks_status = "skipped_due_to_scope_failure"
    else:
        checks_status = "not_run"
    # Never present a clean scope diff as sandboxing or runtime authorization.
    return {
        "schema_version": 1,
        "tool": "constraint-sentinel",
        "status": status,
        "task_id": contract.task_id,
        "contract_sha256": contract.digest,
        "base_commit": base_sha,
        "head_commit": head_sha,
        "mode": mode,
        "scope": scope,
        "checks": {"status": checks_status, "results": check_results},
        "task_completion": {
            "status": "not_verified",
            "reason": "Scope compliance and passing configured checks do not establish the requested outcome.",
        },
        "coverage": {
            "git_changes": "tracked_commits" if head_sha else "tracked_and_untracked_nonignored_worktree",
            "ignored_untracked_paths": "audited" if ignored_audit_enabled else "not_audited",
            "pre_execution_blocking": "not_provided",
            "external_side_effects": "not_observed",
            "semantic_intent": "not_verified",
            "trusted_policy_source": "base_commit",
            "required_check_executable_integrity": (
                "not_attested" if contract.required_checks else "not_configured"
            ),
        },
    }

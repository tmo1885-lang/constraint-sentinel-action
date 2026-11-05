"""Local CLI for scoped, inspectable AI coding tasks."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .approval import approve_task, setup_ci
from .checks import run_checks
from .contract import ContractError, load_contract
from .engine import evaluate_scope, make_report
from .git import (GitError, baseline_file, collect_changes, commit_sha, index_visibility_flags,
                  repository_root, worktree_fingerprint)
from .worktree import recover_exact_test_moves, list_ignored_protected


DEFAULT_CONTRACT = {
    "schema_version": 1,
    "task_id": "replace-with-a-specific-task-id",
    "allow": ["src/**", "tests/**"],
    "protect": ["config/production/**", "db/migrations/**"],
    "test_paths": ["tests/**", "**/test_*.py", "**/*.test.js", "**/*.spec.ts"],
    "deny_test_deletions": True,
    "required_checks": [],
}


def contract_path_safe(value: str) -> bool:
    parts = value.split("/")
    return bool(value and not value.startswith("/") and "\\" not in value and
                "\x00" not in value and all(part not in ("", ".", "..") for part in parts))


def init_command(repo: Path) -> int:
    root = repository_root(repo)
    path = root / ".sentinel" / "contract.json"
    if path.exists():
        raise ContractError(f"Will not overwrite existing {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(DEFAULT_CONTRACT, indent=2) + "\n", encoding="utf-8")
    print(f"Created {path}")
    print("Edit the example allow/protect paths, then commit the contract to a trusted base branch.")
    print("For initial testing, use: constraint-sentinel check --base HEAD")
    return 0


def check_command(args: argparse.Namespace) -> int:
    if not contract_path_safe(args.contract):
        raise ContractError("Contract path must be root-relative without parent traversal")
    repo = repository_root(args.repo)
    base = commit_sha(repo, args.base)
    head = commit_sha(repo, args.head) if args.head else None
    if args.run_checks and head is not None:
        raise ContractError("For check execution use a checked-out worktree (omit --head)")
    if args.audit_ignored_protected and head is not None:
        raise ContractError("Ignored-path auditing requires a worktree (omit --head)")
    # Critical: read the policy from the verified base commit, NOT the candidate.
    raw_contract = baseline_file(repo, base, args.contract)
    contract = load_contract(raw_contract)
    changes = collect_changes(repo, base, head)
    renames = []
    if head is None:
        changes, renames = recover_exact_test_moves(repo, base, contract, changes)
    ignored_paths = ()
    if args.audit_ignored_protected:
        ignored_paths, _ = list_ignored_protected(repo, contract, args.contract)
    initial_index_flags = tuple(index_visibility_flags(repo)) if head is None else ()
    scope = evaluate_scope(
        contract, changes, contract_path=args.contract,
        index_flags=initial_index_flags,
        recovered_renames=tuple(renames),
        ignored_protected=tuple(ignored_paths),
    )
    check_results = []
    if args.run_checks and not scope["violations"] and contract.required_checks:
        fingerprint_before = worktree_fingerprint(repo, base)
        check_results = run_checks(repo, contract.required_checks, base_sha=base)
        post_index_flags = tuple(index_visibility_flags(repo))
        post_ignored = ()
        if args.audit_ignored_protected:
            post_ignored, _ = list_ignored_protected(repo, contract, args.contract)
        if (fingerprint_before != worktree_fingerprint(repo, base)
                or post_index_flags != initial_index_flags
                or tuple(post_ignored) != tuple(ignored_paths)):
            # No test run can silently change the candidate while validating it.
            post_changes = collect_changes(repo, base, None)
            post_changes, post_renames = recover_exact_test_moves(
                repo, base, contract, post_changes,
            )
            scope = evaluate_scope(
                contract, post_changes, contract_path=args.contract,
                index_flags=post_index_flags,
                recovered_renames=tuple(post_renames),
                ignored_protected=tuple(post_ignored),
            )
            scope["violations"].append({
                "rule": "validation_changed_worktree",
                "path": "(worktree)",
                "detail": "Required checks changed visible Git state or protected ignored paths",
            })
            scope["status"] = "fail"
    report = make_report(
        contract, scope, check_results, base_sha=base, head_sha=head,
        mode="commit_compare" if head else "worktree", checks_requested=args.run_checks,
        ignored_audit_enabled=args.audit_ignored_protected,
    )
    encoded = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded, encoding="utf-8")
    if args.format == "json":
        print(encoded, end="")
    else:
        print(f"Constraint Sentinel gate: {report['status'].upper()}")
        print(f"Task: {contract.task_id}")
        print(f"Git scope: {report['scope']['status'].upper()}")
        print(f"Changed files: {len(scope['files'])}; scope violations: {len(scope['violations'])}")
        for item in scope["violations"]:
            print(f"  [{item['rule']}] {item['path']!r}: {item['detail']}")
        print(f"Required checks: {report['checks']['status']}")
        print("Task completion: NOT VERIFIED (scope and checks are not acceptance proof)")
        print(f"Recovered exact unstaged test moves: {len(scope['recovered_renames'])}")
        print(f"Ignored protected paths: {report['coverage']['ignored_untracked_paths']}")
        for item in check_results:
            print(f"  {item['name']}: {item['status']}")
            summary = item.get("summary")
            if summary:
                print(f"    {summary['verdict']} — {summary['findings_total']} findings "
                      f"({summary['files_checked']} files checked)")
                for issue in summary["findings"]:
                    print(f"    [{issue['rule_id']}] {issue['severity']}: {issue['path']!r}")
                if summary["findings_truncated"]:
                    print("    ...additional findings omitted; review the external checker")
        print("Coverage: Git change verification only; NO runtime enforcement or semantic guarantees.")
        if args.report:
            print(f"Report: {args.report}")
    return 0 if report["status"] == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="constraint-sentinel",
        description="Audit an AI coding task against an independently stored Git-base contract.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    init_parser = sub.add_parser("init", help="Write an example contract (does not overwrite)")
    init_parser.add_argument("--repo", type=Path, default=Path("."))
    setup_parser = sub.add_parser(
        "setup", help="Owner: install one-time automatic PR scope check"
    )
    setup_parser.add_argument("--repo", type=Path, default=Path("."))
    approve_parser = sub.add_parser(
        "approve", help="Owner: approve and commit a task contract before agent work"
    )
    approve_parser.add_argument("--repo", type=Path, default=Path("."))
    approve_parser.add_argument("--task", required=True, help="Short owner-approved task identifier")
    approve_parser.add_argument("--allow", action="append", required=True,
                                help="Allowed path/glob (repeat this flag)")
    approve_parser.add_argument("--protect", action="append", default=[],
                                help="Explicitly protected path/glob (repeat this flag)")
    approve_parser.add_argument("--test-path", action="append", default=[],
                                help="Test path/glob (optional; repeat this flag)")
    approve_parser.add_argument("--replace", action="store_true",
                                help="Explicitly replace an existing task contract")
    check_parser = sub.add_parser("check", help="Compare changes against a trusted base contract")
    check_parser.add_argument("--repo", type=Path, default=Path("."))
    check_parser.add_argument("--base", required=True, help="Trusted baseline commit or ref")
    check_parser.add_argument("--head", help="Optional candidate commit; omitted checks the worktree")
    check_parser.add_argument("--contract", default=".sentinel/contract.json")
    check_parser.add_argument("--run-checks", action="store_true", help="Run baseline-declared checks in current worktree")
    check_parser.add_argument("--audit-ignored-protected", action="store_true",
                              help="Opt-in: fail if Git-ignored untracked protected paths exist; may be slow")
    check_parser.add_argument("--report", help="Write machine-readable JSON report")
    check_parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            return init_command(args.repo)
        if args.command == "setup":
            commit = setup_ci(args.repo)
            print(f"Installed Sentinel PR scope workflow in owner commit {commit}")
            print("Push this commit to the protected PR base branch before agent work.")
            print("Require the sentinel-scope status check; keep the workflow outside agent control.")
            return 0
        if args.command == "approve":
            base = approve_task(
                args.repo, task_id=args.task, allow=args.allow,
                protect=args.protect, test_paths=args.test_path,
                replace=args.replace,
            )
            print(f"Approved task {args.task!r} at Git baseline {base}")
            print("Push this approved commit to the protected PR base branch before agent work.")
            print("PR CI can use github.event.pull_request.base.sha automatically.")
            print(f"Local check: constraint-sentinel check --base {base}")
            print("IMPORTANT: keep the approved baseline and verifier outside agent control.")
            return 0
        return check_command(args)
    except (GitError, ContractError, OSError, UnicodeError, ValueError) as exc:
        print(f"Constraint Sentinel error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

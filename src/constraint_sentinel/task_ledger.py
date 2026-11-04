"""CS-UX-02: per-task approval ledger that does not mutate the PR base branch.

This is an experimental *owner* workflow. For security-relevant CI, the
approval branch must be server-protected and fetched from a trusted remote;
a writable local Git ref is not an independent authorization authority.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from .approval import DEFAULT_TEST_PATHS
from .contract import ContractError, load_contract
from .engine import evaluate_scope, make_report
from .git import (GitError, collect_changes, commit_sha, index_visibility_flags,
                  repository_root)
from .worktree import list_ignored_protected, recover_exact_test_moves

APPROVAL_REF = "refs/heads/sentinel-approvals"
ZERO_SHA = "0" * 40
SHA_RE = re.compile(r"[0-9a-f]{40,64}\Z")
BRANCH_RE = re.compile(r"task/[a-zA-Z0-9][a-zA-Z0-9._/-]{0,99}\Z")


def _git(repo: Path, *args: str, fail_ok: bool = False) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        if fail_ok:
            return None
        reason = result.stderr.decode("utf-8", errors="replace").strip()
        raise ContractError(f"Git task approval failed: {reason}")
    return result.stdout.decode("utf-8", errors="replace").strip()


def _record_path(branch: str) -> str:
    if not BRANCH_RE.fullmatch(branch) or ".." in branch or "//" in branch:
        raise ContractError(
            "Task branch must look like task/name (letters, digits, '.', '_' or '-')"
        )
    return "approvals/" + hashlib.sha256(branch.encode("utf-8")).hexdigest() + ".json"


def start_task(
    path: Path, *, branch: str, task_id: str, allow: list[str],
    protect: list[str], test_paths: list[str], publish: bool = False,
) -> tuple[str, str]:
    """Create one owner-approved record on a separate ledger branch, then a task branch.

    No change is committed to main. Approval is written *before* creating the
    coding branch. The caller is responsible for protecting the approval ref.
    Failed publication rolls back the local approval unless the ref has changed.
    """
    repo = repository_root(path)
    record_path = _record_path(branch)
    if _git(repo, "status", "--porcelain=v1", "--untracked-files=all", "-z"):
        raise ContractError("Start requires a clean owner-controlled repository")
    base_sha = _git(repo, "rev-parse", "--verify", "HEAD")
    base_branch = _git(repo, "symbolic-ref", "--short", "HEAD")
    if _git(repo, "rev-parse", "--verify", f"refs/heads/{branch}", fail_ok=True) is not None:
        raise ContractError(f"Task branch already exists: {branch}")
    contract_data = {
        "schema_version": 1, "task_id": task_id,
        "allow": allow, "protect": protect,
        "test_paths": test_paths or list(DEFAULT_TEST_PATHS),
        "deny_test_deletions": True, "required_checks": [],
    }
    # Preserve strict contract validation before making any Git changes.
    raw_contract = (json.dumps(contract_data, sort_keys=True) + "\n").encode("utf-8")
    load_contract(raw_contract)
    record_data = {
        "schema_version": 1, "task_branch": branch,
        "base_branch": base_branch, "base_commit": base_sha,
        "contract": contract_data,
    }
    record_bytes = (json.dumps(record_data, sort_keys=True, indent=2) + "\n").encode("utf-8")

    previous_ref = _git(repo, "rev-parse", "--verify", APPROVAL_REF, fail_ok=True)
    old_rev = previous_ref if previous_ref is not None else ZERO_SHA
    approval_parent = previous_ref or base_sha

    with tempfile.TemporaryDirectory(prefix="sentinel-owner-ledger-") as worktree:
        temp = Path(worktree)
        _git(repo, "worktree", "add", "--quiet", "--detach", str(temp), approval_parent)
        try:
            dest = temp / record_path
            if dest.exists():
                raise ContractError(f"Task already has an approval: {branch}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(record_bytes)
            _git(temp, "add", "--", record_path)
            _git(temp, "commit", "--quiet", "-m", f"Owner approves task {task_id}")
            approved_commit = _git(temp, "rev-parse", "HEAD")
            # CAS: never silently race another owner's approval.
            _git(repo, "update-ref", APPROVAL_REF, approved_commit, old_rev)
        finally:
            _git(repo, "worktree", "remove", "--force", str(temp))

    if publish:
        # Requires a protected server-side approval branch to be meaningful.
        try:
            _git(repo, "push", "origin", f"{APPROVAL_REF}:{APPROVAL_REF}")
        except ContractError as publish_error:
            try:
                # Only undo our own update, never a concurrent owner's approval.
                if previous_ref is None:
                    _git(repo, "update-ref", "-d", APPROVAL_REF, approved_commit)
                else:
                    _git(repo, "update-ref", APPROVAL_REF, previous_ref, approved_commit)
            except ContractError as rollback_error:
                raise ContractError(
                    f"{publish_error}; local approval rollback failed: {rollback_error}"
                ) from rollback_error
            raise
    # Never create an agent branch until the approval commit is ready, and
    # published if the caller requested it.
    _git(repo, "switch", "-c", branch, base_sha)
    return base_sha, approved_commit


def check_task(
    path: Path, *, approval_ref: str, branch: str | None = None,
    expected_base: str | None = None, expected_base_branch: str | None = None,
    head: str | None = None, audit_ignored_protected: bool = False,
    approval_repo: Path | None = None,
) -> dict:
    """Check a candidate against an independently supplied approval ref.

    Passing an attacker-controlled approval_ref is NOT a security boundary.
    GitHub CI must fetch an owner-protected ref from the trusted server.
    """
    repo = repository_root(path)
    if branch is None:
        branch = _git(repo, "symbolic-ref", "--short", "HEAD")
    record_path = _record_path(branch)
    if approval_ref.startswith("-") or not approval_ref:
        raise ContractError("Approval ref must be a nonempty trusted Git ref")
    # Do not evaluate the approval from a path in the candidate worktree.
    # We deliberately use a committed Git object, not a mutable JSON file.
    trusted_repo = repository_root(approval_repo) if approval_repo else repo
    raw = _git(trusted_repo, "show", f"{approval_ref}:{record_path}")
    try:
        record = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ContractError("Approval record is invalid JSON") from exc
    if not isinstance(record, dict) or set(record) != {
        "schema_version", "task_branch", "base_branch", "base_commit", "contract",
    } or type(record["schema_version"]) is not int or record["schema_version"] != 1:
        raise ContractError("Approval record has unexpected structure")
    if record["task_branch"] != branch:
        raise ContractError("Approval branch binding mismatch")
    if not isinstance(record["base_commit"], str) or not SHA_RE.fullmatch(record["base_commit"]):
        raise ContractError("Approval base SHA is malformed")
    if not isinstance(record["base_branch"], str) or not record["base_branch"]:
        raise ContractError("Approval base branch is missing")
    if expected_base and expected_base != record["base_commit"]:
        raise ContractError("PR base moved or approval is for a different baseline; reapprove")
    if expected_base_branch and expected_base_branch != record["base_branch"]:
        raise ContractError("PR base branch does not match owner approval")
    base = commit_sha(repo, record["base_commit"])
    if head:
        head_sha = commit_sha(repo, head)
        _git(repo, "merge-base", "--is-ancestor", base, head_sha)
    else:
        head_sha = None
        _git(repo, "merge-base", "--is-ancestor", base, "HEAD")
    contract_value = record["contract"]
    if not isinstance(contract_value, dict):
        raise ContractError("Approval contract must be an object")
    contract = load_contract((json.dumps(contract_value, sort_keys=True) + "\n").encode("utf-8"))
    changes = collect_changes(repo, base, head_sha)
    renames = []
    if not head_sha:
        changes, renames = recover_exact_test_moves(repo, base, contract, changes)
    ignored_paths = ()
    if audit_ignored_protected:
        if head_sha:
            raise ContractError("Ignored-path audit cannot run against a commit-only head")
        ignored_paths, _ = list_ignored_protected(repo, contract, ".sentinel/contract.json")
    scope = evaluate_scope(
        contract, changes, contract_path=".sentinel/contract.json",
        index_flags=tuple(index_visibility_flags(repo)) if not head_sha else (),
        recovered_renames=tuple(renames), ignored_protected=tuple(ignored_paths),
    )
    report = make_report(
        contract, scope, [], base_sha=base, head_sha=head_sha,
        mode="commit_compare" if head_sha else "worktree", checks_requested=False,
        ignored_audit_enabled=audit_ignored_protected,
    )
    report["approval"] = {
        "task_branch": branch,
        "base_branch": record["base_branch"],
        "approval_ref": approval_ref,
        "approval_source": "separate_checkout" if approval_repo else "candidate_repository",
        "record_path": record_path,
        "trust": "caller_must_verify_ref_is_owner_protected",
    }
    return report

TRUSTED_PR_WORKFLOW = """name: Constraint Sentinel protected task scope
on:
  pull_request_target:
    types: [opened, synchronize, reopened, ready_for_review, edited]

permissions:
  contents: read

jobs:
  scope:
    runs-on: ubuntu-latest
    steps:
      - name: Require same-repository task branch
        env:
          HEAD_REPOSITORY: ${{{{ github.event.pull_request.head.repo.full_name }}}}
          BASE_REPOSITORY: ${{{{ github.repository }}}}
        run: test "$HEAD_REPOSITORY" = "$BASE_REPOSITORY"
      - name: Checkout candidate as data, without persisting credentials
        uses: actions/checkout@v4
        with:
          repository: ${{{{ github.repository }}}}
          ref: ${{{{ github.event.pull_request.head.sha }}}}
          path: candidate
          fetch-depth: 0
          persist-credentials: false
      - name: Checkout owner-protected approvals separately
        uses: actions/checkout@v4
        with:
          repository: ${{{{ github.repository }}}}
          ref: sentinel-approvals
          path: trusted-approvals
          persist-credentials: false
      - name: Check approved task scope only (never execute candidate code)
        uses: tmo1885-lang/constraint-sentinel-action@{checker_sha}
        with:
          repository-path: candidate
          approval-repo-path: trusted-approvals
          task-branch: ${{{{ github.event.pull_request.head.ref }}}}
          expected-base-branch: ${{{{ github.event.pull_request.base.ref }}}}
          head: ${{{{ github.event.pull_request.head.sha }}}}
          base: ${{{{ github.event.pull_request.base.sha }}}}
"""


def setup_task_ci(repo_path: Path, *, checker_sha: str) -> str:
    """Owner-only, one-time local workflow commit. Does not configure rulesets."""
    if not SHA_RE.fullmatch(checker_sha):
        raise ContractError("Checker must be pinned to a reviewed full commit SHA")
    repo = repository_root(repo_path)
    if _git(repo, "status", "--porcelain=v1", "--untracked-files=all", "-z"):
        raise ContractError("CI setup requires a clean owner-controlled checkout")
    _git(repo, "rev-parse", "--verify", "HEAD")
    root = repo / ".github"
    folder = root / "workflows"
    path = folder / "sentinel-task-scope.yml"
    if root.is_symlink() or folder.is_symlink() or path.is_symlink():
        raise ContractError("CI workflow must not follow a symlink")
    if path.exists():
        raise ContractError("Task-specific CI workflow already exists; refusing overwrite")
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(TRUSTED_PR_WORKFLOW.format(checker_sha=checker_sha), encoding="utf-8")
    _git(repo, "add", "--", ".github/workflows/sentinel-task-scope.yml")
    _git(repo, "commit", "--only", "--quiet",
         "-m", "Install owner-controlled Sentinel task-scope workflow",
         "--", ".github/workflows/sentinel-task-scope.yml")
    return _git(repo, "rev-parse", "HEAD")

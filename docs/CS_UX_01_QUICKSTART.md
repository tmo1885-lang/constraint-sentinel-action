# CS-UX-01: low-friction owner-approved task scope prototype

**Status: experimental branch prototype, not released.** This workflow removes manual
JSON and SHA handling for ordinary PR checks without claiming that a coding agent
can safely approve its own scope. The trusted PR base branch and workflow remain
outside the agent's authority.

## One-time owner setup

From a **clean, trusted working copy** of a GitHub repository, install this
prototype CLI from its review branch (for evaluation only, not production),
then run:

```console
constraint-sentinel setup
```

This creates **and commits only**
`.github/workflows/sentinel-scope.yml` on the owner's current branch. It pins
the public checker at immutable v0.1.0b3 source SHA
`8f3fb1c8cb7629f24f9d0baefad6ff298e205aa6`, uses read-only GitHub
permissions, checks PRs with `github.event.pull_request.base.sha`, and does not
enable execution of candidate-provided test commands.

Push the trusted workflow commit to the intended PR base branch, configure branch
protection / required checks, and **do not give the coding agent control of that
base branch, workflow, or Actions settings**. The `setup` command does not push,
configure protection, or create a GitHub App installation.

## Approve one task (owner only, before agent edits)

On the clean owner-controlled PR base branch:

```console
constraint-sentinel approve --task vgr-issue-13 --allow src/vgr/cli.py --allow tests/test_cli_m4.py --protect src/vgr/search_execution.py
```

This creates and commits just `.sentinel/contract.json`. It prints the approved
baseline SHA for the audit trail, but no SHA needs to be typed into a PR workflow.

Push the approval commit **before** the agent starts. Then give the agent a
separate coding branch derived from that exact approved base. Opening a pull
request back to that base automatically runs the pinned scope check.

Use `--replace` only when the owner explicitly wants to reauthorize an
existing task, and do that on the trusted base **before agent work**.
If the new approval is identical, the command is a no-op. A dirty worktree,
untracked file, invalid scope, or unapproved overwrite fails closed.

The default test glob patterns include `tests/**`, `**/test_*.py`, JavaScript
`*.test.js`, and TypeScript `*.spec.ts`; override with repeated
`--test-path` flags. The allowlist remains mandatory and deny-test-deletions
is enabled. Additional protected paths are optional because all non-allowed
changes already fail.

## What this actually saves

No hand-edited task-contract JSON, no manual SHA transfer into CI, no
separate Sentinel virtual environment for the GitHub PR check, and no new
Sentinel CLI invocation when the PR opens. The owner still must make the
approval decision, push it to the protected base, and maintain the required
check. This prototype is not a bot, GitHub App, or fully automatic per-task
approval service.

## Trust limitation to resolve before claiming enforcement

The generated workflow uses ordinary `pull_request` and must be protected by
repository rules. A coding agent able to replace workflow code or GitHub check
requirements can undermine enforcement. Branch protection / organization
ruleset configuration is **not automated or verified** by `setup`. The Action
checks **post-change Git scope only**; it cannot prevent side effects, approve
source changes, or prove task correctness.

Importantly, an agent that controls the PR base commit or can rewrite its
contract can change what Sentinel treats as approved. In production the owner
must keep the PR base, trusted checker and CI configuration independently
controlled. A PASS alone is not a security certification.

**Concurrency limitation:** this first prototype uses one `.sentinel/contract.json`
in the target base branch. Concurrent tasks that require different scopes can
interfere when the base advances. We have not yet built a protected task-specific
approval ledger or tested rebase/retarget behavior; do not present this as a
multi-PR enterprise workflow.

## Qualification criteria

- `setup` creates only the trusted PR workflow and refuses a dirty repository
  or overwrite.
- `approve` commits only a valid policy and rejects dirty/invalid/replacement
  mistakes.
- Actual Git operations with the approved base yield PASS for authorized edits
  and FAIL for protected/out-of-scope edits.
- Standard package Linux/Windows CI and Action smoke tests pass.
- A separate real PR integration trial is required before claiming that
  GitHub organization rules reliably enforce the generated status check.

Success targets (not established adoption metrics): one-time setup under
five minutes, task authorization under 30 seconds, automatic PR checking.

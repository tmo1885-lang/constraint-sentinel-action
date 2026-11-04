# CS-UX-02 — per-task approvals without touching main

**Status:** prototype only. Not a published release, production gate, or security
certification. PR to review; do not install the generated CI workflow in a
sensitive repository until its threat model and branch rules have been reviewed.

## What changed from CS-UX-01

With CS-UX-01, the task contract was committed to the main PR base branch for
each task. That was unnecessarily awkward and prevented unrelated concurrent
tasks from having independent scopes.

CS-UX-02 writes each approved task contract to a distinct record in the
`sentinel-approvals` Git branch. A task branch starts from the existing source
baseline. There is **no task-approval commit on main**, no JSON editing, and no
SHA entry by the developer during normal task creation.

### Start a task

On a **clean, owner-controlled checkout** of the intended target branch:

```sh
constraint-sentinel task start \
  --branch task/vgr-m4-import \
  --task VGR-M4-import \
  --allow src/vgr/cli.py \
  --allow tests/test_cli_m4.py \
  --protect src/vgr/search_execution.py
```

The command validates the contract, appends a record to
`refs/heads/sentinel-approvals` (without checking it out in the normal
worktree), and creates the coding branch. The source baseline stays unchanged.
Different tasks receive different approved scopes.

**For a real remote-backed workflow**, first configure a trusted owner-only
approval branch and its protection rules; then use `--publish` so the approval
is successfully pushed to that branch *before* the coding branch is created.
The command never silently creates an unprotected security boundary:
the owner must establish and check GitHub protections independently.

### Check before opening a PR

```sh
constraint-sentinel task check \
  --approval-ref refs/heads/sentinel-approvals
```

This checks the current branch against its approved base without typing a SHA.
It is a **local convenience check, not a security boundary**: the agent may be
able to modify refs in the same local Git repository.

For separation, the verifier can read the policy from a separately controlled
owner checkout:

```sh
constraint-sentinel task check \
  --approval-repo /path/to/trusted-owner-approvals \
  --approval-ref HEAD \
  --branch task/vgr-m4-import
```

The owner must prevent the agent from altering that checkout or its remote
approval source. The check fails closed on a missing record, a wrong branch
binding, an inconsistent baseline, and an out-of-scope change.

### One-time automatic PR setup (experimental)

```sh
constraint-sentinel task setup-ci --checker-sha FULL_REVIEWED_COMMIT_SHA
```

This generates `.github/workflows/sentinel-task-scope.yml` on the owner's
trusted base branch. The **one-time** immutable SHA must be that of a reviewed
checker release that includes CS-UX-02; v0.1.0b3 is *not* such a release.
Do not use PR #9's unreviewed head as a security gate.

The generated workflow uses `pull_request_target` with read-only contents
permission. It rejects forks in an explicit step, checks the PR head out as
*data* with credentials not persisted, independently checks out the GitHub
repository's owner-protected `sentinel-approvals` branch, and invokes a pinned
checker that never executes candidate code or required-check commands.

The workflow still requires human setup of the allowed writers on the approval
branch, protection of the base branch and workflow, and required status checks.
These settings are **not** configured or audited by the prototype. Running
untrusted code, adding write permissions, or giving the agent access to the
approval branch would defeat this design.

## What is still inconvenient

- Owner must select approved paths and issue the approval before the agent starts.
- The GitHub approval branch must be created, secured, and kept owner-only.
- A protected approval must be pushed before agent activity.
- PRs targeting a base commit different from the approved baseline fail closed.
  A rebase or base advancement requires fresh owner authorization.
- Only same-repository task branches are supported in this prototype.
- No GitHub App/UI, task-path picker, automatic ruleset configuration, or
  independent production security review exists yet.
- A candidate that can control GitHub Actions settings, workflow or branch
  protection can invalidate assurances. GitHub `pull_request_target` workflows
  must never execute PR-supplied scripts or credentials-bearing candidate code.
- Sentinel still only checks post-change Git scope, not external effects or
  semantic correctness.

## Qualification

- 14 focused CS-UX-02 tests cover independent task scopes, unchanged main,
  protected-file violations, missing/tampered approvals, base mismatch, and
  separate owner/candidate checkouts.
- Hosted CI adds a synthetic Action smoke case for separate-owner-checkout
  approval: authorized commit PASS, then protected payment change FAIL.
- An actual repository replay and a live protected PR check are separately
  required before claiming daily-use readiness.
- Trial results should capture *total* owner setup, approval, push and review
  time, not just command execution time.

**Decision criterion:** Does the owner prefer this to a plain Git diff review,
and does an ordinary coding task get through without repeated manual policy
maintenance? If not, simplify rather than expanding configuration.

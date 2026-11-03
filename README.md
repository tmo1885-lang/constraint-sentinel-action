# Constraint Sentinel

**Independent task-scope verification for AI-assisted development.**

[![Status: experimental beta](https://img.shields.io/badge/status-experimental%20beta-334155)](docs/VALIDATION_STATUS.md)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-334155)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-16856b)](LICENSE)

An open-source GitHub Action and Python CLI from **Velorin Intelligence**. Constraint Sentinel checks whether a coding agent's **resulting file changes** remained within boundaries approved at an earlier, trusted Git commit.

**Experimental beta · Independent verification · Volunteers welcome**

[Get started](#quick-start-github-actions) · [How it works](#how-it-works) · [Test evidence](docs/VALIDATION_STATUS.md) · [Beta testing](docs/BETA_TESTING.md) · [Security limitations](SECURITY.md)

> **Scope of assurance:** We have validated specific Git operations through synthetic tests and one limited real coding-agent workflow. This is *post-change scope verification*, not a sandbox, pre-execution guard, security certification, task-completion guarantee, or substitute for human review.

Constraint Sentinel is designed to complement existing CI and [Agent Quality Gates](https://github.com/deeppatternai/agent-quality-gates) (AQG). It is **unofficial** and has no affiliation with or endorsement from AQG.

## How it works

| Step | Owner / agent | Independent verification |
| --- | --- | --- |
| **01 — Define** | Owner approves permitted and protected paths in a Git commit | Policy is pinned to the trusted baseline |
| **02 — Work** | A coding agent changes files normally | No interruption or false claim of runtime blocking |
| **03 — Check** | Sentinel inspects the resulting Git state | In-scope edit: PASS; out-of-scope edit: FAIL |
| **04 — Review** | Developer reviews the change and required tests | Correctness and task completion remain **unverified** |

## Why it exists

Coding agents sometimes change files outside their assignment. Sentinel checks the *actual resulting Git changes* against file boundaries the project owner approved **before** those edits.

A report separates what can be observed from what cannot:

~~~text
Constraint Sentinel gate: PASS
Git scope: PASS
Required checks: not_configured
Task completion: NOT VERIFIED
~~~

If a payment file changes during an approved cart-only task, the scope gate fails and identifies the protected path. A passing scope check never means the implementation is correct.

Example: a coding agent is assigned to update checkout calculations and tests, but payment processing code and migrations must not change.

## What it checks

- Git additions, modifications, deletions, and renames, including nonignored untracked files.
- Approved allow/protect patterns; protection takes precedence.
- Attempts to change task contracts or CI workflows.
- Test-file deletion and uniquely attributable exact-content unstaged test renames.
- Git index flags that can conceal local changes.
- **Optional** inventory of ignored untracked protected paths.
- **Optional** baseline-approved test commands and structured test-integrity reports.

Sentinel does not detect every weakened test assertion, monitor external side effects, or block commands before execution. A PASS means the configured Git-scope gate passed; the software change could still be incorrect or unsafe.

## Quick start: GitHub Actions

**Prerequisite:** The target repository must already contain an approved .sentinel/contract.json in the **trusted base commit** before the agent edits files.

Example contract (customize for your actual task):

~~~json
{
  "schema_version": 1,
  "task_id": "checkout-calculation-update",
  "allow": ["src/cart/**", "tests/**"],
  "protect": ["src/payments/**", "db/migrations/**"],
  "test_paths": ["tests/**"],
  "deny_test_deletions": true,
  "required_checks": []
}
~~~

To use the published beta, put this workflow in the target repository:

~~~yaml
name: Verify AI task scope
on:
  pull_request:

permissions:
  contents: read

jobs:
  scope:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Check approved task scope
        uses: tmo1885-lang/constraint-sentinel-action@v0.1.0b1
        with:
          base: ${{ github.event.pull_request.base.sha }}
          audit-ignored-protected: "true"
~~~

**Security note:** The example uses the versioned beta tag for readability. For stronger supply-chain control, replace `v0.1.0b1` with the exact reviewed **40-character commit SHA** from the release. Do not use a moving branch as a production trust anchor.

The checker must be installed from an **owner-trusted source**. A passing GitHub Action is useful only when repository administrators make it a required status check and protect the trusted baseline and task contract from the coding agent.

## Run locally

Requires Python 3.11+ and Git. From a trusted checkout of the release source:

~~~sh
python3 -m pip install .
# In the target Git repo, after approving and committing its task contract:
constraint-sentinel check --base OWNER_APPROVED_BASE_SHA --audit-ignored-protected
~~~

If the contract declares required checks, add --run-checks **only in an isolated environment**, since test commands may execute untrusted candidate code.

Exit codes: 0 = configured gate passed; 1 = failed or unverified; 2 = invalid input or tool error. Use --format json or --report for machine-readable evidence. To compare commits instead of a worktree, use --head CANDIDATE_SHA; it cannot audit untracked files or run checks.

## Works alongside AQG

Run Sentinel as a **separate check** alongside AQG's engineering evidence and workflow checks. Neither replaces the other, and this package is **not an official AQG integration**. See [AQG companion notes](docs/AQG_COMPANION.md).

## Known limitations

- **Post-change only:** unauthorized file changes may already have occurred.
- **No universal semantic verification:** it cannot judge arbitrary test assertion quality or program correctness. An optional, separately installed [Proof of Done](https://github.com/wasaybuilds/proof-of-done) adapter covers some recognized test-integrity changes.
- **External state unseen:** network calls, secrets read, remote changes, and process side effects are outside its audit.
- **Trust is external:** a malicious or misconfigured agent that controls the verifier, baseline, policy or required CI can bypass the gate.
- **Ignored path auditing is optional** and may flag files that existed before the coding task.
- **Task completion is always explicitly unverified.**
- Only a limited set of Git states, languages and environments has been tested.

Read [security and scope limitations](SECURITY.md) and the [specific validation results and gaps](docs/VALIDATION_STATUS.md) before testing.

## Seeking volunteer beta testers

We welcome developers who use Copilot, Codex, Claude Code or similar assistants to try Sentinel in a **disposable, non-sensitive Git repository**.

We particularly want reports of false positives, missed scope violations, setup friction, confusing output, or cases where existing CI is better. **Negative findings are useful.** Participation is voluntary; no compensation is offered or implied.

Please read the [volunteer testing guide](docs/BETA_TESTING.md) and use GitHub Issues after the repository is released. **Never submit credentials, proprietary source, sensitive logs, private repo URLs, or customer information.** For sensitive security findings, follow [SECURITY.md](SECURITY.md).

## License and project status

[MIT licensed](LICENSE) · © 2026 Velorin Intelligence.

**Experimental beta.** Independent verification is limited to the documented behaviors and environments. This is a community testing release, not a maintained enterprise security service. Please [report what does not work](docs/BETA_TESTING.md).

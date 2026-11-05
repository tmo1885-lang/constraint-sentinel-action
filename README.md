# Constraint Sentinel

**Experimental research · Development paused · Beta recruitment closed (November 2026).**

> **Project status:** Constraint Sentinel remains public for reproducibility, but active product development and volunteer beta recruitment have ended. Controlled experiments verified specific Git-scope and test-execution behaviors; comparisons with existing tools and simpler project-specific CI did **not** establish enough incremental practical value to justify continued development. The last published beta, **v0.1.0b3**, is a historical experimental release—not a maintained product or production security control. [Read the research findings](#why-development-was-paused) and [validation record](docs/VALIDATION_STATUS.md).

**Release notice.** The v0.1.0b1 Action can return success without running the trusted checker when Python imports a same-named module from the candidate checkout. Retire v0.1.0b1 and the earlier `660a778` Action pin as merge gates. The v0.1.0b2 launcher isolates Python startup. **v0.1.0b3** retains that isolation and adds narrowly scoped Windows CRLF test-move recovery; it is still experimental.

[![Status: research paused](https://img.shields.io/badge/status-research%20paused-6b7280)](#why-development-was-paused)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-334155)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-16856b)](LICENSE)

An open-source GitHub Action and Python CLI from **Velorin Intelligence**. Constraint Sentinel checks whether a coding agent's **resulting file changes** remained within boundaries approved at an earlier, trusted Git commit.

**Research paused · Historical experimental beta · Not seeking testers**

[Research finding](#why-development-was-paused) · [How it works](#how-it-works) · [Test evidence](docs/VALIDATION_STATUS.md) · [Historical beta guide](docs/BETA_TESTING.md) · [Security limitations](SECURITY.md)

> **Scope of assurance:** We have validated specific Git operations through synthetic tests and bounded internal coding-agent workflows. This is *post-change scope verification*, not a sandbox, pre-execution guard, security certification, task-completion guarantee, or substitute for human review.

Constraint Sentinel is designed to complement existing CI and [Agent Quality Gates](https://github.com/deeppatternai/agent-quality-gates) (AQG). It is **unofficial** and has no affiliation with or endorsement from AQG.

## Why development was paused

The original file-scope verifier mechanically checked changes against a previously approved Git baseline, but an ordinary Git/Python script could reproduce much of that detection. Later research prototypes detected missing or unexecuted tests and silently disappearing pytest cases. Those additions did not establish that the correct tests were required or that their assertions proved task completion; a small project-specific CI check often detected the same selected failures with less overhead when expected tests were known.

In retrospective replays of real coding work, no independent defect was discovered in an untouched agent-authored change. Stronger negative cases were deliberately constructed and remain labeled as such. Running test code also introduces unsandboxed execution and additional trust requirements. **No sufficient incremental practical or commercial value was established.** The project is preserved as a transparent negative research result, not offered as an actively maintained security or quality service.

The unmerged [test-execution research](https://github.com/tmo1885-lang/constraint-sentinel-action/pull/12), [AQG companion comparison](https://github.com/tmo1885-lang/constraint-sentinel-action/pull/13), and [collection-loss findings](https://github.com/tmo1885-lang/constraint-sentinel-action/pull/14) document the limits. These are **draft research branches**, not features of the published beta or an official AQG partnership.

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
- Test-file deletion and uniquely attributable exact-content unstaged test renames, plus separately reported CRLF checkout-equivalent moves when supported by pinned Git configuration/attributes.
- Git index flags that can conceal local changes.
- **Optional** inventory of ignored untracked protected paths.
- **Optional** baseline-approved test commands and structured test-integrity reports.

Sentinel does not detect every weakened test assertion, monitor external side effects, or block commands before execution. A PASS means the configured Git-scope gate passed; the software change could still be incorrect or unsafe.

## Historical GitHub Actions example (experimental; not recommended as a production gate)

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

For historical reproducibility in a **disposable, non-sensitive repository only**, this was the workflow for the published experimental beta:

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
        uses: tmo1885-lang/constraint-sentinel-action@v0.1.0b3
        with:
          base: ${{ github.event.pull_request.base.sha }}
          audit-ignored-protected: "true"
~~~

For an immutable Action pin, use `8f3fb1c8cb7629f24f9d0baefad6ff298e205aa6` (the v0.1.0b3 release commit). Do **not** pin v0.1.0b1 as an enforcement gate.

The checker must be installed from an **owner-trusted source**. A passing GitHub Action is useful only when repository administrators make it a required status check and protect the trusted baseline and task contract from the coding agent.

## Historical local evaluation

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

## Beta recruitment closed

**We are no longer seeking volunteer beta testers or accepting applications for a testing program.** Thank you to developers who contributed independent feedback, including negative findings. The [historical testing protocol](docs/BETA_TESTING.md) and [closed feedback issue #1](https://github.com/tmo1885-lang/constraint-sentinel-action/issues/1) are retained as evidence, not invitations to participate.

Existing security-sensitive findings should be reported privately according to [SECURITY.md](SECURITY.md). Ordinary issues may still document factual errors in the research record, but there is no active product roadmap, guaranteed support, issue-response schedule, or commitment to release fixes.

## License and project status

[MIT licensed](LICENSE) · © 2026 Velorin Intelligence.

**Research paused (November 2026).** Published v0.1.0b3 remains an experimental historical artifact. Independent verification was limited to the documented behaviors and environments; the project is **not** a maintained enterprise product, certified security control, or an active community beta. No further beta testers are being recruited.

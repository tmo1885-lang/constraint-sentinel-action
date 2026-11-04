# What has actually been validated

**Experimental v0.1.0b3 release. This is not a security certification.**

## Validated behavior and provenance

| Environment | Reported behavior | Evidence |
| --- | --- | --- |
| Windows 11, Python 3.12 (independent local run) | 64 tests run; 62 pass; 2 expected platform skips | Clean checkout of reviewed fix, including CRLF tests |
| Windows 11, Python 3.13 (`core.autocrlf=true`, external volunteer retest) | 64 tests run in 89.415s; 62 pass; 2 expected Windows platform skips; 0 failures and 0 errors, as reported by the tester | @Rohank143's [v0.1.0b3 release-commit retest](https://github.com/tmo1885-lang/constraint-sentinel-action/issues/1#issuecomment-6628984461), commit `8f3fb1c` |
| Linux, Python 3.14 (independent Codespace run) | 64 tests pass | Clean checkout of reviewed fix |
| GitHub-hosted Linux, Python 3.11 / 3.12 / 3.14 | 64 tests per job pass | Merged fix CI, [run 41715634959](https://github.com/tmo1885-lang/constraint-sentinel-action/actions/runs/41715634959) |
| GitHub-hosted Windows, Python 3.12 | Hosted job passed on v0.1.0b3 release-preparation branch | [run 41718579138](https://github.com/tmo1885-lang/constraint-sentinel-action/actions/runs/41718579138) |

The volunteer's November 4, 2026 retest specifically reports PASS for `test_unstaged_test_rename_with_identical_content_is_allowed` and `test_crlf_difference_with_autocrlf_disabled_is_blocked`, with the two platform-specific tests skipping as intended. This is an externally reported regression result on the published release commit, not a maintainer-observed run or a general security certification.

The volunteer beta report by @Rohank143 independently exposed three Windows-specific failures. We reproduced them (59 tests: one failure and two errors), checked the contributor's original patch, and found an additional security-relevant regression: unconditional CRLF normalization could accept byte-different tests as exact-content moves even when conversion was disabled.

The revised implementation retains raw-byte matching; a **distinct** `git_checkout_crlf_match` outcome requires `core.autocrlf=true`, pinned-baseline attributes allowing CRLF conversion, a pure-LF non-binary source, and an exact CRLF-translated destination. Negative tests cover disabled translation, differing content, explicit binary attributes, and ambiguous matches. A successful Git scope check still cannot prove semantic preservation.

The composite GitHub Action has also been exercised on a **disposable synthetic repository**. Hosted checks cover an allowed source edit, rejecting a protected payment modification and a deleted test, an opt-in ignored-protected-path check, and a candidate-module-shadowing regression. The launcher isolation fix was released in v0.1.0b2.

An earlier limited GitHub Copilot CLI coding task and comparisons against open-source tools were conducted separately during internal development. Neither represents general runtime enforcement.

On November 4, 2026, an additional [five-scenario internal GitHub Copilot CLI pilot](CS_PILOT_01_20261104.md) produced five expected scope classifications on separate disposable Git worktrees: two authorized scenarios passed and three deliberately out-of-scope scenarios failed. This is agent-driven but intentionally scripted, not an estimate of spontaneous agent drift or general real-world accuracy. The pilot also exposed a [non-security version-reporting mismatch](https://github.com/tmo1885-lang/constraint-sentinel-action/issues/6) in the v0.1.0b3 CLI banner.

## Known limits and unvalidated claims

- Post-change Git checks cannot prevent unauthorized edits *before* execution, stop network side effects, or prove task completion.
- Semantic test weakening and external state changes are outside ordinary path-based verification.
- No representative adoption metrics, accuracy estimates, enterprise assessment or security certification has been established.
- The host, branch protection, trusted baseline, verifier and policy must remain outside the coding agent's control.
- These checks sample specific Git states and environments, not arbitrary codebases or malicious privileged runners.
- The project has not undergone independent broad security review; a GitHub-hosted test pass is not an attestation.

## What feedback would change our judgment?

A useful beta report contains a small **synthetic** reproduction where a legitimate change failed or an out-of-scope change passed. Please include Git settings, Python/Git versions and operating system; do not include sensitive code, credentials or private logs.

**Evidence provenance:** Verified runs described above are limited to the named commits and environments. Releasing a new version does not add security guarantees beyond the tested cases.

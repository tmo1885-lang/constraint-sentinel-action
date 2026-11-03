# What has actually been validated

**Experimental v0.1.0b3 candidate. This is not a security certification.**

## Validated behavior and provenance

| Environment | Reported behavior | Evidence |
| --- | --- | --- |
| Windows 11, Python 3.12 (independent local run) | 64 tests run; 62 pass; 2 expected platform skips | Clean checkout of reviewed fix, including CRLF tests |
| Linux, Python 3.14 (independent Codespace run) | 64 tests pass | Clean checkout of reviewed fix |
| GitHub-hosted Linux, Python 3.11 / 3.12 / 3.14 | 64 tests per job pass | Merged fix CI, [run 41715634959](https://github.com/tmo1885-lang/constraint-sentinel-action/actions/runs/41715634959) |
| GitHub-hosted Windows, Python 3.12 | Hosted job passed on v0.1.0b3 release-preparation branch | [run 41718579138](https://github.com/tmo1885-lang/constraint-sentinel-action/actions/runs/41718579138) |

The volunteer beta report by @Rohank143 independently exposed three Windows-specific failures. We reproduced them (59 tests: one failure and two errors), checked the contributor's original patch, and found an additional security-relevant regression: unconditional CRLF normalization could accept byte-different tests as exact-content moves even when conversion was disabled.

The revised implementation retains raw-byte matching; a **distinct** `git_checkout_crlf_match` outcome requires `core.autocrlf=true`, pinned-baseline attributes allowing CRLF conversion, a pure-LF non-binary source, and an exact CRLF-translated destination. Negative tests cover disabled translation, differing content, explicit binary attributes, and ambiguous matches. A successful Git scope check still cannot prove semantic preservation.

The composite GitHub Action has also been exercised on a **disposable synthetic repository**. Hosted checks cover an allowed source edit, rejecting a protected payment modification and a deleted test, an opt-in ignored-protected-path check, and a candidate-module-shadowing regression. The launcher isolation fix was released in v0.1.0b2.

An earlier limited GitHub Copilot CLI coding task and comparisons against open-source tools were conducted separately during internal development. Neither represents general runtime enforcement.

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

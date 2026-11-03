# Changelog

All notable changes to Constraint Sentinel are recorded here.

## 0.1.0b3 — Experimental Windows compatibility correction (2026-11-03)

**Status: experimental; this patch does not certify the checker as a security boundary.**

- Fix Windows false-positive test-deletion reports for legitimate unstaged test moves affected by Git checkout CRLF conversion.
- Preserve strict raw-byte identity by default; separately label `git_checkout_crlf_match` only when pinned-baseline Git attributes and explicit `core.autocrlf=true` support the translation. Uncertain, changed, binary, custom-filtered and ambiguous cases remain blocked.
- Fix test portability: skip newline-in-filename fixtures on Windows, and skip symlink fixtures only for expected unsupported/privilege errors.
- Add five negative/positive regression tests (64 total) and a Windows-hosted Python 3.12 CI job alongside Linux Python 3.11, 3.12 and 3.14.
- Credit @Rohank143 for volunteer Windows testing and the initial proposed correction in PR #2; the conservatively scoped fix was merged as PR #4.

Validation is limited to documented synthetic behavior, including real Windows and Linux runs and hosted CI. It does not prove semantic test preservation or agent containment.

## 0.1.0b2 — Experimental launcher correction (2026-11-03)

- Corrected the v0.1.0b1 composite Action launcher: an attacker-controlled candidate checkout could shadow the verifier's Python module and cause a false pass. The Action now isolates the Python launcher and loads code from the trusted Action path.
- Earlier v0.1.0b1 pins should not be used as merge gates. This release predates the Windows CRLF correction.


## 0.1.0b1 — Experimental beta (2026-11-02)

**Status: experimental.** This is a limited developer preview, not a hardened or certified security product. Independent volunteer testing is invited.

### Included

- Owner-approved per-task Git allow/protect contracts, read from a trusted baseline commit.
- Post-change audit of tracked changes, staged/unstaged edits, untracked files, and configured protected paths.
- Conservative test deletion handling and safe recovery of uniquely identifiable exact-content test moves.
- Optional audit of Git-ignored protected files and Git index flags that may conceal local changes.
- JSON or human-readable outcome reports, with task completion explicitly not verified.
- Optional trusted-baseline check commands and a bounded, structured Proof of Done result adapter.
- Standalone Python CLI and GitHub composite Action.
- Synthetic GitHub Actions checks and beta volunteer feedback templates.

### Validation

- 59 focused regression tests passed on GitHub-hosted Linux with Python 3.11, 3.12 and 3.14.
- Composite Action passed the approved-change case and rejected test removal, protected payment edits, and ignored protected files in a disposable fixture.
- A limited real coding-agent patch and additional synthetic comparisons were completed during private development. These do not establish production reliability.

### Limits

Sentinel checks the Git state **after** edits occur. It cannot prevent commands, attest its own executable integrity, prove semantic correctness or task completion, or monitor remote side effects. Trust requires independently controlled source, policy, base commit, and CI enforcement.

For details, see [specific validation findings](docs/VALIDATION_STATUS.md) and [security limitations](SECURITY.md).

This release candidate is a separate public distribution artifact. Private research history and evaluation materials are intentionally not included.

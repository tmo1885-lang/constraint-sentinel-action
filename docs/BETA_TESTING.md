# Historical volunteer beta testing guide — recruitment closed

**Status (November 2026): Research paused; volunteer beta recruitment closed.** This document preserves the historical evaluation procedure; it is **not a current invitation to test**, and no maintenance or feedback-response commitment is offered. The last released experimental beta was **v0.1.0b3** ([release](https://github.com/tmo1885-lang/constraint-sentinel-action/releases/tag/v0.1.0b3)). It requires a *precommitted owner task contract*; the lower-friction task commands in draft PRs #8/#9 are **not part of this release**. Never use the historical beta as a production security gate.

During the volunteer beta, we invited developers using Copilot, Codex, Claude Code, and other coding assistants to report reproducible problems, including negative findings. That recruitment has ended.

## Historical 15–30 minute evaluation procedure

1. Use a **disposable, non-sensitive Git repository** with no confidential code, credentials, customer data or production access.
2. Start with a simple, useful task (e.g. refactor a calculation, update a harmless utility, or add tests).
3. Before the agent edits anything, approve and commit a task contract identifying which paths can and cannot change. Keep its baseline SHA independently.
4. Ask your normal coding agent to make the change.
5. Run Sentinel against that same approved baseline SHA and record whether it correctly classified the resulting edits.
6. Try a deliberately unauthorized edit in a **separate disposable fixture** to see whether your setup catches it. Do not test on real sensitive files.
7. Historically, participants documented false positives, false negatives, setup problems and unclear explanations. The recruitment period has now ended.

You can also test without a coding agent using a disposable Git repository and the [README's approved task-contract example](../README.md#quick-start-github-actions).

### Version and installation notes

- For the published release, use the [v0.1.0b3 tag](https://github.com/tmo1885-lang/constraint-sentinel-action/tree/v0.1.0b3) or immutable source commit `8f3fb1c8cb7629f24f9d0baefad6ff298e205aa6`. Install the checker from that trusted source; do not treat an agent-edited checkout as the verifier.
- **Do not use v0.1.0b1 as a required merge gate.** Its Action launcher could report success without executing the trusted checker. The v0.1.0b3 launcher includes the isolation repair.
- The **v0.1.0b3** package can show **0.1.0b2** for `constraint-sentinel --version` because of a corrected-but-unreleased *display* mismatch ([issue #6](https://github.com/tmo1885-lang/constraint-sentinel-action/issues/6)). Verify the source tag/commit, not the CLI banner.
- Expect some setup time: you must select allowed paths, commit the contract **before** agent edits, and keep the baseline SHA independently. Please report whether this effort was worthwhile even if Sentinel reports PASS.
- The simpler `task start` / task-approval ledger and automatic protected-PR prototype are under review in [PR #9](https://github.com/tmo1885-lang/constraint-sentinel-action/pull/9). They are **unreleased and not approved for multi-writer security enforcement**.

## Questions used in the beta evaluation

- Which coding agent, programming language and operating system did you use?
- How long did installation and task-contract setup take?
- Did the result agree with what you expected? What was flagged or missed?
- Was an ordinary legitimate rename or test edit incorrectly rejected?
- Did this add value beyond normal Git diff review, existing CI and agent permissions?
- Would you choose to use it again without being asked?
- What is one concrete improvement that would make it less annoying or more reliable?

**Do not upload raw prompts, complete private code, credentials, employee data, customer information, or private repository addresses.** File paths and worktree reports may disclose project details: redact them before sharing.

### Historical volunteer terms

Participation during the beta was voluntary and unpaid. Negative findings were welcomed, and developers were cautioned not to submit private or identifying material. No commercial maintenance or support commitment emerged from the evaluation.

## Closed recruitment and historical results

The [beta feedback issue #1](https://github.com/tmo1885-lang/constraint-sentinel-action/issues/1) is closed to new recruitment and retained for provenance. The project remains public as a research record; we are **not requesting new beta evaluations or promising future development**. If you identify a potentially sensitive vulnerability, follow [SECURITY.md](../SECURITY.md) rather than posting exploit details. Do not request access to private engineering or research repositories.

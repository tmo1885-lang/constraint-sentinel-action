# Volunteer beta testing — your feedback is welcome

**Status:** Public experimental beta, currently **v0.1.0b3** ([release](https://github.com/tmo1885-lang/constraint-sentinel-action/releases/tag/v0.1.0b3)). Please use only a disposable, non-sensitive test repository. The published beta requires a *precommitted owner task contract*; the lower-friction task commands in draft PRs #8/#9 are **not part of this release**.

We are looking for developers who already use Copilot, Codex, Claude Code or another AI coding assistant. The goal is to find problems, not gather endorsements.

## A safe 15–30 minute evaluation

1. Use a **disposable, non-sensitive Git repository** with no confidential code, credentials, customer data or production access.
2. Start with a simple, useful task (e.g. refactor a calculation, update a harmless utility, or add tests).
3. Before the agent edits anything, approve and commit a task contract identifying which paths can and cannot change. Keep its baseline SHA independently.
4. Ask your normal coding agent to make the change.
5. Run Sentinel against that same approved baseline SHA and record whether it correctly classified the resulting edits.
6. Try a deliberately unauthorized edit in a **separate disposable fixture** to see whether your setup catches it. Do not test on real sensitive files.
7. Report any false positives, false negatives, setup problems or unclear explanations.

You can also test without a coding agent using a disposable Git repository and the [README's approved task-contract example](../README.md#quick-start-github-actions).

### Version and installation notes

- For the published release, use the [v0.1.0b3 tag](https://github.com/tmo1885-lang/constraint-sentinel-action/tree/v0.1.0b3) or immutable source commit `8f3fb1c8cb7629f24f9d0baefad6ff298e205aa6`. Install the checker from that trusted source; do not treat an agent-edited checkout as the verifier.
- **Do not use v0.1.0b1 as a required merge gate.** Its Action launcher could report success without executing the trusted checker. The v0.1.0b3 launcher includes the isolation repair.
- The **v0.1.0b3** package can show **0.1.0b2** for `constraint-sentinel --version` because of a corrected-but-unreleased *display* mismatch ([issue #6](https://github.com/tmo1885-lang/constraint-sentinel-action/issues/6)). Verify the source tag/commit, not the CLI banner.
- Expect some setup time: you must select allowed paths, commit the contract **before** agent edits, and keep the baseline SHA independently. Please report whether this effort was worthwhile even if Sentinel reports PASS.
- The simpler `task start` / task-approval ledger and automatic protected-PR prototype are under review in [PR #9](https://github.com/tmo1885-lang/constraint-sentinel-action/pull/9). They are **unreleased and not approved for multi-writer security enforcement**.

## Questions we'd like answered

- Which coding agent, programming language and operating system did you use?
- How long did installation and task-contract setup take?
- Did the result agree with what you expected? What was flagged or missed?
- Was an ordinary legitimate rename or test edit incorrectly rejected?
- Did this add value beyond normal Git diff review, existing CI and agent permissions?
- Would you choose to use it again without being asked?
- What is one concrete improvement that would make it less annoying or more reliable?

**Do not upload raw prompts, complete private code, credentials, employee data, customer information, or private repository addresses.** File paths and worktree reports may disclose project details: redact them before sharing.

### Volunteer terms

Participation is voluntary. No paid compensation is being offered or promised. You can stop at any point, and negative feedback is as valuable as praise. We may summarize anonymous feedback in development notes; we will not publicly attribute your comments without asking.

This is early-stage research. We cannot promise that reported issues will be fixed or that the tool will become a maintained commercial product.

## Where to submit results

Use the [public beta feedback issue](https://github.com/tmo1885-lang/constraint-sentinel-action/issues/1) or the [GitHub issue templates](https://github.com/tmo1885-lang/constraint-sentinel-action/issues/new/choose). For potentially sensitive vulnerabilities, follow [SECURITY.md](../SECURITY.md) rather than posting exploit details. Do not request access to private engineering or research repositories.

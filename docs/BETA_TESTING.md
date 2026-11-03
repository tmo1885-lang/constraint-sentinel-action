# Volunteer beta testing — your feedback is welcome

**Status:** Experimental beta. Volunteer testers are welcome after the public GitHub repository and release reference are available. Please use only a disposable, non-sensitive test repository.

We are looking for developers who already use Copilot, Codex, Claude Code or another AI coding assistant. The goal is to find problems, not gather endorsements.

## A safe 15–30 minute evaluation

1. Use a **disposable, non-sensitive Git repository** with no confidential code, credentials, customer data or production access.
2. Start with a simple, useful task (e.g. refactor a calculation, update a harmless utility, or add tests).
3. Before the agent edits anything, approve and commit a task contract identifying which paths can and cannot change. Keep its baseline SHA independently.
4. Ask your normal coding agent to make the change.
5. Run Sentinel against that same approved baseline SHA and record whether it correctly classified the resulting edits.
6. Try a deliberately unauthorized edit in a **separate disposable fixture** to see whether your setup catches it. Do not test on real sensitive files.
7. Report any false positives, false negatives, setup problems or unclear explanations.

You can also run a deterministic sample without an AI agent. See the release's example contract and the small example-generation script (when released).

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

Use the public repository's GitHub Issues and the beta feedback template. For potentially sensitive vulnerabilities, follow SECURITY.md rather than posting exploit details. Do not request access to private engineering or research repositories.

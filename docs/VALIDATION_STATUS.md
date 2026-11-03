# What has actually been validated

**Experimental preview candidate v0.1.0b1. This is not a security certification.**

## Reproducible checks

In the private staging workflow, the beta Python distribution was installed and its focused Git behavior suite was run on hosted Linux under:

| Environment | Unit/behavior tests | Package installation |
| --- | --- | --- |
| Python 3.11 | 59 passed | Passed |
| Python 3.12 | 59 passed | Passed |
| Python 3.14 | 59 passed | Passed |

The composite GitHub Action was also executed against a **disposable synthetic Git repository**. The approved baseline contained a task contract and a non-dangerous required check.

| Synthetic outcome | Observed |
| --- | --- |
| Valid changed cart file within approved scope | PASS |
| Modified protected payment gateway | FAIL (protected_path) |
| Deleted existing test file | FAIL (test_removed) |
| Created ignored protected file | FAIL (ignored_protected_path) |
| Configured required fixture check after scope passed | PASS |
| Required checks when Git scope already failed | Skipped as expected |
| Task-completion assessment | Always NOT VERIFIED |

An earlier internal engineering run used the same core checker in a **real GitHub Copilot CLI coding task** with prewritten acceptance tests, but that is not proof of runtime enforcement or representative real-world reliability.

Previous controlled experiments also compared this scope checker against open-source AQG, Proof of Done, and a small independently written Git/Python reference. A hardened DIY checker matched the tool's selected committed-case path coverage, highlighting the absence of a unique detection algorithm.

## What we have NOT validated

- Real-world correctness across broad developer projects, codebases, languages or operating systems other than the hosted Linux tests.
- A fully adversarial live agent with access to the verifier, branch protection settings, or privileged runner.
- Prevention of unauthorized edits before they occur.
- External side effects, data exfiltration, secrets exposure, or arbitrary semantic test weakening.
- Hosted binary identity attestation, immutable self-verification, or secure customer deployment.
- Accuracy statistics, independent volunteer adoption, or enterprise safety requirements.
- GitHub Marketplace uniqueness, terms, or a published release.

## What feedback would change our judgment?

A useful beta report contains a small *synthetic* reproduction where a legitimate task failed or an out-of-scope change passed. Setup time and user understanding matter as much as raw detection. Negative evidence is welcome.

**Evidence provenance:** These checks were run on a private staging branch before public distribution. Releasing this project does not provide production-security certification, Marketplace endorsement, or any guarantee beyond the tested cases.

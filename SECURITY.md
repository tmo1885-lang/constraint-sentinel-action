# Security policy and limitations

**Experimental preview. Not certified or approved for security-critical use.**

Constraint Sentinel is a post-change Git scope checker, not an agent sandbox or a preventative security boundary. It **cannot guarantee** that an AI coding assistant acts safely, completes its task correctly, or avoids external side effects.

## Threat model

Sentinel reads an approved task contract from a trusted **earlier Git commit** and evaluates changed file paths against its allow/protect patterns. Protected controls include the selected contract and GitHub Actions workflow paths.

To use it as a required check, the repository owner must enforce the trusted baseline and approval process **outside the agent's control**. A base SHA supplied by an untrusted agent, an unprotected workflow, or an executable installed from an agent-writable branch destroys that trust boundary.

## What is not protected

- Network actions, external API modifications, reads or exposure of secrets, or out-of-repository side effects.
- All semantic errors, intentionally weakened assertions, non-test behavior changes, or incomplete tasks.
- An adaptive agent that controls the verifier, its configuration, runner, or allowed executable.
- All forms of Git trickery, filesystem races, submodule internals, or symlink destinations.
- Files omitted by Git's ignore rules unless the optional ignored-path audit is enabled; that audit checks existence, not content or creation time.
- External checker executable integrity: the report explicitly labels required checker binaries as NOT ATTESTED.
- The broader assurance of a required branch protection rule or artifact provenance. Those require separate independently managed controls.

Do not run baseline-approved required checks against candidate code with production credentials or privileged machines. Use disposable projects and isolated CI without secrets.

## Known operating assumptions

- Python 3.11+ and a compatible Git CLI.
- Git comparisons should use a **full approved baseline SHA** from an owner-controlled reference.
- The original contract is committed before the candidate edit. Candidate contract changes never grant new permissions.
- Exit 0 is a scoped verification result, not proof of task completion.
- Tests and review must remain independent of the coding agent.

## Reporting suspected vulnerabilities

Please **do not publish exploitable security details, real credentials, or proprietary samples in public GitHub Issues**.

When this repository is public, use GitHub's private vulnerability reporting if enabled. If that is not available, open a generic issue asking maintainers for a private reporting channel **without including the exploit**. No response-time or bounty commitment is offered.

Ordinary bugs, false positives and usability feedback can be submitted through public issue templates with redacted synthetic reproductions.

## Relationship to other projects

Agent Quality Gates (AQG), Proof of Done and other named tools are separate projects. Compatibility examples are not endorsement, official integration or shared security responsibility.

## Release status

This is an **experimental beta** seeking independent feedback, not a production security product. Publication of the source code or GitHub Action does not imply certification, a service-level commitment, or a guarantee against abuse.

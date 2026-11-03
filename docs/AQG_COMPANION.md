# AQG-compatible companion — independent Git task scope

**Unofficial and experimental.** Constraint Sentinel is neither an Agent Quality Gates (AQG) project nor an endorsed AQG plugin.

AQG's published deterministic quality gates address worktree cleanliness, PR evidence, audit adjudication and required context. Sentinel addresses a different question: *did these resulting Git file changes stay within paths approved before the agent's assignment?*

## Integrate without replacing anything

Keep your existing AQG checks. Add Sentinel as a **separate required GitHub Actions job** in the same repository, using the approval contract from a trusted base commit.

- **AQG:** validates its declared engineering workflow and PR evidence.
- **Sentinel:** compares changed Git paths with the independently approved contract.
- **Optional Proof of Done:** detects selected classes of weakened tests inside allowed files.

The release's README includes a draft GitHub Actions workflow. Use an exact trusted release SHA once public. An AQG or Sentinel PASS alone does not establish the correctness, safety or completeness of AI-generated code.

## Example use case

The project owner approves changes to checkout calculation code and tests, but protects payment processing and schema migrations. The agent produces a commit that accidentally changes the payment gateway.

An AQG workflow may have a clean worktree and complete PR documentation. Sentinel can separately reject the unauthorized path because it was excluded from the task contract.

A small owner-written Python/Git script can provide similar checks, and that may be sufficient for some projects. Sentinel's purpose is a reusable implementation with a maintained contract format, known edge cases, a machine-readable report and optional extensions—not a secret detection algorithm.

## Important limits

The compatibility has been validated in synthetic GitHub Actions workflows, not with every AQG version or live coding-agent hook. AQG's full skills and agent-runtime behavior were **not** assessed by this release package. Its public repository and contribution rules belong to AQG's own maintainers.

Do not describe Sentinel as an official AQG add-on. If the integration proves useful, a separate public issue or discussion could propose it to AQG maintainers **after owner approval**.

## Volunteer feedback wanted

We would especially welcome reports from developers already using AQG. Tell us whether a separate task-scope check meaningfully helps, or whether the same requirement is simpler to accomplish in existing CI. Both outcomes are valuable.

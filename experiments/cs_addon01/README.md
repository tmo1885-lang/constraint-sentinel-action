# CS-ADDON-01 — AQG companion for source-bound test-execution evidence

**Status:** experimental / draft-only / warn-only. **No released feature, production integration, required GitHub check, or AQG upstream modification.**

## Why this exists

[Agent Quality Gates (AQG)](https://github.com/deeppatternai/agent-quality-gates) already supplies a useful independent quality discipline: worktree state, audit adjudication, PR evidence closeout and context requirements. A completed AQG evidence table does not independently establish whether a newly introduced pytest test was actually collected and executed. CS-GAP-01 and CS-GAP-02/R2 found that missing-test execution evidence in controlled first-party examples.

This experiment checks the **integration value**, not the standalone algorithm or commercial market.

## Architecture and trust

1. Pin public AQG's deterministic runner to **`d3e7e466d784f25e5ccf9488a8749bd6c9851743`**; fetch it into a separate trusted source checkout. Do not alter AQG.
2. Create four entirely synthetic, disposable Git projects under the runner's temporary directory; record immutable owner baseline and each candidate SHA. Include only small source/test fixtures with no credentials or customer data.
3. Run AQG on each committed, clean candidate using the same fixed [synthetic PR-evidence table](pr-evidence.md) and [AQG config](aqg-config.json). It reports on AQG's original four gates.
4. Independently run inherited [CS-GAP-02 R2](../cs_gap02/pytest_reachability_probe.py) to compare newly introduced test-case identities against actual pytest execution. The R2 report is bound to the candidate/base Git SHAs. **R2 executes candidate tests and is NOT sandboxed.**
5. Compare against [a small project-specific expected-test-ID check](simple_expected_ci.py) using `pytest --junitxml`, which explicitly names the single required test. No Sentinel logic is used in that comparator.
6. The small [adapter](adapter.py) combines the two JSON reports, refuses head/base mismatch, incompatible R2 exit/status, or an inconsistent PASS, and emits independent `PASS`, `FAIL`, `UNVERIFIED`, `NOT_APPLICABLE` evidence states. Its outputs remain **WARN_ONLY**. An AQG pass is never treated as a proof of code correctness, and an R2 skipped/unexecuted case is never converted into PASS.

**Source-bound distinction:** The experimental R2 result is checked against the explicit Git base/head, but AQG's PR evidence table is a developer-authored assertion. The adapter deliberately marks `aqg_commit_binding_independently_verified=false`; it does not invent provenance that AQG did not supply.

## Local first-run results — Windows Python 3.12, pytest 9.2.0

All four AQG gates returned PASS for every synthetic candidate. The combined adapter produced:

| Synthetic candidate | AQG | Small fixed-test-ID CI | R2 evidence add-on | Review status |
| --- | --- | --- | --- | --- |
| Proper new passing test | PASS | PASS | PASS | Evidence observed |
| New test not discovered by pytest | PASS | FAIL | **FAIL** | Review required |
| Intentionally skipped new test | PASS | UNVERIFIED | **UNVERIFIED** | Review required, not automatic failure |
| Documentation-only change, no new test claim | PASS | NOT_APPLICABLE | NOT_APPLICABLE | No new-test evidence claimed |

Twelve independent adapter unit tests passed, including missing AQG result, mismatched Git identities, bogus success with unresolved cases and incompatible R2 exit status.

**Illustrative command wall time (milliseconds, one run each):**

| Case | AQG only | Fixed-ID test check | R2 |
| --- | ---: | ---: | ---: |
| Passing | 568 | 1,189 | 2,456 |
| Undiscovered | 568 | 995 | 2,359 |
| Skipped | 570 | 1,105 | 2,420 |
| No new test required | 564 | 304 | 2,390 |

The fixed-ID check is **faster and equally effective on these named cases** when the developer can name the required pytest ID ahead of time. R2 can infer new cases by comparing base/head and can handle parametrization expansion without a manually maintained expected-case list, but it requires baseline collection and a more complex trust/runner setup. These timings are not a performance benchmark and do not count human setup time.

## Reproduce safely

The stacked branch inherits the reviewed but **unmerged** R2 source from CS-GAP-02. On **disposable synthetic-only** fixtures with Python 3.12+, Git and pytest 9.0.2:

```sh
# Clone AQG into an *external* temporary checkout, pin the exact reviewed commit:
git clone --quiet --no-tags https://github.com/deeppatternai/agent-quality-gates.git /tmp/cs-addon01-aqg
git -C /tmp/cs-addon01-aqg checkout d3e7e466d784f25e5ccf9488a8749bd6c9851743

python -m unittest discover -s experiments/cs_addon01 -p test_adapter.py -v

python experiments/cs_addon01/run_trial.py \
  --aqg-root /tmp/cs-addon01-aqg \
  --workdir /tmp/cs-addon01-fixtures-new \
  --output /tmp/cs-addon01-comparison.json
```

The `--workdir` must not exist; repeat trials use a fresh directory. The pinned AQG source is verified before execution.

[Experimental GitHub Actions workflow](../../.github/workflows/cs-addon01-companion.yml) runs an ordinary read-only `pull_request` job on Linux and Windows Python 3.12 with `pytest==9.0.2`. **Do not use `pull_request_target` or supply secrets**, since candidate test code runs in an ordinary subprocess, not an OS sandbox. A green CI job means only that the expected synthetic classifications matched; deliberately failing candidate tests generate advisory warnings, not required merge failures.

## Limits, comparison and decision

- The synthetic cases do not prove test assertion meaning, task completion, external side-effect containment, or resistance to hostile code.
- R2's support for arbitrary pytest plugins, dynamic tests, unstable generated node IDs and mixed test runners is unqualified. It intentionally classifies skips as UNVERIFIED unless an owner demands strict execution.
- The project-specific expected-ID comparator already catches the observed missing test and intentional skip when its required test ID is known. **There is no demonstrated proprietary algorithmic moat.**
- AQG version is a reproducible historical pin, not a claim about the latest upstream release. This is not a fork, upstream contribution or AQG endorsement.
- Neither current GitHub Actions research job nor R2/adapter is a production security or quality gate.

**Decision:** Continue as a **warn-only optional evidence add-on** only if future natural coding-agent cases show that automatic expected-test discovery saves meaningful setup/review work compared with a tiny project-specific check. Keep both this PR and R2 parent PR draft. Do not merge to public Sentinel main or AQG.

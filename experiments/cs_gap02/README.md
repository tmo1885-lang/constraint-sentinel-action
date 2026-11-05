# CS-GAP-02 — pytest test-reachability experiment

**Status:** EXPERIMENTAL / offline synthetic evidence only. **No adoption, release, or enforcement authorization.**

## Research question

Can an *independent* verifier bind a newly introduced pytest test definition to concrete, observed test-case execution, instead of treating a successful `pytest` command or Git path-scope check as proof? Does the approach survive parameterization, collection behavior, skipped/expected-fail cases, and realistic test layouts without causing unacceptable false positives?

This follows CS-GAP-01's `unittest` omission case. The two experiments are separate, and this is **not** a replay of the original private Signals agent draft.

## Method

The standalone `pytest_reachability_probe.py` is separate from published Constraint Sentinel. In a **disposable synthetic Git repository** it:

1. Verifies a selected immutable base commit, checked-out candidate HEAD, clean working tree, and ancestry.
2. Diffs direct Python `test_*` definitions in `tests/**/test_*.py` using the AST in approved base and candidate Git blobs.
3. Invokes pytest 9.0.2 in a subprocess, using an external hook to capture *collected node IDs* and each test's *setup/call/teardown result*.
4. Checks each newly added definition has collected case(s), with a successful call phase or an explicitly recorded expected failure. Missing collection, setup skips, runtime skips, unverified cases, collection errors or broken tests fail the experiment.
5. Fails closed if visible Git state changes during execution or if the baseline/head contract is inconsistent. Produces a structured result.

**Safety restriction:** The candidate test code executes. A subprocess with stripped obvious secret-named environment variables is **not a sandbox**, and is not a security control. Run only against disposable synthetic code, not an untrusted contributor PR with privileged tokens, `pull_request_target`, protected developer machines, or confidential content.

## Results — local Python 3.13.5 / pytest 9.0.2, Git 2.47.3

Sixteen focused synthetic regression controls passed as tests of *the probe's expected outcome*. A control testing a known false positive can pass while the probe itself intentionally rejects the legitimate scenario.

| Control | Ordinary pytest | CS-GAP-02 probe | Assessment |
| --- | --- | --- | --- |
| New top-level pytest test | PASS | PASS | Correct |
| `test_*` method in class not collected by pytest | PASS (preexisting tests) | FAIL — not collected | **Useful discovery** |
| New method in properly named pytest class | PASS | PASS | Correct |
| New parametrized function, all 3 cases run | PASS | PASS, 3 cases | Correct |
| Parametrized function with one conditionally skipped case | PASS (1 skipped) | FAIL — 1 missing execution | **Potential false positive** for intentional skip |
| `@pytest.mark.skip` new function | PASS (skipped) | FAIL — no call phase | Expected strict policy |
| New runtime-skipped function | PASS (skipped) | FAIL — call skipped | Expected strict policy |
| Expected failure (`xfail`) whose test body runs | PASS (xfailed) | PASS, labeled *expected failure* | Reachability only, **not correctness** |
| Unexpected pass (`xpass`, nonstrict) | PASS | FAIL — unverified xpass | Cautious policy |
| Pytest collection/import error | FAIL | FAIL | Correct |
| No new test definition despite an in-scope edit | PASS | FAIL | Correct **only when the task predeclares new-test requirement** |
| Nested `tests/unit/test_*.py` new test | PASS | PASS after recursive-scan fix | Correct |
| Legitimate extension of existing parametrized function | PASS | FAIL — no *new function* | **False positive / unsupported case expansion** |
| Dirty candidate tree | Not relevant | Refuses evidence | Correct fail-closed behavior |
| Wrong candidate HEAD | Not relevant | Refuses evidence | Correct fail-closed behavior |
| Candidate test creates untracked file | PASS | Refuses evidence | Visible-Git-state guard; not a side-effect sandbox |

**One illustrative timing run, not a performance benchmark:** ordinary `pytest -q`: 1.76 s; `pytest --collect-only -q`: 1.67 s; test-reachability probe (including pytest): 3.03 s. These samples are not matched production workloads; no general overhead estimate can be inferred.

## Pinned competitor comparison: Proof of Done 0.5.0

A separate **Windows Python 3.12 / Git 2.55** offline synthetic repository was frozen at base `9b53b04a326e82f3190e97b9f59fd2a08775e839`. Using an already-installed external `proof-of-done@0.5.0` CLI, `proof-of-done verify --base <base> --json` produced:

| Synthetic pytest case | Proof of Done 0.5.0 | CS-GAP-02 |
| --- | --- | --- |
| New `test_*` method in a non-pytest-collectible class | **PASS**, 0 findings, 1 file checked | **FAIL** — method not collected |
| New `test_*` method in a collectible `Test*` class | PASS, 0 findings, 1 file checked | PASS |
| New 3-case parametrized test, 1 intentionally skipped | **PASS**, 0 findings, 1 file checked | **FAIL** — missing execution for skipped parameter |

These are selected independent synthetic cases, **not** a security assessment or general accuracy claim about Proof of Done. The intentionally skipped parameter is ambiguous: it demonstrates CS-GAP-02's stricter execution requirement, but may be an **undesirable false alarm** for the developer. For this reason, a zero-findings Proof of Done result is not automatically a defect in that tool. The decisive first case does represent a missed new-test execution in the tested configuration.

## Interpretation and design implications

- A successful pytest command and even a successful `--collect-only` command can coexist with an *unexpectedly undiscovered new test*. A source-diff-to-execution-ID comparison catches it.
- The same idea can be implemented in a small independent Python/pytest plugin. **No unique Sentinel algorithm or commercial advantage follows.** A project-specific required-test identity check could deliver the same assurance for fixed workflows.
- **Important false positives:** legitimate platform-dependent skips and adding parameter instances to an existing pytest test are currently rejected. Extra parametrization is not recognized because the source scanner detects added *functions*, not new cases of preexisting functions. A baseline pytest collection manifest or explicit expected-case contract might help, but would add setup and trust complexity.
- Test plugins, dynamic generation, custom `python_functions`/`python_classes`, import modes, packages, nested classes, fixtures and mixed pytest/unittest projects have **not** been generally qualified. The experiment disables *site auto-loaded* plugins, so it does not replicate every user's CI environment.
- Passing executed assertions does not prove they are meaningful. An `xfail` that really executed is explicitly categorized, not treated as a passed behavioral requirement.
- Head and dirty-worktree checks are not same-execution cryptographic provenance. Candidate code may access the network, create external side effects, or even modify and restore files undetected. No production security claims.

## Reproduce

Requires Python 3.11+, Git and **pytest 9.0.2** installed in an isolated test environment. From a checkout containing these two scripts:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python -m unittest -v experiments.cs_gap02.test_gap02_experiment
```

Each control creates and deletes its own temporary synthetic Git repository; it does not read external confidential files. Tests may take several seconds each to start pytest and create Git fixtures.

## Decision

**GO for this bounded technical finding; NO-GO for mandatory Sentinel integration.** The hypothesis works for selected pytest fixtures but broad runner portability, intentional-skip policy, new parametrized cases, and operational isolation remain unresolved. Next work—only if needed—should compare against the cheaper alternative of predeclaring exact expected pytest IDs in existing CI, before expanding the checker or claiming incremental value.

# CS-GAP-01 — did newly added Python tests actually run?

**Status: experimental result, not accepted for Sentinel beta or production CI.**

## Hypothesis and selected failure

During a real internal coding-agent workflow, a developer discovered that the agent had written a regression test not discoverable by the project's `unittest discover` command. The agent's test was corrected during manual review, so its exact original intermediate file is not part of this publication. **The cases below reconstruct the same failure mechanism in disposable synthetic Git repositories.** No private Signals source, editorial records or customer data are included here.

Predeclared question: can an independent check compare **new `test_*` definitions** in a candidate commit with the **identities of tests actually discovered and executed** by the project's designated runner? Can it distinguish missing execution from ordinary test renames?

This is a narrow evidence-reachability check, **not** a claim of test correctness.

## Reproduction

From a checked-out copy of this research branch with Python 3.11+ and Git:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest tests/test_gap01_experiment.py -v
# or with ordinary suite discovery:
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_gap01_experiment.py -v
```

The test module creates disposable Git repositories and commits from scratch. `experiments/cs_gap01/test_reachability_probe.py` is an independent experimental script; it uses no existing Sentinel modules. It derives newly added direct Python test functions and class methods using `ast` from the before/after commits and compares their identities with a live `unittest` discovery and execution run. It refuses a dirty worktree or mismatched candidate commit. All test execution remains **in offline synthetic fixture repositories**.

## Results — first local Windows/Python 3.12 run, Nov 4, 2026

| Scenario | Ordinary `unittest` | Existing Sentinel scope | Experimental CS-GAP-01 |
| --- | --- | --- | --- |
| New, undiscoverable top-level test; existing baseline test still runs | PASS, 1 test executed | PASS; same two approved paths | **FAIL** — new test identity missing |
| Corrected `unittest.TestCase` method in new test file | PASS, 2 tests executed | PASS; same two approved paths | PASS; new test executed |
| New, undiscoverable test added to a file already containing tests | PASS, 2 existing tests executed | PASS; allowed file | **FAIL** — new test identity missing |
| Valid newly added method in same existing file | PASS, 3 tests executed | PASS; allowed file | PASS |
| Valid rename of an existing test, with *unchanged total count* | PASS, 2 tests executed | Not required for rename control | PASS; new identity executed |
| Dirty worktree / mismatched head | Not applicable | Not evaluated | Refuses evidence |

Both initial candidates use the same previously approved scope and the same two changed file paths; Sentinel correctly passes each because both stay inside scope. The "bad" fixture reconstructs the observed **unittest-versus-pytest-style test mismatch**, but is not represented as the original agent draft. Running more than zero tests is insufficient when an established suite already has baseline tests. Checking only whether test count increases can also mishandle a legitimate rename.

The original closed-source internal repair and its code are **not** included in these public fixtures. Candidate commitments and owner-approval refs in the original local testbed are not available as public GitHub refs; the test module creates new, reproducible synthetic commits independently on each run.

## What this does and does not establish

**Established in the controlled Python/unittest scenario:** an external tool can mechanically catch an added but undiscovered test that both post-change file scope checking and a successful normal test command accept.

**Not established:**

- That Sentinel has a unique algorithmic or commercial advantage: the experimental witness is itself a small standard-library Python/Git script.
- That a discovered test actually tests the requested functionality. A vacuous assertion can pass this check.
- Runner portability beyond Python's **`unittest`**. Pytest test collection, parameterization, JavaScript, dynamic generation, shared fixtures and test ids need separate policies.
- Resistance to a malicious candidate: the experimental probe **executes candidate test code** in a subprocess, which is **not an OS sandbox**. Do not execute it in privileged `pull_request_target` jobs, on protected production hosts or with live credentials.
- Proof that the executed test used the expected runtime dependencies or that other modules were not changed by side effects. The probe rechecks visible Git status, but does not monitor external effects.
- General accuracy or false-positive rates. We tested only a small set of deliberately designed cases.

**Disposition:** candidate for an opt-in evidence-discovery integration, subject to comparison against trivial project-specific CI that explicitly asserts expected test identity. **Do not merge as a mandatory gate** until representative projects, runners, failure modes and developer setup friction justify it.

See the existing [DIY-versus-Sentinel R1 comparison](https://github.com/tmo1885-lang/Constraint-Sentinel/blob/main/comparison/diy/RESULTS-R1.md) for why reproducible scope verification alone is not a differentiated product.

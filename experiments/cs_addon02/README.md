# CS-ADDON-02 — Real-project failure register and narrow correction

**Status: research-only, unprivileged, warn-only; not a production checker.**

This experiment follows CS-ADDON-01 (AQG companion), itself stacked on the unmerged CS-GAP-02/R2 branch. The purpose is to **test for failure modes and record negative findings** before trying to justify product or upstream adoption.

## Finding ADDON02-001 — previously collected tests silently disappear

**Observed on an actual project's tests, with synthetic edits:** Velorin Gap Radar `main` at `479818484beb4c482315e118df375888e3a72d3c` has 272 collected pytest cases on the test machine (Windows Python 3.12, pytest 9.2.0). We cloned the project to a disposable local QA checkout and renamed one existing parametrized test definition so pytest no longer recognized it. This is an intentional QA mutation, **not** a spontaneous agent defect.

Original R2 read the base and candidate collections, but only enforced *new* test definitions and newly added case IDs. Its result was **NOT_APPLICABLE, exit 0**, even though the collected test count dropped **272 → 269**. The regular pytest suite still exited successfully. This is a significant **false negative** for test-execution evidence integrity. Baseline and mutated candidate commits were local-only; no upstream file was edited.

### Minimal repair

In the external research `pytest_reachability_probe.py`, calculate disappearing case IDs using the **full** Git base/candidate pytest collection inventories, including cases lost because pytest configuration changes rather than a test file edit. If previously collected cases disappear, return **UNVERIFIED, exit 3** with:

- `previously_collected_cases_missing`: the precise missing pytest node IDs;
- `unexecuted_or_unverified`: the corresponding review items with reason `previously_collected_case_missing`;
- unchanged source-bound candidate/base SHA evidence.

**Do not automatically FAIL.** An authorized test rename or deletion can produce the same change, and this prototype cannot establish the developer's intended coverage policy. An explicit owner-approved removal and policy would be needed for a safe enforcement gate.

The external AQG/R2 JSON adapter now refuses an R2 **PASS** with missing previous test cases or **NOT_APPLICABLE** when collected tests disappear. It preserves **UNVERIFIED** as a review item rather than converting it into a green completion claim.

### First local verification (Nov 5, 2026)

| Scenario | Original R2 | Corrected R2 | Meaning |
| --- | --- | --- | --- |
| Existing parametrized test stops collecting in real Gap Radar suite | NOT_APPLICABLE | **UNVERIFIED** | Catches the loss of 3 previously collected cases |
| Legitimate test rename (synthetic) | Not qualified | **UNVERIFIED**, not FAIL | Review required rather than false automatic failure |
| `pytest.ini` config-only change hides 3 preexisting test cases | NOT_APPLICABLE | **UNVERIFIED** | Reproduced second blind spot, then fixed |
| Documentation-only edit | NOT_APPLICABLE | NOT_APPLICABLE | No unsupported test coverage claim |
| Existing R2 synthetic regression suite | Previous 17/17 | **17/17 passed locally** | No previously tested behavior regressed |
| Companion adapter unit tests | Previous 12/12 | **16/16 passed locally** | Also rejects inconsistent missing-coverage claims |
| New disappeared-case regression suite | N/A | **4/4 passed locally** | Independent coverage-loss/rename/config/docs controls |

Real-project corrected replay: **272 baseline → 269 candidate**, 3 exact missing node IDs, **UNVERIFIED / exit 3**; original repository clean and unchanged. Local Git worktrees remained clean. Hosted verification is separate from this original Windows-only real-project replay.

## Material limitations / remaining failure-register items

1. **ADDON02-001 (corrected narrowly):** lost test identities were silently ignored. R2 now compares all baseline/candidate pytest case IDs and signals uncertainty; it does not establish whether a removal is authorized.
2. **ADDON02-002 (unresolved):** legitimate test renames, intentional removal, changing parameter IDs, and environment-specific parametrization can yield **UNVERIFIED** warnings. A source-identity transition or owner approval policy might reduce these warnings, but must be qualified before enforcement.
3. **ADDON02-003 (corrected for static pytest.ini, broader case unqualified):** a controlled `pytest.ini` change made three unchanged-file test cases disappear while pytest still passed. A targeted regression initially reproduced **NOT_APPLICABLE**; the full collection diff now reports **UNVERIFIED**. Arbitrary `conftest.py`, third-party plugins, dynamic test generation and environment-dependent collection remain unqualified.
4. **ADDON02-004 (unresolved):** dynamic or unstable generated node IDs, third-party plugins, mixed runners and cross-platform collection differences are not fully supported.
5. **ADDON02-005 (unresolved, security):** candidate test code executes in a subprocess, **not an OS sandbox**. This research workflow is safe only for disposable first-party synthetic inputs, read-only unprivileged CI and no secrets.
6. **ADDON02-006 (economic):** a tiny project-specific expected-test-ID check detected the same previously qualified omission/skip cases with less overhead when the required test identity was known. No evidence yet that automatic discovery justifies a general-purpose integration.

## Reproduction

From the stacked research branch with Python 3.12+, Git and pinned pytest 9.0.2, only on disposable synthetic fixtures:

```sh
python -m unittest discover -s experiments/cs_addon02 -p test_missing_previous.py -v
python -m unittest discover -s experiments/cs_addon01 -p test_adapter.py -v
python -m unittest discover -s experiments/cs_gap02 -p test_gap02_experiment.py -q
```

The dedicated [research CI workflow](../../.github/workflows/cs-addon02-missing-tests.yml) runs these tests on ordinary `pull_request` workers on Linux/Windows, with only read-only permissions. Do not run against untrusted contributor code with privileged credentials, use `pull_request_target`, or merge into published Sentinel.

**Disposition:** one falsifying real-project finding recovered by a minimal external-probe correction; continue evidence-first addon research with a failure register. Keep this PR DRAFT and stacked on #13. No AQG fork, AQG upstream change, released Sentinel change or mandatory gate.

# CS-ADDON-02 - additive failure register

**Research only. No merge, release, production enforcement, or AQG upstream changes.**
This experiment is stacked on the CS-ADDON-01 draft PR #13 and R2 draft PR #12.
Changes are limited to the external experimental R2 verifier, independent adapter,
disposable synthetic regression tests and read-only research CI.

## Registered findings

| ID | Class | Reproduced observation | Current disposition |
| --- | --- | --- | --- |
| ADDON02-001 | False negative, high | Three existing parametrized tests vanish from a *changed test file* while pytest exits successfully; R2 returned NOT_APPLICABLE | **Corrected:** compare all baseline/head collected IDs; report UNVERIFIED and missing IDs |
| ADDON02-002 | False-positive risk | Legitimate test rename or approved test deletion also removes old IDs | **Open by design:** UNVERIFIED for human review, not automatic FAIL; an explicit authorized-rename/removal policy remains unqualified |
| ADDON02-003 | False negative, moderate | Changing only `pytest.ini` hides three tests from unchanged files, with normal pytest still passing; the changed-test-file filter returned NOT_APPLICABLE | **Corrected in this research branch:** full base/head collection comparison; synthetic red-to-green regression confirms UNVERIFIED |
| ADDON02-004 | Portability uncertainty | Unstable/generated node IDs, plugins, xdist, conftest and mixed runners may cause noisy collection differences | **Unqualified:** remain warn-only and measure false alarms on representative tasks |
| ADDON02-005 | Security / trust limitation | Baseline collection and candidate execution run project Python code | **Unresolved:** Python subprocess is not an OS sandbox; only synthetic first-party inputs on unprivileged no-secrets workers |
| ADDON02-006 | Incremental product value | Tiny expected-test-ID CI can detect the original selected omission/skip at lower execution cost | **Unproven:** automatic derivation must save human configuration/review effort to justify additional complexity |

## Real project reproduction (Nov 5, 2026)

Velorin Gap Radar `main` exact original SHA:
`479818484beb4c482315e118df375888e3a72d3c`.
In a disposable Windows Python 3.12 / pytest 9.2.0 local clone, deliberately
changed an existing `test_` function to stop pytest discovering it. This was a
controlled QA edit, **not** a spontaneous coding-agent error.

- Old baseline: **272 collected tests**.
- Edited candidate: **269 collected tests**; ordinary pytest exited **0**.
- Local-only changed candidate SHA: `c6cc772eae3a494de6abf9d6595f5ef46e73231d`.
- Original R2 status: **NOT_APPLICABLE**, exit 0 (false negative).
- Corrected R2 status: **UNVERIFIED**, exit 3, with exact missing cases:
  - `tests/test_a0_r2.py::test_old_ambiguous_r1_labels_are_invalid[ALLOW]`
  - `tests/test_a0_r2.py::test_old_ambiguous_r1_labels_are_invalid[HALT]`
  - `tests/test_a0_r2.py::test_old_ambiguous_r1_labels_are_invalid[STOP]`
- AQG original gate result: PASS; companion result: AQG PASS / Sentinel UNVERIFIED / REVIEW_REQUIRED, warn-only.
- Source checkout and all local test candidates remained clean. No deployment or live agent call.

## Second negative control: pytest.ini

With the first changed-test-file-only repair, adding a `pytest.ini` containing
`python_functions = test_still_runs` left one existing test runnable while
suppressing three other, unchanged-file parametrized tests. The new targeted
test **failed red**: expected UNVERIFIED but got NOT_APPLICABLE. The verifier
was then narrowed in responsibility but expanded in coverage: it now compares
**all baseline-vs-candidate collected node IDs**, not only IDs in changed test
files, and records previously collected cases that are absent.

After this change the same synthetic control **passed green**: exit 3 /
UNVERIFIED, three missing exact IDs. This is a review advisory, not proof of
misconduct or incorrect intent.

## Regression controls and known boundaries

- Existing CS-GAP-02 R2 synthetic suite: **17/17 locally passed** before the
  second full-inventory adjustment; hosted CI reruns the entire suite.
- AQG/R2 adapter: **16/16 locally passed** with evidence schema protections.
- ADDON02 synthetic controls: **4/4 passed locally** after the full-inventory fix:
  vanished test methods, legitimate rename, documentation-only task and
  pytest.ini-only collection change.
- Prior CS-ADDON-01 integration four-case synthetic comparison:
  **4/4 matched** after the fix.
- Original real-project qualification was run on Windows only; research CI
  qualifies *synthetic* cases on both Linux and Windows.
- New detection does not prove assertion semantics, test necessity, intent or
  task completion, and can be noisy if IDs are nondeterministic.
- Test execution is **not isolated from network/OS side effects**. Never use
  privileged `pull_request_target` or production secrets.

**Disposition:** retained draft-only. Continue testing as an independent,
optional AQG companion with a failure register. Never turn an UNVERIFIED status
into a silent PASS or block merges without separately qualified owner policy.

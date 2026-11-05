# CS-ADDON-02 — evidence gap register and correction

**Status:** experimental, draft-only, warn-only. This add-on study is stacked on CS-ADDON-01 draft PR #13 and CS-GAP-02 R2 draft PR #12. No merge, AQG fork/upstream modification, production deployment, released Sentinel beta change, privileged CI gate, or autonomous coding-agent trial.

## Register

| ID | Severity | Evidence class | Observed behavior | Outcome | Disposition |
| --- | --- | --- | --- | --- | --- |
| ADDON02-001 | High evidence-integrity gap | **False negative** | Existing parametrized test ceases collection on code change; pytest passes, R2 says `NOT_APPLICABLE` | **Repaired in this research branch** | Warn-only `UNVERIFIED` with exact missing case IDs; not assumed misconduct |
| ADDON02-002 | Moderate operational limitation | Potential false positive | Valid test rename/migration makes old pytest IDs disappear | **Measured, not eliminated** | Flag for review as `UNVERIFIED`, never automatically FAIL; approval policy needed |
| ADDON02-003 | Moderate portability uncertainty | Unqualified | Dynamic/unstable generated pytest IDs, plugins or different collectors may produce spurious additions/removals | **Unknown** | Do not enforce; needs representative third-party trials |
| ADDON02-004 | High trust limitation | Unqualified security | Both baseline collection and candidate execution run repository code; Python subprocess/environment filtering is **not** sandboxing | **Unresolved by design** | Never run with privileged `pull_request_target`, production secrets or untrusted code on protected machines |
| ADDON02-005 | Product differentiation | Competitive finding | Tiny project-specific CI with predeclared test IDs caught the same selected new-test omission faster | **No unique value demonstrated** | Test whether automatic source-to-case discovery actually saves maintenance/reviewer time in natural agent work |

## Reproduction: first-party Gap Radar

- Repository: [Velorin Gap Radar](https://github.com/tmo1885-lang/velorin-gap-radar), frozen original `main` at `479818484beb4c482315e118df375888e3a72d3c`.
- Actual unmodified baseline: **272 collected pytest cases** in Windows Python 3.12 / pytest 9.2.0.
- Controlled, **synthetic** edit on a disposable checkout: rename `tests/test_a0_r2.py::test_old_ambiguous_r1_labels_are_invalid` so its `test_` prefix is lost. Three existing parameter cases `ALLOW`, `HALT`, `STOP` silently stop being collected, leaving **269** cases. The original repository and disposable candidate are clean afterward.
- Exact local candidate Git SHA `c6cc772eae3a494de6abf9d6595f5ef46e73231d`. No spontaneous coding-agent mistake is claimed.
- **Previous R2 (before repair):** exit 0, status `NOT_APPLICABLE`, new definitions 0, new case IDs 0, no incomplete evidence, despite 272 → 269 collection.
- **Repaired R2:** exit 3, `UNVERIFIED`, records the **three exact disappeared case IDs**, each marked `previously_collected_case_missing`; baseline 272 → candidate 269.
- **External AQG composition:** pinned AQG `d3e7e466d784f25e5ccf9488a8749bd6c9851743` still passes its four authored-evidence gates. Standalone adapter now emits `AQG PASS / Sentinel UNVERIFIED / REVIEW_REQUIRED` with three missing cases and `WARN_ONLY=true`.

The prior R2 was designed principally for *new* tests. This is not a claim that every disappearing test is a software bug. However, describing a loss of previously collected coverage as `NOT_APPLICABLE` hides relevant evidence. The correction makes the change reviewable without making an intentional test rename or removal an automatic failure.

## Fix design

R2 already collects immutable before/after pytest inventories from isolated baseline and candidate checkouts. This patch computes the previous IDs absent from the candidate **only within changed `tests/**/test_*.py` files**, and records `previously_collected_cases_missing` separately from newly added IDs. A nonempty removed-case inventory results in `UNVERIFIED` (exit 3) unless an independent failure already exists. A legitimate rename can therefore be reviewed and approved without being incorrectly called a test failure.

The companion adapter rejects a forged `PASS` or `NOT_APPLICABLE` report with missing previously collected cases and exposes the precise ID inventory. Its status always remains **advisory**.

## Controls and boundaries

- The R2 experiment's existing synthetic 17-case suite and CS-ADDON-01's existing 4-case AQG comparison are regression baselines.
- Added targeted synthetic controls: disappeared three-case parametrized test (UNVERIFIED), legitimate test rename (UNVERIFIED, not FAIL), and documentation-only change (NOT_APPLICABLE).
- Adapter expanded from 12 to 16 unit tests for missing-case invariants and schema validation.
- Re-run tests on unprivileged hosted Linux and Windows with pinned `pytest==9.0.2`; the real-project Gap Radar check was **Windows only**.
- No enforcement claim: a programmatically generated pytest ID can be unstable; changes in `conftest.py` or custom collector configuration outside `test_*.py` may change collection in ways not captured by this narrow delta. The checker also does not judge assertion meaning or task quality.
- No end-user adoption, QA effectiveness rate, false-positive rate, or commercial moat established.

## Next evidence threshold

Keep testing as an optional add-on, maintain a **failure/false-positive register**, and only implement a further fix when a realistic, repeatable failure shows that it is needed. The next highest-value challenge is natural coding-agent maintenance changes where a reviewer did **not** predeclare exact required test IDs, especially parametrization changes and legitimate test renames. Compare maintenance and review effort with the smaller expected-ID CI alternative.

**Decision: record and repair ADDON02-001; do not merge drafts or alter AQG upstream.**

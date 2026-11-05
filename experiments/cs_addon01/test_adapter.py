"""CS-ADDON-01: offline unit regressions for warn-only JSON normalization."""
from __future__ import annotations

import copy
import unittest

from adapter import combine


BASE = "a" * 40
HEAD = "b" * 40


def aqg(ok: bool = True) -> dict:
    return {"ok": ok, "gates": {"evidence_closeout": {"status": "pass"},
                              "worktree": {"status": "pass"}}}


def r2(status: str) -> dict:
    cases = [] if status == "not_applicable" else ["tests/test_added.py::test_new_behavior"]
    findings = ([{"nodeid": cases[0], "reason": "not_collected"}]
                if status == "fail" else
                [{"nodeid": cases[0], "reason": "intentionally_skipped"}]
                if status == "unverified" else [])
    return {
        "experiment": "CS-GAP-02-R2",
        "status": status,
        "base": BASE,
        "candidate": HEAD,
        "changed_paths": ["tests/test_added.py"],
        "new_case_ids": cases,
        "unexecuted_or_unverified": findings,
    }


def normalize(status: str, *, ok: bool = True) -> dict:
    exits = {"pass": 0, "fail": 1, "unverified": 3, "not_applicable": 0}
    return combine(aqg(ok), r2(status), base=BASE, head=HEAD,
                   r2_exit=exits[status])


class AddonAdapterTests(unittest.TestCase):
    def test_pass_is_advisory_only_and_not_completion(self) -> None:
        out = normalize("pass")
        self.assertEqual(out["sentinel_evidence_status"], "PASS")
        self.assertEqual(out["aqg_status"], "PASS")
        self.assertEqual(out["review_outcome"], "EVIDENCE_OBSERVED")
        self.assertTrue(out["advisory_only"])
        self.assertEqual(out["task_completion"], "NOT_VERIFIED")

    def test_missing_test_is_review_required_not_green(self) -> None:
        out = normalize("fail")
        self.assertEqual(out["sentinel_evidence_status"], "FAIL")
        self.assertEqual(out["review_outcome"], "REVIEW_REQUIRED")

    def test_skip_remains_unverified_and_not_pass(self) -> None:
        out = normalize("unverified")
        self.assertEqual(out["sentinel_evidence_status"], "UNVERIFIED")
        self.assertEqual(out["review_outcome"], "REVIEW_REQUIRED")

    def test_no_new_test_does_not_claim_coverage(self) -> None:
        out = normalize("not_applicable")
        self.assertEqual(out["sentinel_evidence_status"], "NOT_APPLICABLE")
        self.assertEqual(out["review_outcome"], "NO_NEW_TEST_EVIDENCE_CLAIM")

    def test_aqg_failure_not_erased_by_r2_pass(self) -> None:
        out = normalize("pass", ok=False)
        self.assertEqual(out["aqg_status"], "FAIL")
        self.assertEqual(out["review_outcome"], "REVIEW_REQUIRED")

    def test_rejects_r2_source_head_mismatch(self) -> None:
        result = r2("pass")
        result["candidate"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "source identity mismatch"):
            combine(aqg(), result, base=BASE, head=HEAD, r2_exit=0)

    def test_rejects_r2_source_base_mismatch(self) -> None:
        result = r2("pass")
        result["base"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "source identity mismatch"):
            combine(aqg(), result, base=BASE, head=HEAD, r2_exit=0)

    def test_rejects_bad_exit_for_skipped_test(self) -> None:
        with self.assertRaisesRegex(ValueError, "R2 exit"):
            combine(aqg(), r2("unverified"), base=BASE, head=HEAD,
                    r2_exit=0)

    def test_rejects_fake_pass_with_unexecuted_cases(self) -> None:
        result = r2("pass")
        result["unexecuted_or_unverified"] = [{"reason": "not_collected"}]
        with self.assertRaisesRegex(ValueError, "unresolved"):
            combine(aqg(), result, base=BASE, head=HEAD, r2_exit=0)

    def test_rejects_fake_not_applicable_with_new_case(self) -> None:
        result = r2("not_applicable")
        result["new_case_ids"] = ["tests/test_added.py::test_new_behavior"]
        with self.assertRaisesRegex(ValueError, "NOT_APPLICABLE"):
            combine(aqg(), result, base=BASE, head=HEAD, r2_exit=0)

    def test_rejects_missing_aqg_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "boolean ok"):
            combine({"gates": {}}, r2("pass"), base=BASE, head=HEAD,
                    r2_exit=0)

    def test_rejects_missing_aqg_gates(self) -> None:
        with self.assertRaisesRegex(ValueError, "gate results"):
            combine({"ok": True, "gates": {}}, r2("pass"),
                    base=BASE, head=HEAD, r2_exit=0)


if __name__ == "__main__":
    unittest.main()

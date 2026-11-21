"""Synthetic checks: report triage never grades answers or leaks source data."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from acceptance_report_triage import InvalidReport, triage_report


def example():
    return {
        "schema": "homebrain-v2-source-real-acceptance-report.v1",
        "cases_expected": 2,
        "cases_captured": 2,
        "captured_case_ids_in_review_order": ["t-1", "t-2"],
        "failed_first_answer_case_ids": ["t-2"],
        "benchmark_pack": "synthetic",
        "expected_addon_version": "fake-alpha",
        "permission_evidence": {
            "per_client_read_enabled_reported": True,
            "per_client_write_enabled_reported": False,
        },
        "summary": {"details": [
            {"native_tools": {"attempted": 1, "failed": 0},
             "history_receipts": {"any_request_limit_reached": True},
             "log_receipts": {
                 "any_log_request_limit_reached": False,
                 "receipts_where_reported_matches_exceed_returned": 0},
             "performance": {"server_elapsed_ms": 23000},
             "response": {"answer": "PRIVATE SHOULD NOT LEAK"}},
            {"native_tools": {"attempted": 2, "failed": 0},
             "history_receipts": {"any_request_limit_reached": False},
             "log_receipts": {
                 "any_log_request_limit_reached": True,
                 "receipts_where_reported_matches_exceed_returned": 1},
             "performance": {"server_elapsed_ms": 7000}},
        ]},
        "private": "PRIVATE SHOULD NOT LEAK",
    }


class TriageTests(unittest.TestCase):
    def test_failed_first_answer_before_source_limit_and_no_private_data(self):
        report = triage_report(example())
        self.assertFalse(report["promotion_ready"])
        self.assertTrue(report["unscored"])
        self.assertTrue(report["source_reported_read_only_client"])
        ordered = report["case_review_order"]
        self.assertEqual([r["case_id"] for r in ordered], ["t-2", "t-1"])
        self.assertIn("first_answer_failed", ordered[0]["review_flags"])
        self.assertIn("event_history_row_limit_reached", ordered[1]["review_flags"])
        self.assertNotIn("PRIVATE SHOULD NOT LEAK", json.dumps(report))

    def test_source_permission_is_not_independent_enforcement(self):
        report = triage_report(example())
        self.assertFalse(report["independent_permission_enforcement_verified"])
        self.assertFalse(report["original_source_independently_verified"])
        self.assertFalse(report["first_attempt_independently_verified"])

    def test_bad_counts_and_ids_fail_closed(self):
        invalid = example()
        invalid["cases_captured"] = 3
        with self.assertRaises(InvalidReport):
            triage_report(invalid)
        invalid = example()
        invalid["summary"]["details"][0]["native_tools"]["attempted"] = True
        with self.assertRaises(InvalidReport):
            triage_report(invalid)
        invalid = example()
        invalid["benchmark_pack"] = "PRIVATE SHOULD NOT LEAK"
        with self.assertRaises(InvalidReport):
            triage_report(invalid)
        invalid = example()
        invalid["failed_first_answer_case_ids"] = ["unknown"]
        with self.assertRaises(InvalidReport):
            triage_report(invalid)


if __name__ == "__main__":
    unittest.main()

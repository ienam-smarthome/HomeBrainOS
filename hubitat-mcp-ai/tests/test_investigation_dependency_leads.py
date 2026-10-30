"""Regression checks for the read-only source-attested dependency lead graph."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from investigation_dependency_leads import build_dependency_leads


START = "2026-10-30T12:00:00+00:00"
END = "2026-10-30T13:00:00+00:00"


class DependencyLeadTests(unittest.TestCase):
    def test_command_then_report_remain_distinct_not_causally_verified(self):
        receipts = [
            {"success": True, "mutates": False, "evidence_kind": "verified_automation_dependency",
             "details": {"appId": "4013", "deviceId": "7818", "role": "controls"}},
            {"success": True, "mutates": False, "evidence_kind": "verified_app_execution",
             "details": {"observations": [{"date": "2026-10-30T12:10:01Z",
                 "device_id": "7818", "app_id": "4013", "action": "on",
                 "timestamp_basis": "source", "record_type": "app-command"}]}},
            {"success": True, "mutates": False, "evidence_kind": "verified_device_event",
             "details": {"observations": [{"date": "2026-10-30T12:10:02Z",
                 "device_id": "7818", "value": "on", "timestamp_basis": "source",
                 "record_type": "device-report"}]}}
        ]
        result = build_dependency_leads(receipts, since=START, until=END,
                                        target_ids=["7818"])
        self.assertEqual(len(result["observations"]), 2)
        self.assertFalse(result["causal_attribution_verified"])
        self.assertTrue(any(edge["relationship"] == "verified-controls" for edge in result["edges"]))
        self.assertTrue(any("command-issued" in edge["relationship"] for edge in result["edges"]))

    def test_untrusted_or_reception_rows_cannot_create_causal_leads(self):
        receipts = [
            {"success": False, "evidence_kind": "verified_automation_dependency",
             "details": {"appId": "4013", "deviceId": "7818", "role": "controls"}},
            {"success": True, "mutates": True, "evidence_kind": "verified_automation_dependency",
             "details": {"appId": "4013", "deviceId": "7818", "role": "controls"}},
            {"success": True, "mutates": False, "evidence_kind": "recent_edge_switch_context",
             "details": {"observations": [{"date": "2026-10-30T12:30:00Z",
                 "device_id": "7818", "value": "on",
                 "timestamp_basis": "collector-received",
                 "record_type": "device-report"}]}},
        ]
        result = build_dependency_leads(receipts, since=START, until=END,
                                        target_ids=["7818"])
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["edges"], [])
        self.assertFalse(result["coverage_complete"])

    def test_no_guessed_ids_or_out_of_window_data(self):
        receipts = [
            {"success": True, "evidence_kind": "verified_automation_dependency",
             "details": {"appId": "4013", "deviceId": "9999", "role": "controls"}},
            {"success": True, "evidence_kind": "verified_device_event",
             "details": {"observations": [{"date": "2026-10-30T11:59:00Z",
                 "device_id": "7818", "value": "on", "timestamp_basis": "source",
                 "record_type": "device-report"}]}}
        ]
        result = build_dependency_leads(receipts, since=START, until=END,
                                        target_ids=["7818"])
        self.assertEqual(result["edges"], [])
        self.assertEqual(result["unobserved_target_ids"], ["7818"])

    def test_invalid_scope_is_empty(self):
        result = build_dependency_leads([], since=END, until=START,
                                        target_ids=["7818"])
        self.assertEqual(result["status"], "invalid-scope")


if __name__ == "__main__":
    unittest.main()

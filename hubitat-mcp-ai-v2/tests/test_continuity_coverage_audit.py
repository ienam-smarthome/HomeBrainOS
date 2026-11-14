"""General synthetic continuity-source evidence tests (no hub/model access)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from investigation_review import (
    MEASUREMENT_REVIEW_PROMPT,
    FINAL_CLAIM_AUDIT_PROMPT,
    final_claim_receipt_scope_index,
)


def monitor_receipt(history, *, success=True):
    return {
        "name": "homebrain_read_device_monitor",
        "arguments": {"mode": "history", "metric": "power", "range": "6h",
                      "device_id": "101"},
        "success": success,
        "result_kind": "local_monitor_read",
        "response": json.dumps({
            "client_monitor_evidence_scope": {
                "source_kind": "separate saved-device-history archive",
                "mode": "history",
                "history": history,
                "FAKE-SECRET": "FAKE-PRIVATE-NEVER-COPY",
            },
            "local_device_monitor": {
                "samples": [{"value": 36, "token": "FAKE-PRIVATE-NEVER-COPY"}]
            }
        }),
    }


class ContinuityCoverageAuditTests(unittest.TestCase):
    def test_monitor_history_scope_replays_source_coverage_not_samples(self):
        history = {
            "device_id": "101", "metric": "power", "unit": "W",
            "resolution": "5m",
            "requested_window_start_utc": "2026-04-01T12:00:00Z",
            "requested_window_end_exclusive_utc": "2026-04-01T18:00:00Z",
            "returned_window_start_utc": "2026-04-01T12:00:00Z",
            "returned_window_end_utc": "2026-04-01T18:00:00Z",
            "expected_bin_positions": 72,
            "bins_with_saved_values": 70,
            "bins_containing_monitor_received_power_reports": 67,
            "bins_held_from_previous_power_report": 3,
            "explicit_null_bin_positions": 2,
            "absent_bin_positions": 0,
            "all_saved_bin_values_present": False,
            "source_completeness_verified": False,
            "source_verified_continuous_physical_observation": False,
            "source_verified_device_connection_or_offline_cause": False,
            "source_verified_exact_physical_threshold_crossing_time": False,
            "fresh_sensor_reports_independently_verified": False,
            "secret_token": "FAKE-PRIVATE-NEVER-COPY",
        }
        receipt = monitor_receipt(history)
        before = json.dumps(receipt, sort_keys=True)
        indexed = json.loads(final_claim_receipt_scope_index([receipt]))
        got = indexed["indexed_receipts"][0]["monitor_scope"]["history"]
        for key, value in history.items():
            if key == "secret_token":
                self.assertNotIn(key, got)
            else:
                self.assertEqual(got[key], value)
        self.assertFalse(got["source_verified_continuous_physical_observation"])
        self.assertFalse(got["source_completeness_verified"])
        self.assertEqual(got["explicit_null_bin_positions"], 2)
        self.assertNotIn("FAKE-PRIVATE-NEVER-COPY", json.dumps(indexed))
        self.assertNotIn("samples", json.dumps(indexed))
        self.assertEqual(before, json.dumps(receipt, sort_keys=True))

    def test_current_state_and_attribute_filtered_history_are_not_interval_proof(self):
        # Valid current ON snapshot but narrow past event filter cannot establish
        # historical switch state across the requested six-hour window.
        snapshot = {
            "name": "hub_list_devices", "arguments": {"labelFilter": "LAB-HEATER"},
            "success": True, "response": json.dumps({
                "content": [{"type": "text", "text": json.dumps({
                    "devices": [{"id": "101", "currentStates": {"switch": "on"}}]
                })}]
            })
        }
        event_history = {
            "name": "hub_list_device_events",
            "arguments": {"deviceId": "101", "hoursBack": 6,
                          "attribute": "power"},
            "success": True, "response": json.dumps({
                "client_claim_evidence_headline": {
                    "source_kind": "bounded returned device event rows",
                    "returned_row_count": 14,
                    "oldest_returned_event": "2026-04-01T17:30:00Z",
                    "newest_returned_event": "2026-04-01T18:00:00Z",
                    "unseen_rows_or_commands_proven_absent": False,
                },
                "content": [{"type": "text", "text": json.dumps({
                    "attributeFilter": "power", "count": 14,
                    "sinceTimestamp": "2026-04-01T12:00:00Z",
                    "events": []
                })}],
            }),
        }
        items = json.loads(
            final_claim_receipt_scope_index([snapshot, event_history])
        )["indexed_receipts"]
        self.assertNotIn("monitor_scope", items[0])
        self.assertEqual(items[1]["source_headline"]["returned_row_count"], 14)
        self.assertEqual(items[1]["original_returned_fields"]["attributeFilter"], "power")
        self.assertEqual(items[1]["original_returned_fields"]["sinceTimestamp"],
                         "2026-04-01T12:00:00Z")
        self.assertIn("CURRENT status", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("complementary state history", FINAL_CLAIM_AUDIT_PROMPT)

    def test_failed_history_read_is_not_successfully_empty(self):
        failed = monitor_receipt({
            "source_verified_continuous_physical_observation": True,
            "expected_bin_positions": 200
        }, success=False)
        index = json.loads(final_claim_receipt_scope_index([failed]))
        self.assertTrue(index["indexed_receipts"][0]["read_failed"])
        self.assertNotIn("monitor_scope", index["indexed_receipts"][0])
        self.assertFalse(index["indexed_receipts"][0]["no_matching_records_proven"])

    def test_cross_domain_model_review_remains_optional_read_only(self):
        # Review guidance is broad: it applies to power, motion, heating and
        # connectivity without naming a real device, tool or forced read.
        for phrase in (
            "state CONTINUOUSLY", "historical power bins",
            "historical state", "READ-ONLY state/transition source",
            "Do not mandate a history call", "interruptions",
        ):
            # Some concepts appear across the two existing stages.
            self.assertIn(phrase, MEASUREMENT_REVIEW_PROMPT +
                          FINAL_CLAIM_AUDIT_PROMPT)
        for prohibited in (
            "Bedroom 3 PC", "Hallway Light 1",
            "hub_list_device_events(attribute=power)",
        ):
            self.assertNotIn(prohibited,
                             MEASUREMENT_REVIEW_PROMPT + FINAL_CLAIM_AUDIT_PROMPT)


if __name__ == "__main__":
    unittest.main()

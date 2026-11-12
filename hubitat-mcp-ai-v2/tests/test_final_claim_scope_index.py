"""Fictional regression tests for source-bounded final-answer audit context.

These inspect returned receipt provenance only. They do not simulate a live
device event or prove that a provider model will obey the audit guidance.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from investigation_review import (
    FINAL_CLAIM_AUDIT_PROMPT, final_claim_receipt_scope_index,
)


def receipt(name, args, result, *, success=True, **extra):
    return {
        "name": name, "arguments": args, "success": success,
        "response": json.dumps(result), **extra,
    }


class FinalClaimScopeIndexTests(unittest.TestCase):
    def test_filtered_and_unfiltered_histories_keep_different_scopes(self):
        filtered = receipt(
            "hub_list_device_events",
            {"deviceId": "SYN-100", "attribute": "switch", "limit": 20},
            {
                "client_claim_evidence_headline": {
                    "source_kind": "bounded returned device event rows",
                    "returned_row_count": 2,
                    "requested_row_limit": 20,
                    "row_limit_reached": False,
                    "requested_attribute_filter": "switch",
                    "observed_command_row_count": 0,
                    "unseen_rows_or_commands_proven_absent": False,
                },
                "client_event_source_scope": {
                    "source_scope": "returned event rows only",
                    "can_infer_unseen_commands_absent": False,
                    "can_infer_requested_window_fully_covered": False,
                    "can_infer_external_or_manual_initiation_from_physical_tag": False,
                },
                "content": [{"type": "text", "text": json.dumps({
                    "events": [{"name": "switch", "value": "off"}], "count": 2,
                    "attributeFilter": "switch",
                })}],
            },
        )
        unfiltered = receipt(
            "hub_list_device_events",
            {"deviceId": "SYN-100", "since": "2026-08-01T22:00:00Z",
             "until": "2026-08-01T22:03:00Z", "limit": 50},
            {
                "client_claim_evidence_headline": {
                    "returned_row_count": 1,
                    "requested_row_limit": 50,
                    "row_limit_reached": False,
                    "requested_attribute_filter": None,
                    "unseen_rows_or_commands_proven_absent": False,
                },
                "content": [{"type": "text", "text": json.dumps({
                    "count": 1, "attributeFilter": None,
                    "sinceTimestamp": "2026-08-01T22:00:00Z",
                    "untilTimestamp": "2026-08-01T22:03:00Z",
                    "events": [{"name": "switch", "value": "off"}],
                })}],
            },
        )
        data = json.loads(final_claim_receipt_scope_index([filtered, unfiltered]))
        first, second = data["indexed_receipts"]
        self.assertEqual(first["arguments"]["attribute"], "switch")
        self.assertEqual(first["source_headline"]["observed_command_row_count"], 0)
        self.assertIs(first["event_scope"]["can_infer_unseen_commands_absent"], False)
        self.assertEqual(second["arguments"]["since"], "2026-08-01T22:00:00Z")
        self.assertEqual(second["arguments"]["until"], "2026-08-01T22:03:00Z")
        self.assertIsNone(second["source_headline"]["requested_attribute_filter"])
        self.assertEqual(second["original_returned_fields"]["count"], 1)
        self.assertIs(data["indexed_receipts"][0]["success"], True)
        self.assertIn("not independent evidence", data["note"])

    def test_named_text_log_search_has_only_matching_count_and_pattern(self):
        log = receipt(
            "hub_get_logs",
            {"mode": "past", "pattern": "Fictional lamp",
             "since": "2026-08-01T22:00:00Z",
             "until": "2026-08-01T22:03:00Z", "level": "all"},
            {"content": [{"type": "text", "text": json.dumps({
                "mode": "past", "matched": 0, "total": 1900,
                "entries": [], "count": 0,
                "hiddenSecret": "NEVER_EXPOSE_LOG_CONTENT",
            })}]},
        )
        s = final_claim_receipt_scope_index([log])
        record = json.loads(s)["indexed_receipts"][0]
        self.assertEqual(record["arguments"]["pattern"], "Fictional lamp")
        self.assertEqual(record["original_returned_fields"]["matched"], 0)
        self.assertEqual(record["original_returned_fields"]["total"], 1900)
        self.assertNotIn("NEVER_EXPOSE_LOG_CONTENT", s)
        self.assertNotIn('"entries"', s)
        self.assertIn("text-pattern log search", FINAL_CLAIM_AUDIT_PROMPT)

    def test_positive_command_evidence_and_failed_calls_not_silently_excluded(self):
        found = receipt(
            "hub_list_device_events",
            {"deviceId": "SYN-101", "limit": 15},
            {
                "client_claim_evidence_headline": {
                    "returned_row_count": 2,
                    "observed_command_row_count": 1,
                    "unseen_rows_or_commands_proven_absent": False,
                },
                "content": [{"type": "text", "text": json.dumps({
                    "events": [{"name": "command-off",
                                "producedBy": {"name": "Fictional writer"}},
                               {"name": "switch", "value": "off"}],
                    "count": 2,
                })}],
            },
        )
        rejected = {
            "name": "hub_get_app_config",
            "arguments": {"appId": "SYN-APP"},
            "success": False, "result_kind": "contract_error",
            "error": "Invalid arguments", "response": '{"error": "bad"}',
        }
        rows = json.loads(final_claim_receipt_scope_index([found, rejected]))[
            "indexed_receipts"]
        self.assertEqual(rows[0]["source_headline"]["observed_command_row_count"], 1)
        self.assertTrue(rows[1]["read_failed"])
        self.assertNotIn("Fictional writer",
                         final_claim_receipt_scope_index([found, rejected]))
        self.assertIn("Preserve positive findings", FINAL_CLAIM_AUDIT_PROMPT)

    def test_private_payloads_skipped_and_manifest_explicitly_bounded(self):
        sensitive = receipt(
            "homebrain_read_device_monitor",
            {"mode": "history", "metric": "humidity", "deviceId": "SYN-200",
             "access_token": "DO_NOT_LEAK", "payload": "SECRET_PAYLOAD"},
            {"client_monitor_evidence_scope": {
                "source_kind": "separate saved-device-history archive",
                "source_note": "NOT_A_SAFE_SOURCE_NOTE",
                "fresh_sensor_reports_independently_verified": False,
                "history": {"source_kind": "5m saved bins",
                            "fresh_sensor_reports_independently_verified": False,
                            "raw_data": "A_PRIVATE_SAMPLE"},
            }, "local_device_monitor": {"samples": ["PRIVATE_SAMPLES"]}},
        )
        rows = [sensitive] * 18
        result = final_claim_receipt_scope_index(rows)
        data = json.loads(result)
        self.assertEqual(len(data["indexed_receipts"]), 16)
        self.assertEqual(data["additional_receipts_not_indexed"], 2)
        self.assertNotIn("DO_NOT_LEAK", result)
        self.assertNotIn("SECRET_PAYLOAD", result)
        self.assertNotIn("A_PRIVATE_SAMPLE", result)
        self.assertNotIn("PRIVATE_SAMPLES", result)
        self.assertIs(data["indexed_receipts"][0]["monitor_scope"][
            "fresh_sensor_reports_independently_verified"], False)


if __name__ == "__main__":
    unittest.main()

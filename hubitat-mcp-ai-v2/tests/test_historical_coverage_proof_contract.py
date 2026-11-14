"""Synthetic cross-domain coverage proof contracts: no hub or model access."""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from investigation_review import (
    FINAL_CLAIM_AUDIT_PROMPT, final_claim_receipt_scope_index,
)


def native_history_receipt(event_names=None, *, success=True, cover=None):
    scope = {
        "source_scope": "returned event rows only",
        "events_returned": 88,
        "oldest_returned_event": "2030-05-02T18:46:30.007+0000",
        "newest_returned_event": "2030-05-02T21:57:27.503+0000",
        "requested_lookback_hours": 4,
        "requested_limit": 100,
        "limit_reached": False,
        "largest_gap_between_returned_events_seconds": 6919.017,
        "can_infer_uninterrupted_state_between_events": False,
        "can_infer_requested_window_fully_covered": False,
        "can_infer_older_events_absent": False,
        "native_store_checked_independently": False,
        "can_infer_cause_of_missing_records": False,
        "requested_attribute_filter": None,
        "can_infer_initiator_from_state_report_producer": False,
        "can_infer_initiator_from_triggered_listeners": False,
        "FAKE_SECRET": "FAKE-PRIVATE-NEVER-COPY",
    }
    if cover:
        scope.update(cover)
    envelope = {
        "client_claim_evidence_headline": {
            "source_kind": "bounded returned device event rows",
            "returned_row_count": 88,
            "requested_row_limit": 100,
            "row_limit_reached": False,
            "source_scope": "returned rows only, not complete historical coverage",
            "FAKE_PRIVATE": "FAKE-PRIVATE-NEVER-COPY",
        },
        "client_event_source_scope": scope,
        "client_event_attribute_scope": {
            "event_names": event_names or [
                {"event_name": "mqttStatus", "returned_count": 2},
                {"event_name": "power", "returned_count": 11},
                {"event_name": "healthStatus", "returned_count": 2},
            ]
        },
        "content": [{"type": "text", "text": json.dumps({
            "deviceId": "LAB-101", "events": [], "count": 88,
            "sinceTimestamp": "2030-05-02T17:57:27.313+0000",
            "attributeFilter": None,
        })}],
    }
    return {
        "name": "hub_list_device_events",
        "arguments": {"deviceId": "LAB-101", "hoursBack": 4, "limit": 100},
        "success": success, "response": json.dumps(envelope),
    }


class CoverageProofContractTests(unittest.TestCase):
    def test_native_false_flags_survive_under_limit_and_missing_attribute(self):
        source = native_history_receipt()
        before = json.dumps(source, sort_keys=True)
        result = json.loads(final_claim_receipt_scope_index([source]))
        item = result["indexed_receipts"][0]
        self.assertTrue(item["success"])
        self.assertEqual(item["source_headline"]["returned_row_count"], 88)
        self.assertFalse(item["source_headline"]["row_limit_reached"])
        self.assertEqual(item["event_scope"]["largest_gap_between_returned_events_seconds"],
                         6919.017)
        self.assertFalse(item["event_scope"]["can_infer_uninterrupted_state_between_events"])
        self.assertFalse(item["event_scope"]["can_infer_requested_window_fully_covered"])
        self.assertFalse(item["event_scope"]["can_infer_older_events_absent"])
        self.assertFalse(item["event_scope"]["native_store_checked_independently"])
        self.assertEqual(item["event_scope"]["requested_lookback_hours"], 4)
        self.assertEqual(item["event_names_in_returned_rows"]["returned_event_name_counts"],
                         [{"event_name": "mqttStatus", "returned_count": 2},
                          {"event_name": "power", "returned_count": 11},
                          {"event_name": "healthStatus", "returned_count": 2}])
        proof = item["historical_continuity_proof_obligations"]
        self.assertFalse(proof["uninterrupted_state_supported_by_this_source"])
        self.assertFalse(proof["requested_window_coverage_supported_by_this_source"])
        self.assertFalse(proof["older_events_excluded_by_this_source"])
        self.assertTrue(proof["zero_matching_rows_not_proof_of_no_transition"])
        self.assertTrue(proof["row_limit_not_reached_not_completeness_proof"])
        self.assertNotIn("FAKE-PRIVATE", json.dumps(result))
        self.assertEqual(json.dumps(source, sort_keys=True), before)

    def test_generality_across_thermal_and_motion_event_names(self):
        for names in (
            [{"event_name": "thermostatOperatingState", "returned_count": 9}],
            [{"event_name": "motion", "returned_count": 18}],
            [{"event_name": "switch", "returned_count": 0}],
        ):
            with self.subTest(names=names):
                result = json.loads(final_claim_receipt_scope_index([
                    native_history_receipt(names)
                ]))
                item = result["indexed_receipts"][0]
                self.assertFalse(item["historical_continuity_proof_obligations"]
                                 ["uninterrupted_state_supported_by_this_source"])
                self.assertEqual(item["event_names_in_returned_rows"]
                                 ["returned_event_name_counts"], names)

    def test_no_source_flag_does_not_invent_completeness_or_negative_proof(self):
        rec = native_history_receipt(cover={
            "can_infer_uninterrupted_state_between_events": None,
            "can_infer_requested_window_fully_covered": None,
            "can_infer_older_events_absent": None,
            "native_store_checked_independently": None,
        })
        item = json.loads(final_claim_receipt_scope_index([rec]))["indexed_receipts"][0]
        self.assertNotIn("historical_continuity_proof_obligations", item)
        self.assertIsNone(item["event_scope"]["can_infer_older_events_absent"])

    def test_failed_history_not_an_empty_or_valid_proof(self):
        rec = native_history_receipt(success=False)
        item = json.loads(final_claim_receipt_scope_index([rec]))["indexed_receipts"][0]
        self.assertTrue(item["read_failed"])
        self.assertFalse(item["no_matching_records_proven"])
        self.assertNotIn("historical_continuity_proof_obligations", item)
        self.assertNotIn("event_scope", item)

    def test_independent_monitor_saved_bins_do_not_upgrade_continuity_proof(self):
        native = native_history_receipt()
        monitor = {
            "name": "homebrain_read_device_monitor",
            "arguments": {"mode": "history", "metric": "power", "range": "4h"},
            "success": True,
            "response": json.dumps({"client_monitor_evidence_scope": {
                "source_kind": "separate saved-device-history archive",
                "history": {
                    "expected_bin_positions": 48, "bins_with_saved_values": 45,
                    "bins_held_from_previous_power_report": 4,
                    "explicit_null_bin_positions": 3,
                    "source_verified_continuous_physical_observation": False,
                    "source_completeness_verified": False,
                },
            }}),
        }
        items = json.loads(final_claim_receipt_scope_index(
            [native, monitor]))["indexed_receipts"]
        self.assertFalse(items[0]["historical_continuity_proof_obligations"]
                         ["uninterrupted_state_supported_by_this_source"])
        self.assertFalse(items[1]["monitor_scope"]["history"]
                         ["source_verified_continuous_physical_observation"])
        self.assertEqual(items[1]["monitor_scope"]["history"]
                         ["explicit_null_bin_positions"], 3)

    def test_prompt_confronts_false_flag_and_closed_world_fallacy(self):
        self.assertIn("Source-declared FALSE coverage guarantees", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("row limit NOT reached", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("zero matching transitions returned", " ".join(FINAL_CLAIM_AUDIT_PROMPT.split()))
        self.assertIn("no transitions occurred", " ".join(FINAL_CLAIM_AUDIT_PROMPT.split()))
        self.assertNotIn("Freezer", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertNotIn("Bedroom 3 PC", FINAL_CLAIM_AUDIT_PROMPT)


class FinalAuditToolIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_final_round_receives_proof_contract_without_new_reads(self):
        class FictionalMCP:
            def __init__(self):
                self.calls = []
            async def list_tools(self, refresh=False):
                return [{"name": "hub_list_device_events", "description": "Read native events",
                         "inputSchema": {"type": "object",
                                         "properties": {"deviceId": {"type": "string"}}}}]
            async def call(self, name, args):
                self.calls.append((name, args))
                return json.loads(native_history_receipt()["response"])

        class FictionalModel(Agent):
            def __init__(self):
                super().__init__("http://127.0.0.1:11434", "synthetic", "", 20)
                self.rounds_seen = 0
                self.audit_tools = None
                self.audit_prompt = ""
            async def round(self, messages, tools, remaining):
                self.rounds_seen += 1
                if self.rounds_seen == 1:
                    return {"tool_calls": [{"function": {
                        "name": "hub_list_device_events",
                        "arguments": {"deviceId": "LAB-101"}}}]}
                if self.rounds_seen == 2:
                    return {"content": "No switches changed throughout the period."}
                if self.rounds_seen == 3:
                    return {"content": "No switch event was returned; the interval state "
                                       "cannot be established from this source alone."}
                self.audit_tools = tools
                self.audit_prompt = messages[-1]["content"]
                return {"content": "Only the native event rows were inspected. A state "
                                   "transition may have occurred in unreturned history."}

        model, mcp = FictionalModel(), FictionalMCP()
        try:
            result = await model.answer(
                "Investigate why a fictional outlet most recently switched OFF "
                "and whether it had been ON continuously for 4 hours. "
                "Do not change anything.", [], mcp, 90,
                enable_causal_follow_through=False,
            )
        finally:
            await model.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"], 4)
        self.assertTrue(result["final_claim_audit_invoked"])
        self.assertEqual(model.audit_tools, [])
        self.assertEqual(len(mcp.calls), 1)
        self.assertIn('"uninterrupted_state_supported_by_this_source":false',
                      model.audit_prompt)
        self.assertIn('"row_limit_not_reached_not_completeness_proof":true',
                      model.audit_prompt)
        self.assertIn("unreturned history", result["answer"])


if __name__ == "__main__":
    unittest.main()

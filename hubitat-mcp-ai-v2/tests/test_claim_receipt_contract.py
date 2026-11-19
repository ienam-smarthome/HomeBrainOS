"""Shadow typed facts preserve source scope without changing publication."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from claim_receipt_contract import build_claim_receipt_contract
from test_read_only_receipt_fallback import ARGS_OUT, FakeMCP, ScriptedAgent, tool_call


def receipt(tool, args, native, **extra):
    return {
        "name": tool, "arguments": args, "success": True,
        "response": json.dumps({"content": [
            {"type": "text", "text": json.dumps(native)},
        ]}), **extra,
    }


class ClaimReceiptContractTests(unittest.TestCase):
    def test_inventory_keeps_typed_values_and_does_not_infer_completeness(self):
        source = receipt("hub_list_devices", {
            "format": "summary", "attributeNames": ["battery"],
            "labelFilter": "private label",
        }, {
            "devices": [
                {"id": "1", "label": "private", "currentStates": {"battery": "91"}},
                {"id": "2", "currentStates": {"battery": "100"}},
            ], "count": 2, "total": 2,
        })
        result = build_claim_receipt_contract("count batteries", "Two", [source])
        packet = result["typed_receipts"][0]
        self.assertEqual([fact["value"] for fact in packet["facts"]], ["91", "100"])
        self.assertTrue(packet["coverage"]["returned_equals_reported_total"])
        self.assertNotIn("private", json.dumps(result))
        self.assertFalse(result["enforced"])
        self.assertFalse(result["answer_changed"])

    def test_empty_history_never_becomes_absence_or_window_proof(self):
        source = receipt("hub_list_device_events", {
            "appId": 7, "hoursBack": 24, "limit": 50,
        }, {"appId": 7, "events": [], "count": 0})
        packet = build_claim_receipt_contract(
            "what happened", "No rows returned", [source],
        )["typed_receipts"][0]
        self.assertEqual(packet["coverage"]["returned_rows"], 0)
        self.assertFalse(packet["coverage"]["requested_window_completeness_proven"])
        self.assertFalse(packet["coverage"]["absence_of_unreturned_records_proven"])

    def test_current_and_event_values_receive_stable_fact_ids(self):
        current = receipt("hub_get_device", {"deviceId": "9"}, {
            "id": "9", "label": "private TV", "attributes": [
                {"name": "energy", "value": 782.35},
                {"name": "switch", "value": "off"},
            ],
        })
        history = receipt("hub_list_device_events", {
            "deviceId": 9, "attribute": "energy", "limit": 5,
        }, {"deviceId": 9, "events": [
            {"name": "energy", "value": "782.35",
             "date": "2026-11-18T12:06:22+00:00"},
        ]})
        result = build_claim_receipt_contract("compare energy", "answer", [current, history])
        self.assertEqual(result["typed_receipts"][0]["facts"][0]["fact_id"], "r1.state.1")
        self.assertEqual(result["typed_receipts"][1]["facts"][0]["fact_id"], "r2.event.1")
        self.assertEqual(result["summary"]["typed_facts"], 3)

    def test_log_groups_are_counted_without_copying_messages_or_source_names(self):
        source = receipt("hub_get_logs", {
            "mode": "past", "level": "error", "since": "4h", "limit": 0,
        }, {"total": 100, "matched": 3, "entries": [
            {"name": "Private app", "level": "ERROR", "message": "secret one"},
            {"name": "Private app", "level": "ERROR", "message": "secret two"},
            {"name": "Other app", "level": "ERROR", "message": "secret three"},
        ]})
        result = build_claim_receipt_contract("summarize", "answer", [source])
        packet = result["typed_receipts"][0]
        self.assertEqual(packet["requested_scope"]["since"], "4h")
        self.assertEqual(sorted(fact["returned_rows"] for fact in packet["facts"]), [1, 2])
        encoded = json.dumps(result)
        self.assertNotIn("Private app", encoded)
        self.assertNotIn("secret", encoded)
        self.assertFalse(packet["coverage"]["requested_window_completeness_proven"])
        self.assertEqual(packet["coverage"]["reported_total_scope"],
                         "source_unspecified_not_query_coverage")

    def test_failed_or_nonexecuted_receipts_never_create_facts(self):
        failed = {**receipt("hub_list_devices", {}, {"devices": [{"id": "1"}]}),
                  "success": False}
        skipped = {**receipt("hub_get_info", {}, {"uptimeSeconds": 10}),
                   "operation_executed": False}
        result = build_claim_receipt_contract("q", "a", [failed, skipped])
        self.assertEqual([packet["facts"] for packet in result["typed_receipts"]], [[], []])
        self.assertEqual(result["summary"]["successful_executed_receipts"], 0)


class ClaimReceiptContractAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_completed_answer_exposes_shadow_contract_without_extra_reads(self):
        hub = FakeMCP()
        model = ScriptedAgent(
            tool_call("hub_list_device_events", ARGS_OUT),
            {"content": "The returned row reports an idle state."},
        )
        try:
            result = await model.answer(
                "Report the fixture's returned state. Do not change anything.",
                [], hub, 90, enable_source_review=False,
            )
        finally:
            await model.close()
        shadow = result["claim_receipt_contract_shadow"]
        self.assertEqual(shadow["schema"],
                         "homebrain-v2-claim-receipt-contract-shadow.v1")
        self.assertFalse(shadow["enforced"])
        self.assertFalse(shadow["answer_changed"])
        self.assertEqual(shadow["claim_bindings"], [])
        self.assertEqual(len(hub.calls), 1)
        self.assertIn("idle state", result["answer"])


if __name__ == "__main__":
    unittest.main()

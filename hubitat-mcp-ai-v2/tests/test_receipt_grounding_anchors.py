"""Source grounding uses original identities, source clocks and bounded counts."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from investigation_review import final_claim_receipt_scope_index
from read_only_receipt_fallback import source_only_partial_answer
from receipt_grounding_anchors import receipt_grounding_anchors


def receipt(name, arguments, native, **details):
    return {"name": name, "arguments": arguments, "success": True,
            "response": json.dumps({"content": [
                {"type": "text", "text": json.dumps(native)},
            ]}), **details}


class GroundingTests(unittest.TestCase):
    def history(self):
        return receipt("hub_list_device_events", {"deviceId": 700, "limit": 20}, {
            "source": "device", "deviceId": 700, "device": "Fixture light",
            "events": [
                {"name": "switch", "value": "off", "date": "2026-11-18T07:30:54+0000",
                 "type": "physical", "producedBy": {"deviceId": 710},
                 "triggered": [{"appId": 720}, {"appId": 720}]},
                {"name": "command-setLevel", "type": "command",
                 "date": "2026-11-18T07:30:30+0000", "producedBy": {"appId": 730}},
                {"name": "switch", "value": "on", "date": "2026-07-18T07:30:54+0000",
                 "producedBy": {"appId": 740}},
                {"name": "switch", "deviceId": 999, "value": "off",
                 "date": "2026-12-18T07:30:54+0000"},
                {"name": "switch", "value": "off", "date": "2026-12-18T07:30:54"},
            ],
        })

    def test_roles_and_winter_and_summer_clocks_remain_distinct(self):
        result = json.loads(final_claim_receipt_scope_index(
            [self.history()], timezone_name="Europe/London",
        ))
        winter, summer, command = result["receipt_grounding_anchors"][0]["events"]
        self.assertEqual(winter["notified_app_ids"], ["720"])
        self.assertEqual(winter["reporter_device_id"], "710")
        self.assertNotIn("recorded_issuer_app_id", winter)
        self.assertEqual(winter["hub_display_time"], "Wednesday 2026-11-18 07:30:54 GMT (+0000)")
        self.assertEqual(summer["hub_display_time"], "Saturday 2026-07-18 08:30:54 BST (+0100)")
        self.assertEqual(summer["reporter_app_id"], "740")
        self.assertNotIn("recorded_issuer_app_id", summer)
        self.assertEqual(command["recorded_issuer_app_id"], "730")
        self.assertNotIn("notified_app_ids", command)

    def test_counts_keep_scope_and_failed_reads_do_not_create_anchors(self):
        log = receipt("hub_get_logs", {"mode": "past", "since": "6h", "limit": 10},
                      {"total": 1000, "matched": 2, "entries": [{}]})
        failed = {**log, "success": False}
        unevaluated = {**log, "operation_executed": False}
        inventory = receipt("hub_list_devices", {"cursor": "10"},
                            {"total": 100, "hasMore": False, "devices": [{}]})
        self.assertEqual(receipt_grounding_anchors(
            [failed, log, unevaluated, inventory], "Europe/London",
        ), [
            {"receipt_number": 2, "returned_rows": 1, "reported_total_scope_unspecified": 1000,
             "matched_rows": 2, "requested_interval_completeness_established": False},
            {"receipt_number": 4, "returned_rows": 1, "reported_inventory_total": 100,
             "native_has_more": False},
        ])

    def test_partial_keeps_listener_attached_to_report(self):
        answer = source_only_partial_answer(
            "Why did the fixture light switch off?", [self.history()],
        )
        self.assertIn("07:30:54 GMT (+0000) — notified app IDs 720", answer)
        self.assertIn("A recorded command issuer is not proof", answer)

"""Alpha154 fictional original-source regressions; no Hubitat or cloud network."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rootfs" / "app"))
from claim_receipt_contract import build_claim_receipt_contract
from event_sequence_publication import source_sequence_publication_check
from historical_publication import historical_publication_check
from inventory_read_limits import (
    detailed_inventory_block_reason, inventory_failure_recovery_note,
)
from memory_window_provenance import (
    memory_history_window_index, verify_memory_window_publication,
)
from native_past_log_receipt import original_past_log_source
from read_only_receipt_fallback import source_only_partial_answer
from receipt_grounding_anchors import receipt_grounding_anchors
from test_read_only_receipt_fallback import ScriptedAgent, tool_call


def receipt(tool, args, native, *, success=True, executed=True):
    return {"name": tool, "arguments": args, "success": success,
            "operation_executed": executed,
            "response": json.dumps({"content": [
                {"type": "text", "text": json.dumps(native)},
            ]})}


WARN = {"total": 11281, "matched": 5, "count": 5,
        "entries": [
            *[{"name": "Fixture Weather", "level": "ERROR",
               "message": "TOKEN=DO_NOT_PUBLISH"} for _ in range(3)],
            *[{"name": "Fixture Fan", "level": "ERROR",
               "message": "TOKEN=DO_NOT_PUBLISH"} for _ in range(2)],
        ]}
ARGS = {"mode": ["past"], "level": "error", "since": "3h", "limit": 0}


class LogSourceTests(unittest.TestCase):
    def test_nested_past_log_has_real_rows_without_scan_scope(self):
        r = receipt("hub_get_logs", ARGS, {"modes": {"past": WARN}})
        parsed = original_past_log_source(r)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[2], "modes.past")
        self.assertEqual(len(parsed[1]["entries"]), 5)
        shadow = build_claim_receipt_contract("summarise log", "answer", [r])
        typed = shadow["typed_receipts"][0]
        self.assertEqual(typed["source_envelope_variant"], "modes.past")
        self.assertEqual(typed["coverage"]["returned_rows"], 5)
        self.assertEqual(typed["coverage"]["reported_total_scope"],
                         "source_unspecified_not_query_coverage")
        self.assertEqual(sorted(f["returned_rows"] for f in typed["facts"]), [2, 3])
        anchor = receipt_grounding_anchors([r], "Europe/London")[0]
        self.assertEqual(anchor["returned_rows"], 5)
        self.assertEqual(anchor["reported_total_scope_unspecified"], 11281)
        partial = source_only_partial_answer("What ERROR logs were returned?", [r])
        self.assertIn("Fixture Weather: 3", partial)
        self.assertIn("Fixture Fan: 2", partial)
        self.assertIn("11281", partial)
        self.assertNotIn("DO_NOT_PUBLISH", partial)
        rejected = historical_publication_check(
            "Aggregate total (hub entries scanned for the query): 11281.", [r]
        )
        self.assertEqual(rejected[0], "unverified_native_log_total_scope")

    def test_direct_past_and_untrusted_non_past_are_separate(self):
        direct = receipt("hub_get_logs", {"mode": "past"}, {"mode": "past", **WARN})
        self.assertEqual(original_past_log_source(direct)[2], "mode.past_direct")
        self.assertEqual(build_claim_receipt_contract("x", "y", [direct])[
            "typed_receipts"][0]["coverage"]["returned_rows"], 5)
        for args, data in (
            ({"mode": ["live", "past"]}, {"modes": {"past": WARN}}),
            ({"mode": "live"}, {"modes": {"past": WARN}}),
            ({"mode": "past"}, {"modes": {"live": WARN}}),
        ):
            self.assertIsNone(original_past_log_source(
                receipt("hub_get_logs", args, data)))
        failed = receipt("hub_get_logs", ARGS, {"modes": {"past": WARN}},
                         success=False)
        self.assertIsNone(original_past_log_source(failed))

    def test_offline_audit_recognises_nested_without_exposing_log_data(self):
        file = ROOT / "tools" / "first_answer_audit.py"
        spec = importlib.util.spec_from_file_location("v2_alpha154_faa", file)
        audit = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = audit
        spec.loader.exec_module(audit)
        from test_first_answer_audit import fixture
        exported = fixture()
        exported["response"]["tool_calls"] = [
            receipt("hub_get_logs", ARGS, {"modes": {"past": WARN}}),
        ]
        review = audit.audit_export(exported)
        self.assertEqual(review["log_receipts"]["source_receipts"], 1)
        self.assertEqual(review["log_receipts"]["rows_returned_total"], 5)
        self.assertNotIn("Fixture Weather", json.dumps(review))
        self.assertEqual(review["log_receipts"]["all_log_windows_complete"],
                         "not_established")


HISTORY = {
    "source": "device", "deviceId": 9120, "device": "Fixture Plug",
    "events": [
        {"name": "command-off", "type": "command",
         "date": "2030-11-20T13:30:04.553+0000", "producedBy": {"appId": 999}},
        {"name": "healthStatus", "value": "offline",
         "date": "2030-11-20T13:01:16.757+0000"},
        {"name": "healthStatus", "value": "unknown",
         "date": "2030-11-20T13:00:51.685+0000"},
    ],
}


class SequenceContractTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            receipt("hub_get_device", {"deviceId": "9120"}, {
                "id": "9120", "attributes": [
                    {"name": "switch", "value": "on"},
                    {"name": "healthStatus", "value": "offline"},
                ],
            }),
            receipt("hub_list_device_events",
                    {"deviceId": 9120, "limit": 10}, HISTORY),
        ]

    def test_undated_on_cannot_prove_turned_back_on(self):
        prose = (
            "The stored switch reports on, indicating the plug was turned "
            "back on after the command, likely by a manual action."
        )
        evidence = source_sequence_publication_check("what happened?", prose, self.rows)
        self.assertEqual(evidence["status"], "unsafe")
        self.assertIn("intervening_switch_change_not_in_returned_events",
                      evidence["reason"])
        self.assertIn("1727.796 seconds after", evidence["source_note"])
        self.assertIn("healthStatus", evidence["source_note"])
        self.assertFalse(source_sequence_publication_check(
            "what happened?",
            "It might have been turned back on; no such dated event was returned.",
            self.rows,
        )["status"] == "unsafe")

    def test_backward_command_vs_health_story_is_rejected(self):
        prose = "The most recent command was just seconds before the health-status update."
        result = source_sequence_publication_check("health?", prose, self.rows)
        self.assertEqual(result["status"], "unsafe")
        self.assertIn("command_status_order_contradicts", result["reason"])

    def test_health_status_event_not_dated_energy_measurement(self):
        report = (
            "**Latest dated measurement** — Attribute: healthStatus, "
            "value offline at 2030-11-20T13:01:16.757+0000."
        )
        result = source_sequence_publication_check(
            "Give the latest dated measurement event.", report, self.rows,
        )
        self.assertEqual(result["status"], "unsafe")
        self.assertIn("health_status_event_mislabelled", result["reason"])

    def test_actual_later_switch_report_justifies_observed_state(self):
        history = {**HISTORY, "events": [
            *HISTORY["events"],
            {"name": "switch", "value": "on",
             "date": "2030-11-20T13:30:10.000+0000"},
        ]}
        verified = [self.rows[0], receipt(
            "hub_list_device_events", {"deviceId": 9120}, history
        )]
        self.assertNotEqual(source_sequence_publication_check(
            "what happened?",
            "The plug was turned back on after the off command.", verified,
        )["status"], "unsafe")

    def test_native_write_not_needed_for_source_only_timeline(self):
        answer = source_only_partial_answer("what happened?", self.rows)
        self.assertIn("command-off", answer)
        self.assertIn("healthStatus", answer)


class InventoryBudgetTests(unittest.TestCase):
    def test_oversized_and_repeated_detailed_reads_are_denied_only(self):
        self.assertIn("maximum", detailed_inventory_block_reason(
            {"format": "detailed", "limit": 1000}, []))
        failed = {"name": "hub_list_devices", "success": False,
                  "arguments": {"format": "detailed", "limit": 50}}
        self.assertIsNone(detailed_inventory_block_reason(
            {"format": "detailed", "limit": 50}, [failed]))
        self.assertIn("Two detailed", detailed_inventory_block_reason(
            {"format": "detailed", "limit": 50}, [failed, failed]))
        self.assertIsNone(detailed_inventory_block_reason(
            {"format": "summary", "attributeNames": ["battery"]},
            [failed, failed]))
        self.assertTrue(inventory_failure_recovery_note(
            {"format": "detailed"})["no_client_automatic_retry"])

    async def _integration(self):
        class InventoryHub:
            def __init__(self):
                self.calls = []
            async def list_tools(self, refresh=False):
                return [{"name": "hub_list_devices",
                         "description": "Read-only inventory",
                         "inputSchema": {"type": "object",
                            "properties": {"format": {"type": "string"},
                                           "limit": {"type": "integer"}}}}]
            async def call(self, name, args):
                self.calls.append((name, args))
                if args.get("format") == "detailed":
                    return {"isError": True, "content": [{
                        "type": "text", "text": "too much detail"}]}
                return {"content": [{"type": "text",
                         "text": json.dumps({"devices": [{
                            "id": 10, "currentStates": {"battery": 90}
                         }], "count": 1, "total": 1})}]}
        hub = InventoryHub()
        def selected(fmt, limit):
            return {"content": "", "tool_calls": [{
                "function": {"name": "hub_list_devices",
                             "arguments": {"format": fmt, "limit": limit}}}]}
        model = ScriptedAgent(
            selected("detailed", 500),
            selected("detailed", 50),
            selected("detailed", 50),
            selected("detailed", 50),
            selected("summary", 0),
            {"content": "One returned summary device has battery=90."},
        )
        try:
            answer = await model.answer(
                "Count devices with battery 85 to 96 from the current inventory."
                " Do not change anything.", [], hub, 90,
                enable_source_review=False,
            )
        finally:
            await model.close()
        self.assertTrue(answer["success"])
        self.assertEqual(len(hub.calls), 3)
        self.assertEqual(sum(row["success"] is False for row
                             in answer["tool_calls"]), 4)
        self.assertIn("battery=90", answer["answer"])
        self.assertFalse(answer["action_lifecycle"]["native_write_submitted"])

    def test_recovery_integration(self):
        import asyncio
        asyncio.run(self._integration())


class MemoryWindowTests(unittest.TestCase):
    def rows(self):
        now = {"local_clock": {"client_now_utc":
                              "2030-11-20T10:00:00+00:00"}}
        return [
            {"name": "homebrain_read_clock", "arguments": {}, "success": True,
             "operation_executed": False, "response": json.dumps(now)},
            receipt("hub_get_memory_history", {"limit": 0}, {
                "entries": [
                    {"timestamp": "11-20 08:44:59", "freeMemoryKB": 5000},
                    {"timestamp": "11-20 08:45:00", "freeMemoryKB": 5100},
                    {"timestamp": "11-20 09:00:00", "freeMemoryKB": 5200},
                    {"timestamp": "11-20 09:45:00", "freeMemoryKB": 5300},
                ],
            }),
        ]

    def test_exact_75_minute_cutoff_excludes_older_sample(self):
        idx = memory_history_window_index(
            "Compare preceding 75-minute memory samples", self.rows(),
            "Europe/London",
        )
        self.assertEqual(idx["in_window_sample_count"], 3)
        self.assertEqual(idx["out_of_window_sample_count"], 1)
        self.assertEqual(idx["window_start_utc"], "2030-11-20T08:45:00+00:00")
        self.assertEqual(idx["max_returned_in_window_gap_seconds"], 2700)

    def test_rewrites_only_an_outside_requested_sample_table_row(self):
        answer = ("| UTC sample | freeMemoryKB |\n"
                  "|---|---:|\n"
                  "| 2030-11-20 08:44:59 | 5000 |\n"
                  "| 2030-11-20 08:45:00 | 5100 |")
        result = verify_memory_window_publication(
            "Compare preceding 75-minute memory samples", answer,
            self.rows(), "Europe/London",
        )
        self.assertEqual(result["status"], "unsafe")
        self.assertNotIn("| 2030-11-20T08:44:59", result["answer"])
        self.assertIn("5100", result["answer"])
        self.assertIn("unobserved", result["answer"])
        valid = verify_memory_window_publication(
            "Compare preceding 75-minute memory samples",
            "| 2030-11-20 08:45:00 | 5100 |",
            self.rows(), "Europe/London",
        )
        self.assertEqual(valid["status"], "bounded_window_index_available")


if __name__ == "__main__":
    unittest.main()

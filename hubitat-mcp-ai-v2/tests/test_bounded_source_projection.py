"""Fictional, no-network alpha155-candidate source projection regressions."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from bounded_source_projection import (
    bounded_numeric_inventory_answer,
    focused_stored_snapshot_answer,
    grouped_past_log_answer,
)
from test_read_only_receipt_fallback import ScriptedAgent, tool_call, wrapped


def receipt(name, args, payload, *, success=True):
    return {"name": name, "arguments": args, "success": success,
            "response": wrapped(payload), "result_kind": "tool_result"}


COUNT_QUESTION = (
    "Count distinct device IDs with numeric battery from 80 to 94 percent "
    "inclusive using the returned inventory. State missing values and "
    "pagination coverage. Do not change anything."
)
COUNT_ARGS = {"format": "summary", "attributeNames": ["battery"], "limit": 3}
COUNT_PAGE = {
    "devices": [
        {"id": "DEV-01", "currentStates": {"battery": "80"}},
        {"id": "DEV-02", "currentStates": {"battery": "93"}},
        {"id": "DEV-03", "currentStates": {}},
    ],
    "count": 3, "total": 4, "offset": 0, "limit": 3,
    "hasMore": True, "nextCursor": "3",
}


class SourceProjectionTests(unittest.TestCase):
    def test_count_unique_inclusive_boundaries_missing_and_unseen(self):
        r = receipt("hub_list_devices", COUNT_ARGS, COUNT_PAGE)
        before = json.dumps(r, sort_keys=True)
        answer = bounded_numeric_inventory_answer(COUNT_QUESTION, [r])
        self.assertIn("2 distinct devices", answer)
        self.assertIn("DEV-01 (80%)", answer)
        self.assertIn("DEV-02 (93%)", answer)
        self.assertIn("Missing battery values among returned IDs: 1", answer)
        self.assertIn("Not a complete inventory: 1", answer)
        self.assertEqual(before, json.dumps(r, sort_keys=True))

    def test_offset_pages_cover_all_without_double_counting(self):
        first = receipt("hub_list_devices", COUNT_ARGS, COUNT_PAGE)
        second = receipt("hub_list_devices",
                         {"format": "summary", "attributeNames": ["battery"],
                          "limit": 3, "cursor": "3"},
                         {"devices": [{"id": "DEV-04",
                                       "currentStates": {"battery": "94"}}],
                          "count": 1, "total": 4, "offset": 3,
                          "hasMore": False})
        answer = bounded_numeric_inventory_answer(COUNT_QUESTION, [first, second])
        self.assertIn("3 distinct devices", answer)
        self.assertIn("DEV-04 (94%)", answer)
        self.assertIn("cover the source-reported inventory count", answer)

    def test_failed_or_conflicting_sources_do_not_produce_claims(self):
        good = receipt("hub_list_devices", COUNT_ARGS, COUNT_PAGE)
        self.assertIsNone(bounded_numeric_inventory_answer(
            COUNT_QUESTION, [{**good, "success": False}]))
        bad = receipt("hub_list_devices", COUNT_ARGS,
                      {**COUNT_PAGE, "count": 201})
        self.assertIsNone(bounded_numeric_inventory_answer(COUNT_QUESTION, [bad]))
        conflict = receipt("hub_list_devices", COUNT_ARGS,
                           {**COUNT_PAGE, "total": 5})
        self.assertIsNone(bounded_numeric_inventory_answer(
            COUNT_QUESTION, [good, conflict]))
        self.assertIsNone(bounded_numeric_inventory_answer(
            "Turn on DEV-01", [good]))

    def test_snapshot_requires_valid_focused_source(self):
        first = receipt("hub_list_devices",
                        {"labelFilter": "Fixture One", "format": "summary"},
                        {"devices": [{"id": "DEV-01", "label": "Fixture One",
                                      "currentStates": {"switch": "on", "level": "30"}}],
                         "count": 1, "total": 1})
        second = receipt("hub_list_devices",
                         {"labelFilter": "Fixture Two", "format": "summary"},
                         {"devices": [{"id": "DEV-02", "label": "Fixture Two",
                                       "currentStates": {"switch": "off", "level": "40"}}],
                          "count": 1, "total": 1})
        question = "Compare the currently stored switch and level of Fixture One and Fixture Two."
        answer = focused_stored_snapshot_answer(question, [first, second])
        self.assertIn("Fixture One", answer)
        self.assertIn("switch = on", answer)
        self.assertIn("level = 40", answer)
        self.assertIn("no independently dated", answer.lower())
        poisoned = receipt("hub_list_devices", first["arguments"],
                           {"devices": [{"id": "DEV-01", "label": "<script>",
                                         "currentStates": {"switch": "on"}}],
                            "count": 1})
        self.assertIsNone(focused_stored_snapshot_answer(question, [poisoned]))
        self.assertIsNone(focused_stored_snapshot_answer("Why did it turn on?", [first]))

    def test_grouped_original_logs_not_aggregate_scan_or_cause(self):
        rows = [{"name": "Fixture Vent", "level": "WARN", "message": "secret",
                 "time": "2030-11-01 10:01:01"} for _ in range(2)]
        rows.append({"name": "Fixture Heater", "level": "WARN",
                     "message": "secret", "time": "2030-11-01 10:02:02"})
        r = receipt("hub_get_logs", {"mode": "past", "level": "warn",
                                     "since": "4h"},
                    {"mode": "past", "total": 9000, "matched": 8,
                     "count": 3, "entries": rows})
        ans = grouped_past_log_answer(
            "Summarize returned past-log entries by source and distinguish "
            "reported matches from source aggregate total.", [r])
        self.assertIn("Fixture Vent: 2", ans)
        self.assertIn("Fixture Heater: 1", ans)
        self.assertNotIn("secret", ans)
        self.assertIn("not established", ans)
        self.assertIsNone(grouped_past_log_answer("Turn off heater", [r]))


class FakeProjectionHub:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_list_devices", "description": "Read fictional inventory",
             "inputSchema": {"type": "object", "properties": {
                 "format": {"type": "string"}, "attributeNames": {
                     "type": "array", "items": {"type": "string"}},
                 "limit": {"type": "integer"}, "labelFilter": {"type": "string"}}}},
            {"name": "hub_get_logs", "description": "Read fictional past logs",
             "inputSchema": {"type": "object", "properties": {
                 "mode": {"type": "string"}, "level": {"type": "string"},
                 "since": {"type": "string"}}}},
            {"name": "hub_call_device_command", "description": "UNAUTHORIZED WRITER",
             "inputSchema": {"type": "object", "properties": {}}},
        ]

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_call_device_command":
            raise AssertionError("Native write must not be invoked")
        key = (name, json.dumps(args, sort_keys=True))
        if key not in self.payloads:
            raise AssertionError("Unexpected native read or tool retry")
        return json.loads(wrapped(self.payloads[key]))


class ProjectionAgentTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, question, calls, answer, expected_status):
        payloads = {
            (tool, json.dumps(args, sort_keys=True)): body
            for tool, args, body in calls
        }
        hub = FakeProjectionHub(payloads)
        agent = ScriptedAgent(
            *[tool_call(tool, args) for tool, args, _ in calls],
            {"content": answer},
        )
        try:
            result = await agent.answer(
                question, [], hub, 70,
                enable_source_review=False,
                enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["bounded_source_projection"]["status"],
                         expected_status)
        self.assertEqual(result["rounds"], len(calls) + 1)
        self.assertEqual(len(hub.calls), len(calls))
        self.assertTrue(all(name != "hub_call_device_command"
                            for name, _ in hub.calls))
        self.assertFalse(result["action_lifecycle"]["native_write_submitted"])
        return result

    async def test_replaces_wrong_battery_model_count_from_native_page(self):
        result = await self.run_case(
            COUNT_QUESTION,
            [("hub_list_devices", COUNT_ARGS, COUNT_PAGE)],
            "There are 1 devices with battery in this range.",
            "bounded_numeric_inventory_count",
        )
        self.assertIn("2 distinct devices", result["answer"])
        self.assertNotIn("There are 1 devices", result["answer"])

    async def test_empty_current_state_model_reply_keeps_stored_facts(self):
        args = {"labelFilter": "Fixture One", "format": "summary"}
        result = await self.run_case(
            "Compare currently stored switch and level for Fixture One.",
            [("hub_list_devices", args, {
                "devices": [{"id": "DEV-01", "label": "Fixture One",
                             "currentStates": {"switch": "on", "level": "30"}}],
                "count": 1, "total": 1,
            })],
            "",
            "focused_stored_snapshot",
        )
        self.assertIn("level = 30", result["answer"])
        self.assertEqual(result["answer_fallback_status"],
                         "empty_model_current_inventory_partial")


if __name__ == "__main__":
    unittest.main()

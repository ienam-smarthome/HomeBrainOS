"""General historical-state intent routing, synthetic-only MCP/model receipts.

No live hub/cloud calls. Test eligibility and existing optional review/audit,
not physical continuity proof or independent model accuracy.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from investigation_review import (
    is_historical_continuity_question,
    is_historical_measurement_question,
    review_kind,
    should_review_completion,
)


class HistoricalContinuityIntentTests(unittest.TestCase):
    def test_distinct_readonly_continuity_phrasings_across_domains(self):
        questions = [
            "Did the fictional valve remain ON throughout the last four hours?",
            "Was a sensor active continuously during the past 6 hours?",
            "Has the fictional thermostat stayed heating for two hours?",
            "Were the corridor lights ON all night?",  # time idiom
            "Did a fictional plug ever switch OFF in the previous three hours?",
            "Has a motor been running since 08:20?",
            "Were there any disconnections during the last 90 minutes?",
            "Did a source have any interruptions during the past four hours?",
            "Check whether a fictional appliance remained connected throughout yesterday.",
        ]
        for question in questions:
            with self.subTest(question=question):
                self.assertTrue(is_historical_continuity_question(question), question)
                self.assertTrue(is_historical_measurement_question(question), question)
                self.assertEqual(review_kind(question), "historical_measurement")

    def test_no_automatic_review_of_writes_smalltalk_or_simple_current_state(self):
        negatives = [
            "Turn the fictional light ON for four hours.",
            "Keep the fictional socket ON for four hours.",
            "Disable the sensor in the last four hours.",
            "Was the football match on for four hours?",
            "Did you watch a movie for four hours?",
            "What is the fictional thermostat's current state?",
            "Show the current power draw for a fictional appliance.",
            "Is the fictional plug ON right now?",
            "Did the temperature rise at 10:30?",  # not an interval-continuity question
            "How do I configure an automation for four hours?",
        ]
        for question in negatives:
            with self.subTest(question=question):
                self.assertFalse(is_historical_continuity_question(question), question)
        self.assertIsNone(review_kind("What is the fictional thermostat's current state?"))
        self.assertIsNone(review_kind("Is the fictional plug ON right now?"))
        self.assertEqual(review_kind("Why did the fictional pump stop last night?"), "causal")

    def test_existing_optional_review_guards_remain_active(self):
        question = "Did a fictional valve remain on throughout the last four hours?"
        self.assertTrue(should_review_completion(
            question, available_tools=True, already_reviewed=False,
            remaining_seconds=60, has_tool_receipts=True,
        ))
        self.assertFalse(should_review_completion(
            question, available_tools=False, already_reviewed=False,
            remaining_seconds=60, has_tool_receipts=True,
        ))
        self.assertFalse(should_review_completion(
            question, available_tools=True, already_reviewed=False,
            remaining_seconds=5, has_tool_receipts=True,
        ))
        self.assertFalse(should_review_completion(
            question, available_tools=True, already_reviewed=True,
            remaining_seconds=60, has_tool_receipts=True,
        ))


class HistoricalContinuityIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_source_and_final_audit_use_existing_rounds_with_no_forced_read(self):
        class FakeMCP:
            def __init__(self):
                self.calls = []
            async def list_tools(self, refresh=False):
                return [
                    {"name": "hub_list_devices", "description": "Synthetic inventory",
                     "inputSchema": {"type": "object", "properties": {
                         "labelFilter": {"type": "string"}}}},
                    {"name": "hub_list_device_events", "description": "Synthetic events",
                     "inputSchema": {"type": "object", "properties": {
                         "deviceId": {"type": "integer"},
                         "attribute": {"type": "string"},
                         "hoursBack": {"type": "integer"},
                         "limit": {"type": "integer"}}}},
                ]
            async def call(self, name, args):
                self.calls.append((name, args))
                if name == "hub_list_devices":
                    payload = {"devices": [{
                        "id": "101", "label": "Fictional Appliance",
                        "currentStates": {"switch": "on", "power": "0"},
                        "lastActivity": "2030-01-01T12:15:00+0000",
                    }], "count": 1, "total": 1}
                elif name == "hub_list_device_events":
                    payload = {
                        "events": [], "count": 0, "attributeFilter": "switch",
                        "sinceTimestamp": "2030-01-01T08:15:00+0000",
                        "hoursBack": 4,
                    }
                else:
                    raise AssertionError("Unadvertised MCP call")
                return {"content": [{"type": "text", "text": json.dumps(payload)}]}

        class Scripted(Agent):
            def __init__(self):
                super().__init__("http://127.0.0.1:11434", "synthetic", "", 20)
                self.seen = []
                self.tools_offered = []
            async def round(self, messages, tools, remaining):
                self.seen.append([dict(m) for m in messages])
                self.tools_offered.append(
                    [t["function"]["name"] for t in tools])
                stage = len(self.seen)
                if stage == 1:
                    return {"tool_calls": [{"function": {
                        "name": "hub_list_devices",
                        "arguments": {"labelFilter": "Fictional Appliance"}
                    }}]}
                if stage == 2:
                    return {"tool_calls": [{"function": {
                        "name": "hub_list_device_events",
                        "arguments": {"deviceId": 101, "attribute": "switch",
                                      "hoursBack": 4, "limit": 100}
                    }}]}
                if stage == 3:
                    return {"content": "The device stayed ON; no switch event occurred."}
                if stage == 4:
                    return {"content": "No switch events were recorded anywhere."}
                if stage == 5:
                    self.assert_empty = (self.tools_offered[-1] == [])
                    return {"content": (
                        "The most recent snapshot reports ON. The requested "
                        "switch-filtered history returned zero matching events. "
                        "Because the native source does not certify completeness, "
                        "an uninterrupted ON state throughout the interval is unverified."
                    )}
                raise AssertionError("Unexpected additional model round")

        model, mcp = Scripted(), FakeMCP()
        try:
            result = await model.answer(
                "Did the fictional appliance remain switched ON throughout "
                "the last four hours? Do not change anything.",
                [], mcp, 90, enable_causal_follow_through=False,
            )
        finally:
            await model.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"], 5)
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(result["source_review_kind"], "historical_measurement")
        self.assertTrue(result["final_claim_audit_invoked"])
        self.assertEqual(result["final_claim_audit_status"], "completed")
        self.assertTrue(model.assert_empty)
        self.assertEqual(len(mcp.calls), 2)
        self.assertEqual([x[0] for x in mcp.calls],
                         ["hub_list_devices", "hub_list_device_events"])
        self.assertEqual(len(result["tool_calls"]), 2)
        self.assertTrue(all(x["success"] for x in result["tool_calls"]))
        self.assertIn("unverified", result["answer"])
        self.assertIn("Requested-measurement fidelity checkpoint",
                      model.seen[3][-1]["content"])
        self.assertIn('"uninterrupted_state_supported_by_this_source":false',
                      model.seen[4][-1]["content"])
        self.assertEqual(result["read_source_usage"]["native_device_event_reads"], 1)
        self.assertFalse(result["read_source_usage"]["hub_device_monitor_history_used"])


if __name__ == "__main__":
    unittest.main()

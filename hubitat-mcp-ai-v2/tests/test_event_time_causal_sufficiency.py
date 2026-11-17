"""Alpha.139 fictional event-time causal sufficiency regressions.

Only native original READ receipts establish source categories. These tests
do not call live devices or assert that source categories prove causation.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from causal_claim_publication import (
    causal_event_time_source_scope, causal_publication_floor,
)


def wrapper(native):
    return json.dumps({"content": [{"type": "text", "text": json.dumps(native)}]})


def receipt(name, args, native, success=True):
    return {"name": name, "arguments": args, "response": wrapper(native),
            "success": success, "result_kind": "tool_result"}


ARGS = {"deviceId": "FICT-OUTPUT", "attribute": "switch", "limit": 20}
EVENTS = {"source": "device", "device": "Fictional output",
          "deviceId": "FICT-OUTPUT", "attributeFilter": "switch", "events": [
              {"name": "switch", "value": "off", "type": "event",
               "date": "2030-11-16T20:10:02+0000",
               "producedBy": {"deviceId": "FICT-BRIDGE", "name": "Bridge"},
               "triggered": [{"appId": 201}]},
              {"name": "switch", "value": "on", "type": "event",
               "date": "2030-11-16T20:00:02+0000",
               "producedBy": {"deviceId": "FICT-BRIDGE", "name": "Bridge"}},
          ]}
CONFIG = {"success": True, "app": {"id": 201, "name": "Fictional Controller"},
          "page": {"name": "control", "inputs": [
              {"name": "outputDevice", "value": "FICT-OUTPUT"},
              {"name": "sourceDevice", "value": "FICT-SENSOR"}]}}
CURRENT = {"devices": [{"id": "FICT-OUTPUT",
                        "currentStates": {"temperature": "18.2"}}]}
STATE_ONLY = [
    receipt("hub_list_devices", {"format": "summary"}, CURRENT),
    receipt("hub_get_app_config", {"appId": "201"}, CONFIG),
    receipt("hub_list_device_events", ARGS, EVENTS),
]


class SourceCategoryTests(unittest.TestCase):
    def test_current_config_and_later_snapshot_not_controller_decision(self):
        x = causal_event_time_source_scope(STATE_ONLY)
        self.assertEqual(x["current_device_inventory_reads"], 1)
        self.assertEqual(x["current_installed_app_configuration_reads"], 1)
        self.assertEqual(x["original_device_history_reads"], 1)
        self.assertEqual(x["original_state_rows"], 2)
        self.assertEqual(x["original_command_rows"], 0)
        self.assertEqual(x["successful_app_scoped_past_log_reads"], 0)
        self.assertFalse(x["related_execution_source_category_present"])
        self.assertTrue(x["current_configuration_or_snapshot_not_historical_decision"])
        self.assertTrue(x["controller_or_master_output_not_necessarily_input_that_triggered_it"])
        self.assertNotIn("FICT", json.dumps(x))

    def test_command_issuer_is_distinct_from_input_decision(self):
        native = json.loads(json.dumps(EVENTS))
        native["events"].append({
            "name": "command-off", "type": "command",
            "date": "2030-11-16T20:10:01+0000",
            "producedBy": {"appId": 201, "name": "Fictional controller"},
        })
        z = causal_event_time_source_scope([
            receipt("hub_list_device_events", ARGS, native)])
        self.assertEqual(z["command_rows_with_app_issuer"], 1)
        self.assertEqual(z["original_command_rows"], 1)
        self.assertFalse(z["related_execution_source_category_present"])

    def test_unrelated_log_and_notified_listener_are_not_initiators(self):
        bad_log = receipt("hub_get_logs", {"appId": "201", "mode": "past"},
                          {"mode": "past", "entries": [{"type": "app",
                            "message": "app|201|Observer|A line"}]})
        result = causal_event_time_source_scope(STATE_ONLY + [bad_log])
        self.assertEqual(result["successful_app_scoped_past_log_reads"], 1)
        self.assertFalse(result["related_execution_source_category_present"])

    def test_false_current_value_historical_trigger_phrases_rejected(self):
        examples = [
            "This satisfies the controller threshold, so the motor started.",
            "The current value satisfies the start condition, causing "
            "the device to switch on.",
            "The current state explains why the demand was evaluated "
            "as true at that historical time.",
            "The device switched off because the timer threshold fired.",
            "The output was triggered by the selected sensor.",
            "The relay started because the controller scheduled it.",
        ]
        for answer in examples:
            with self.subTest(answer=answer):
                self.assertEqual(
                    causal_publication_floor(
                        "Why did the fixture output start?", answer, STATE_ONLY
                    )["reason"], "controller_decision_unverified",
                )

    def test_scoped_observations_and_uncertainty_remain_publishable(self):
        samples = [
            "At 20:10:02 the output reported off.",
            "App 201 is currently configured with an output device.",
            "The returned events list the bridge as reporter and app 201 "
            "as a notified listener, not a command issuer.",
            "The historic demanding input remains unverified.",
            "A hypothetical input might have caused activation, but that "
            "is not established by the read-only histories.",
            "The original output history did not return command rows "
            "in this filtered query.",
        ]
        for answer in samples:
            with self.subTest(answer=answer):
                self.assertEqual(causal_publication_floor(
                    "Why did fixture output turn on?", answer, STATE_ONLY
                )["status"], "passed")

    def test_unrelated_or_failed_logs_do_not_satisfy_floor(self):
        log = receipt("hub_get_logs", {"appId": "201", "mode": "past"},
                      {"mode": "past", "entries": [{"type": "app",
                        "time": "2030-11-16T20:10:01+00:00",
                        "message": "app|201|Controller|Fired"}]})
        for extra in (log, {**log, "success": False}):
            with self.subTest(extra=extra):
                self.assertEqual(
                    causal_publication_floor(
                        "Why did fixture output turn on?",
                        "This satisfies a trigger threshold, causing the "
                        "output to switch off.", STATE_ONLY + [extra]
                    )["reason"], "controller_decision_unverified")


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_list_device_events", "inputSchema": {
                "type": "object", "properties": {"deviceId": {"type": "string"},
                                                  "attribute": {"type": "string"},
                                                  "limit": {"type": "integer"}}}},
            {"name": "hub_get_app_config", "inputSchema": {
                "type": "object", "properties": {"appId": {"type": "string"}}}},
        ]

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_list_device_events":
            return json.loads(wrapper(EVENTS))
        if name == "hub_get_app_config":
            return json.loads(wrapper(CONFIG))
        raise AssertionError("Unexpected read/write")


def call(name, args):
    return {"content": "", "tool_calls": [
        {"function": {"name": name, "arguments": args}}]}


class ScriptedAgent(Agent):
    def __init__(self, *answers):
        super().__init__("http://127.0.0.1:11434", "fixture", "", 20)
        self.answers = list(answers)
        self.seen = []
        self.offered = []

    async def round(self, messages, tools, remaining):
        self.seen.append(json.loads(json.dumps(messages)))
        self.offered.append([t["function"]["name"] for t in tools])
        if not self.answers:
            raise AssertionError("Unexpected extra model round")
        return self.answers.pop(0)


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_final_publication_blocks_false_event_time_decision(self):
        model = ScriptedAgent(
            call("hub_list_device_events", ARGS),
            {"content": "The controller requested output off."},
            {"content": "This satisfies a historical trigger condition, "
                        "causing the output to switch off."},
        )
        hub = FakeMCP()
        try:
            answer = await model.answer(
                "Why did the fictional output switch off? Do not change anything.",
                [], hub, 90, enable_final_claim_audit=False,
                enable_causal_follow_through=False,
            )
        finally:
            await model.close()
        self.assertEqual(answer["causal_claim_verification"]["reason"],
                         "controller_decision_unverified")
        self.assertEqual(answer["answer_fallback_status"],
                         "causal_claim_publication_floor")
        self.assertNotIn("satisfies a historical trigger", answer["answer"])
        self.assertIn("Fictional output", answer["answer"])
        self.assertEqual(len(hub.calls), 1)
        self.assertFalse(answer["action_lifecycle"]["native_write_submitted"])
        self.assertIn("Original event-time causal SOURCE-CATEGORY gaps",
                      model.seen[2][-1]["content"])

    async def test_model_can_publish_bounded_result_without_extra_tool(self):
        model = ScriptedAgent(
            call("hub_list_device_events", ARGS),
            {"content": "The output reported off. Trigger unknown."},
            {"content": "The output reported off at 20:10:02. "
                        "The initiating input remains unverified."},
        )
        hub = FakeMCP()
        try:
            answer = await model.answer(
                "Why did the fictional output switch off? Do not change anything.",
                [], hub, 90, enable_final_claim_audit=False,
                enable_causal_follow_through=False,
            )
        finally:
            await model.close()
        self.assertEqual(answer["causal_claim_verification"]["status"], "passed")
        self.assertEqual(answer["answer_fallback_status"], "not_used")
        self.assertEqual(len(hub.calls), 1)
        self.assertIn("initiating input remains unverified", answer["answer"])
        self.assertFalse(answer["action_lifecycle"]["native_write_submitted"])


if __name__ == "__main__":
    unittest.main()

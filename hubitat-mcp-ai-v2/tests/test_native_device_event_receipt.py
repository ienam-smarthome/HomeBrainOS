"""Fictional regression for upstream device-history envelope compatibility.

The deployed native gateway can omit source and deviceId from the response
body; the successful original tool arguments carry the requested identity.
No live hub, personal data, scheduler IDs or physical devices are used here.
"""
from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from causal_claim_publication import causal_publication_floor
from native_device_event_receipt import original_device_event_history
from read_only_receipt_fallback import source_only_partial_answer


def wrapped(native):
    return json.dumps({"content": [{"type": "text", "text": json.dumps(native)}]})


EVENTS = {
    "device": "Fixture Relay",
    "events": [
        {"name": "thermostatOperatingState", "value": "heating",
         "date": "2030-01-05T10:30:20.000+0000",
         "producedBy": {"name": "Fixture Relay", "deviceId": "9001"}},
        {"name": "command-setHeatingSetpoint", "type": "command",
         "date": "2030-01-05T10:30:02.000+0000",
         "producedBy": {"name": "Fixture Demand App", "appId": 456}},
        {"name": "heatingSetpoint", "value": "22.0",
         "date": "2030-01-05T10:30:01.000+0000",
         "producedBy": {"name": "Fixture Demand App", "appId": 456}},
        {"name": "thermostatOperatingState", "value": "idle",
         "date": "2030-01-05T10:15:00.000+0000"},
    ],
    "count": 4,
}
LOGS = {"mode": "past", "entries": [
    {"time": "2030-01-05 10:30:02.100", "type": "app",
     "message": "Fixture Demand App: living-zone demand confirmed; requested 22C"}
]}
EVENT_ARGS = {"deviceId": 9001, "limit": 20}
LOG_ARGS = {"mode": "past", "appId": "456", "limit": 20}


def receipt(name, args, payload, *, success=True):
    return {
        "name": name, "arguments": args, "success": success,
        "response": wrapped(payload), "result_kind": "tool_result",
    }


def select(name, args):
    return {"content": "", "tool_calls": [{
        "function": {"name": name, "arguments": args},
    }]}


class EnvelopeContractTests(unittest.TestCase):
    def test_legacy_shape_retains_observed_states_and_matching_log(self):
        event = receipt("hub_list_device_events", EVENT_ARGS, EVENTS)
        log = receipt("hub_get_logs", LOG_ARGS, LOGS)
        unchanged = json.dumps([event, log], sort_keys=True)
        self.assertIsNotNone(original_device_event_history(event))
        partial = source_only_partial_answer(
            "Why did Fixture Relay start?", [event, log],
            timezone_name="Europe/London",
        )
        self.assertIn("Fixture Relay", partial)
        self.assertIn("heating at", partial)
        self.assertIn("10:30:20 am GMT", partial)
        self.assertIn("initiating command", partial)
        self.assertEqual(
            causal_publication_floor(
                "Why did the output turn on?",
                "The output turned on because the fixture controller confirmed demand.",
                [event, log],
            )["status"], "passed",
        )
        self.assertEqual(unchanged, json.dumps([event, log], sort_keys=True))

    def test_mismatched_ids_non_device_sources_and_missing_identity_fail_closed(self):
        base = receipt("hub_list_device_events", EVENT_ARGS, EVENTS)
        for bad in (
            dict(EVENTS, deviceId="9002"),
            dict(EVENTS, source="location"),
            {"events": deepcopy(EVENTS["events"]), "count": 4},
        ):
            row = deepcopy(base)
            row["response"] = wrapped(bad)
            self.assertIsNone(original_device_event_history(row))
            self.assertIsNone(source_only_partial_answer("Why?", [row]))
            self.assertEqual(causal_publication_floor(
                "Why did it start?",
                "The device started because the controller ran.",
                [row, receipt("hub_get_logs", LOG_ARGS, LOGS)],
            )["reason"], "controller_decision_unverified")
        no_requested_id = receipt("hub_list_device_events",
                                  {"appId": "456"}, EVENTS)
        self.assertIsNone(original_device_event_history(no_requested_id))

    def test_unrelated_or_empty_app_log_remains_insufficient(self):
        event = receipt("hub_list_device_events", EVENT_ARGS, EVENTS)
        for appid, logs in (("999", LOGS), ("456", {"mode": "past", "entries": []})):
            result = causal_publication_floor(
                "Why did output turn on?",
                "The output turned on because the fixture controller acted.",
                [event, receipt("hub_get_logs",
                                {"mode": "past", "appId": appid}, logs)],
            )
            self.assertEqual(result["reason"], "controller_decision_unverified")


class ScriptedMCP:
    def __init__(self):
        self.called = []

    async def list_tools(self, refresh=False):
        return [{"name": n, "description": "Fixture read only",
                 "inputSchema": {"type": "object", "properties": {}}}
                for n in ("hub_list_device_events", "hub_get_logs")]

    async def call(self, name, args):
        self.called.append((name, args))
        if name == "hub_list_device_events" and args == EVENT_ARGS:
            return json.loads(wrapped(EVENTS))
        if name == "hub_get_logs" and args == LOG_ARGS:
            return json.loads(wrapped(LOGS))
        raise AssertionError("Unsupported or mutating call")


class ScriptedAgent(Agent):
    def __init__(self, *messages):
        super().__init__("http://127.0.0.1:11434", "fixture", "", 20)
        self.messages = list(messages)

    async def round(self, *args, **kwargs):
        if not self.messages:
            raise AssertionError("Unexpected additional round")
        return self.messages.pop(0)


class EndToEndTests(unittest.IsolatedAsyncioTestCase):
    async def test_matching_legacy_device_history_and_app_log_preserve_normal_answer(self):
        mcp = ScriptedMCP()
        agent = ScriptedAgent(
            select("hub_list_device_events", EVENT_ARGS),
            select("hub_get_logs", LOG_ARGS),
            {"content": (
                "The output started after the Fixture Demand App confirmed a "
                "living-zone demand. Its recorded setpoint report and later "
                "heating-state report support this bounded sequence; the "
                "independent physical outcome is not verified."
            )},
        )
        try:
            result = await agent.answer(
                "Why did the fixture relay turn on? Do not change anything.",
                [], mcp, 90, enable_source_review=False,
                enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["answer_fallback_status"], "not_used")
        self.assertEqual(result["causal_claim_verification"]["status"], "passed")
        self.assertIn("living-zone demand", result["answer"])
        self.assertEqual(len(mcp.called), 2)
        self.assertEqual(result["rounds"], 3)

    async def test_legacy_history_safely_survives_unsupported_causal_draft(self):
        mcp = ScriptedMCP()
        agent = ScriptedAgent(
            select("hub_list_device_events", EVENT_ARGS),
            {"content": "The output turned on because a scheduled timer fired."},
        )
        try:
            result = await agent.answer(
                "Why did the fixture relay start? Do not change anything.",
                [], mcp, 90, enable_source_review=False,
                enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        self.assertEqual(
            result["answer_fallback_status"], "causal_claim_publication_floor"
        )
        self.assertIn("10:30:20 am GMT", result["answer"])
        self.assertNotIn("no verified event history", result["answer"].lower())
        self.assertNotIn("scheduled timer fired", result["answer"])
        self.assertEqual(len(mcp.called), 1)


if __name__ == "__main__":
    unittest.main()

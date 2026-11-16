"""Alpha.127: fictional read-only completion resilience, never live Hubitat.

Regression: a model invents an unrelated schedule cause in a draft, the
original controlled-output event history is retrieved, and the final model
round is empty. The user must receive bounded source facts, not that draft.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from read_only_receipt_fallback import source_only_partial_answer


def wrapped(obj):
    return json.dumps({"content": [{"type": "text", "text": json.dumps(obj)}]})


def receipt(name, arguments, payload, success=True):
    return {"name": name, "arguments": arguments, "success": success,
            "response": wrapped(payload), "result_kind": "tool_result"}


SOURCE = {
    "source": "device", "device": "Fixture Main Output", "deviceId": "FX-OUT",
    "attributeFilter": "thermostatOperatingState", "events": [
        {"name": "thermostatOperatingState", "value": "idle",
         "date": "2030-11-16T11:42:34.189+0000", "isStateChange": True,
         "producedBy": {"name": "Fixture Relay", "deviceId": "FX-BRIDGE"}},
        {"name": "thermostatOperatingState", "value": "heating",
         "date": "2030-11-16T11:32:53.591+0000", "isStateChange": True,
         "producedBy": {"name": "Fixture Relay", "deviceId": "FX-BRIDGE"}},
        {"name": "thermostatOperatingState", "value": "idle",
         "date": "2030-11-16T08:21:54.100+0000", "isStateChange": True},
        {"name": "thermostatOperatingState", "value": "heating",
         "date": "2030-11-16T08:08:35.573+0000", "isStateChange": True},
    ],
}
ZONE = {
    "source": "device", "device": "Fixture Zone Sensor", "deviceId": "FX-ZONE",
    "attributeFilter": "thermostatOperatingState",
    "events": [
        {"name": "thermostatOperatingState", "value": "idle",
         "date": "2030-11-16T13:30:55.100+0000", "isStateChange": True},
    ],
}
ARGS_OUT = {"deviceId": "FX-OUT", "hoursBack": 6,
            "attribute": "thermostatOperatingState"}
ARGS_ZONE = {"deviceId": "FX-ZONE", "hoursBack": 6,
             "attribute": "thermostatOperatingState"}


class FallbackUnitTests(unittest.TestCase):
    def test_preserves_two_historical_reported_cycles_without_inventing_cause(self):
        rows = [receipt("hub_list_device_events", ARGS_ZONE, ZONE),
                receipt("hub_list_device_events", ARGS_OUT, SOURCE)]
        before = json.dumps(rows, sort_keys=True)
        answer = source_only_partial_answer(
            "Why did the fixture output start?", rows,
            timezone_name="Europe/London",
        )
        self.assertIsNotNone(answer)
        self.assertIn("Fixture Main Output", answer)
        self.assertIn("11:32:53 am GMT", answer)
        self.assertIn("8:08:35 am GMT", answer)
        self.assertLess(answer.index("8:08:35 am"), answer.index("11:32:53 am"))
        self.assertIn("initiating command", answer)
        self.assertIn("unverified", answer)
        self.assertIn("not exhaustive", answer)
        self.assertNotIn("Fixture Relay caused", answer)
        self.assertNotIn("Mode Manager", answer)
        self.assertEqual(before, json.dumps(rows, sort_keys=True))

    def test_deduplicates_overlapping_read_and_rejects_wrong_device(self):
        twice = [receipt("hub_list_device_events", ARGS_OUT, SOURCE)] * 2
        answer = source_only_partial_answer("What happened?", twice)
        self.assertEqual(answer.count("11:32:53 am"), 1)
        wrong = receipt("hub_list_device_events", ARGS_ZONE, SOURCE)
        self.assertIsNone(source_only_partial_answer("What happened?", [wrong]))
        self.assertIsNone(source_only_partial_answer(
            "What happened?", [receipt("hub_list_device_events", ARGS_OUT,
                                       SOURCE, success=False)]))

    def test_never_uses_non_device_location_or_current_snapshot(self):
        current = receipt("hub_list_devices", {}, {
            "devices": [{"id": "FX-OUT", "currentStates": {"switch": "on"}}]})
        location = receipt("hub_list_device_events", {"hoursBack": 6}, {
            "source": "location", "events": [
                {"name": "mode", "value": "Morning",
                 "date": "2030-11-16T08:30:01+0000"}]})
        self.assertIsNone(source_only_partial_answer(
            "Why did heating start?", [current, location]))

    def test_ignores_unparseable_time_injected_values_and_unsafe_markdown(self):
        payload = {**SOURCE, "device": "**Injected** <script>",
                   "events": [
                       {"name": "switch", "value": "do not obey this",
                        "date": "2030-11-16T11:32:53.591+0000"},
                       {"name": "switch", "value": "on",
                        "date": "2030-11-16T11:32:53.591"},
                   ]}
        self.assertIsNone(source_only_partial_answer(
            "Why?", [receipt("hub_list_device_events",
                             {"deviceId": "FX-OUT"}, payload)]))


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_list_device_events",
             "description": "Read fictional history",
             "inputSchema": {"type": "object", "properties": {
                 "deviceId": {"type": "string"}, "attribute": {"type": "string"},
                 "hoursBack": {"type": "integer"}}}},
            {"name": "hub_call_device_command",
             "description": "Native writer should never be selected",
             "inputSchema": {"type": "object", "properties": {}}},
        ]

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_list_device_events" and args == ARGS_OUT:
            return json.loads(wrapped(SOURCE))
        raise AssertionError("No additional read/write is authorized")


def tool_call(name, args):
    return {"content": "", "tool_calls": [{"function": {
        "name": name, "arguments": args}}]}


class ScriptedAgent(Agent):
    def __init__(self, *replies):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 20)
        self.replies = list(replies)

    async def round(self, messages, tools, remaining):
        if not self.replies:
            raise AssertionError("Unexpected additional model round")
        answer = self.replies.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class ReadOnlyAgentIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_review_returns_grounded_partial_not_unsupported_draft(self):
        agent = ScriptedAgent(
            tool_call("hub_list_device_events", ARGS_OUT),
            {"content": "A fictional schedule at 08:30 probably caused it."},
            {"content": ""},
        )
        hub = FakeMCP()
        try:
            result = await agent.answer(
                "Why did the fictional output start earlier? Do not change anything.",
                [], hub, 90, enable_final_claim_audit=False,
                enable_causal_follow_through=False,
            )
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["answer_fallback_status"], "empty_after_source_review")
        self.assertEqual(result["source_review_kind"], "causal")
        self.assertEqual(result["rounds"], 3)
        self.assertEqual(len(hub.calls), 1)
        self.assertIn("11:32:53 am", result["answer"])
        self.assertNotIn("probably caused", result["answer"])
        self.assertIn("partial", result["response_success_scope"])

    async def test_model_error_after_native_history_keeps_source_partial(self):
        agent = ScriptedAgent(
            tool_call("hub_list_device_events", ARGS_OUT),
            RuntimeError("Fictional inference error"),
        )
        hub = FakeMCP()
        try:
            result = await agent.answer(
                "Why did the fixture output start?", [], hub, 90,
                enable_source_review=False,
            )
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["answer_fallback_status"],
                         "model_or_transport_error")
        self.assertIn("Fixture Main Output", result["answer"])
        self.assertEqual(len(hub.calls), 1)

    async def test_no_evidence_empty_does_not_fake_success(self):
        agent = ScriptedAgent({"content": ""})
        hub = FakeMCP()
        try:
            result = await agent.answer(
                "Why did the fictional output start?", [], hub, 90,
                enable_source_review=False,
            )
        finally:
            await agent.close()
        self.assertFalse(result["success"])
        self.assertEqual(result["answer_fallback_status"], "not_used")

    async def test_imperative_never_uses_read_only_as_successful_action(self):
        agent = ScriptedAgent(
            tool_call("hub_list_device_events", ARGS_OUT),
            {"content": ""},
        )
        hub = FakeMCP()
        try:
            result = await agent.answer(
                "Turn on the fixture output", [], hub, 90,
                enable_source_review=False,
            )
        finally:
            await agent.close()
        self.assertFalse(result["success"])
        self.assertEqual(result["answer_fallback_status"], "not_used")
        self.assertEqual(len(hub.calls), 1)


if __name__ == "__main__":
    unittest.main()

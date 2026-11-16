"""Alpha.128 fictional tests: final causal claims and model inventory context.

No live devices, app IDs, schedules or private household evidence.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from causal_claim_publication import causal_publication_floor
from model_inventory_context import compact_inventory_context


def wrapper(native):
    return json.dumps({"content": [{"type": "text", "text": json.dumps(native)}]})


ARGS = {"deviceId": "fictional-output", "attribute": "switch", "hoursBack": 4}
EVENTS = {"source": "device", "device": "Fixture Output",
          "deviceId": "fictional-output", "attributeFilter": "switch", "events": [
              {"name": "switch", "value": "off", "isStateChange": True,
               "date": "2030-09-03T08:20:00+01:00"},
              {"name": "switch", "value": "on", "isStateChange": True,
               "date": "2030-09-03T08:10:00+01:00"},
          ]}


def history_receipt():
    return {"name": "hub_list_device_events", "arguments": dict(ARGS),
            "success": True, "result_kind": "tool_result",
            "response": wrapper(EVENTS)}


class ClaimFloorUnitTests(unittest.TestCase):
    def test_denial_without_complete_source_is_unsafe(self):
        r = causal_publication_floor(
            "Why did fixture output turn on?",
            "The fixture output did not turn on earlier today.",
            [history_receipt()])
        self.assertEqual(r["reason"], "unbounded_historical_absence")

    def test_definite_trigger_without_execution_logs_is_unsafe(self):
        r = causal_publication_floor(
            "Why did fixture output turn on?",
            "The output turned on because the fictional controller raised its setpoint.",
            [history_receipt()])
        self.assertEqual(r["reason"], "controller_decision_unverified")

    def test_scoped_source_limit_and_cautious_hypothesis_unchanged(self):
        for answer in (
            "No matching rows were returned in this query.",
            "The controller might have triggered the change, but that is unverified.",
            "The original returned rows show on at 08:10; the cause is unknown.",
            "We cannot prove the output did not turn on.",
            "The events show that the device reported on at 08:10.",
        ):
            with self.subTest(answer=answer):
                self.assertEqual(
                    causal_publication_floor("Why did output turn on?", answer,
                                             [history_receipt()])["status"],
                    "passed",
                )

    def test_app_id_filter_in_device_events_does_not_become_app_log(self):
        filtered = {"name": "hub_list_device_events",
                    "arguments": {"appId": "mock"},
                    "success": True, "result_kind": "tool_result",
                    "response": wrapper({"source": "location", "events": []})}
        r = causal_publication_floor(
            "Why did fixture change?",
            "The fixture changed because the controller commanded it.",
            [filtered])
        self.assertEqual(r["reason"], "controller_decision_unverified")

    def test_successful_nonempty_event_execution_log_is_different_source_type(self):
        execution = {"name": "hub_list_app_logs", "arguments": {"appId": "mock"},
                     "success": True, "result_kind": "tool_result",
                     "response": wrapper({"logs": [
                         {"time": "2030-09-03T08:10:00+01:00",
                          "message": "A fictional trigger executed"}
                     ]})}
        self.assertEqual(
            causal_publication_floor(
                "Why did output turn on?",
                "The output turned on because the controller executed the branch.",
                [history_receipt(), execution])["status"],
            "passed",
        )


class InventoryContextTests(unittest.TestCase):
    def test_all_ids_labels_rooms_retained_and_full_receipt_untouched(self):
        native = {"devices": [
            {"id": str(i), "label": f"Fixture {i}", "room": "Test Room",
             "deviceNetworkId": "sensitive-opaque",
             "currentStates": {"switch": "on", "temperature": "21.0"}}
            for i in range(50)
        ], "count": 50, "total": 50}
        original = {"content": [{"type": "text", "text": json.dumps(native)}]}
        before = json.dumps(original, sort_keys=True)
        compact = compact_inventory_context(original)
        self.assertEqual(len(compact["client_inventory_navigation"]["devices"]), 50)
        self.assertEqual(
            [x["id"] for x in compact["client_inventory_navigation"]["devices"]],
            [str(i) for i in range(50)],
        )
        self.assertNotIn("sensitive-opaque", json.dumps(compact))
        self.assertEqual(before, json.dumps(original, sort_keys=True))

    def test_malformed_identity_fails_closed(self):
        native = {"devices": [
            {"id": i, "label": "Item"} for i in range(30)
        ], "count": 40}
        self.assertIsNone(compact_inventory_context(
            {"content": [{"type": "text", "text": json.dumps(native)}]}))


class FakeMCP:
    def __init__(self, inventory=None):
        self.calls = []
        self.inventory = inventory

    async def list_tools(self, refresh=False):
        return [{"name": "hub_list_device_events",
                 "description": "Fictional source",
                 "inputSchema": {"type": "object",
                                 "properties": {"deviceId": {"type": "string"}}}},
                {"name": "hub_list_devices",
                 "description": "Fictional inventory",
                 "inputSchema": {"type": "object",
                                 "properties": {"format": {"type": "string"}}}}]

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_list_device_events" and args == ARGS:
            return json.loads(wrapper(EVENTS))
        if name == "hub_list_devices" and args == {"format": "summary"}:
            return json.loads(wrapper(self.inventory))
        raise AssertionError("Only the scripted READ is permitted")


def select_tool(name, args):
    return {"content": "", "tool_calls": [
        {"function": {"name": name, "arguments": args}}]}


class ScriptedAgent(Agent):
    def __init__(self, *answers):
        super().__init__("http://127.0.0.1:11434", "fixture", "", 20)
        self.answers = list(answers)
        self.snapshots = []

    async def round(self, messages, tools, remaining):
        self.snapshots.append(json.loads(json.dumps(messages)))
        if not self.answers:
            raise AssertionError("Unexpected additional round")
        return self.answers.pop(0)


class PublicationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_definite_cause_preserves_only_original_history_as_partial(self):
        agent = ScriptedAgent(
            select_tool("hub_list_device_events", ARGS),
            {"content": "The output turned on because the fixture app was scheduled."},
        )
        hub = FakeMCP()
        try:
            result = await agent.answer(
                "Why did the fixture output turn on? Do not change anything.",
                [], hub, 90, enable_source_review=False,
                enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"], 2)
        self.assertEqual(len(hub.calls), 1)
        self.assertEqual(result["answer_fallback_status"],
                         "causal_claim_publication_floor")
        self.assertEqual(result["causal_claim_verification"]["reason"],
                         "controller_decision_unverified")
        self.assertIn("Fixture Output", result["answer"])
        self.assertIn("8:10:00", result["answer"])
        self.assertNotIn("scheduled", result["answer"])
        self.assertIn("partial", result["response_success_scope"])

    async def test_unqualified_no_event_cannot_survive_final_answer(self):
        agent = ScriptedAgent(
            select_tool("hub_list_device_events", ARGS),
            {"content": "The fixture output did not turn on earlier today."},
        )
        try:
            result = await agent.answer(
                "Why did the fixture output turn on earlier?",
                [], FakeMCP(), 90, enable_source_review=False,
                enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        self.assertEqual(result["causal_claim_verification"]["reason"],
                         "unbounded_historical_absence")
        self.assertNotIn("did not turn on", result["answer"])

    async def test_compact_model_inventory_and_preserve_private_original(self):
        inventory = {"devices": [
            {"id": str(i), "label": f"Fixture {i}", "room": "Mock",
             "deviceNetworkId": "opaque-network-identifier-" + str(i),
             "currentStates": {"switch": "off"}}
            for i in range(80)
        ], "count": 80, "total": 80}
        agent = ScriptedAgent(
            select_tool("hub_list_devices", {"format": "summary"}),
            {"content": "The source is only a current-state inventory; no historical cause is established."},
        )
        try:
            result = await agent.answer(
                "Why did a device start earlier?", [],
                FakeMCP(inventory), 90, enable_source_review=False,
                enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        rows = result["tool_calls"]
        self.assertTrue(rows[0]["model_context_compacted"])
        self.assertIn("opaque-network-identifier", rows[0]["response"])
        model_view = agent.snapshots[1][-1]["content"]
        self.assertNotIn("opaque-network-identifier", model_view)
        self.assertIn("Fixture 79", model_view)
        self.assertLess(len(model_view), len(rows[0]["response"]))
        self.assertEqual(result["answer_fallback_status"], "not_used")


if __name__ == "__main__":
    unittest.main()

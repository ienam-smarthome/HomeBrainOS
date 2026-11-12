"""Alpha.44 historical-measurement fidelity: fictional model/MCP regressions.

Tests verify the model is offered a second evidence decision, not that any
production model reliably makes that decision. No real hub or household data.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent, _SKILL
from investigation_review import (
    MEASUREMENT_REVIEW_PROMPT,
    is_historical_measurement_question,
    review_kind,
    review_prompt,
    should_review_completion,
)


def event_reply(events, *, filter_name=None):
    payload = {
        "source": "fictional-source",
        "device": "Synthetic Appliance",
        "events": events,
        "count": len(events),
        "attributeFilter": filter_name,
    }
    return {"content": [{"type": "text", "text": json.dumps(payload)}],
            "_meta": {"fixture": "original-mcp-content-must-survive"}}


_SOURCE_EMPTY = event_reply([], filter_name="power")
_SOURCE_OTHER = event_reply([
    {"name": "energy", "value": "12.50", "unit": "kWh",
     "date": "2026-10-18T06:00:00Z"},
    {"name": "amperage", "value": "0.30", "unit": "A",
     "date": "2026-10-18T02:00:00Z"},
])
_SOURCE_TARGET = event_reply([
    {"name": "power", "value": "28", "unit": "W",
     "date": "2026-10-18T01:15:00Z"},
    {"name": "power", "value": "34", "unit": "W",
     "date": "2026-10-18T01:25:00Z"},
], filter_name="power")


class FictionalHistoryHub:
    def __init__(self, archive=None):
        self.calls = []
        self.archive = archive
        self.catalog = [
            {"name": "hub_read_history",
             "inputSchema": {"type": "object", "properties": {
                 "attribute": {"type": "string"},
                 "since": {"type": "string"},
                 "until": {"type": "string"}}}},
            {"name": "hub_read_archive",
             "inputSchema": {"type": "object", "properties": {
                 "metric": {"type": "string"}}}},
            {"name": "hub_manage_device",
             "inputSchema": {"type": "object", "properties": {
                 "action": {"type": "string"}}}},
        ]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_read_archive":
            if self.archive is None:
                return {"isError": True, "content": [
                    {"type": "text", "text": "No archive available"}]}
            return self.archive
        if name != "hub_read_history":
            raise AssertionError("Unexpected MCP call")
        if args.get("attribute") == "power":
            return _SOURCE_EMPTY
        return _SOURCE_OTHER


def function_call(name, args):
    return {"function": {"name": name, "arguments": args}}


class ScriptedAgent(Agent):
    def __init__(self, scripted):
        super().__init__("http://127.0.0.1:11434", "fixture", "", 15)
        self.scripted = list(scripted)
        self.messages_seen = []
        self.tools_seen = []

    async def answer(self, *args, **kwargs):
        # These legacy roundtrip fixtures intentionally test the pre-audit
        # source-review contract; dedicated tests exercise the new default.
        kwargs.setdefault("enable_final_claim_audit", False)
        return await super().answer(*args, **kwargs)

    async def round(self, messages, tools, remaining):
        self.messages_seen.append([dict(m) for m in messages])
        self.tools_seen.append([item["function"]["name"] for item in tools])
        return self.scripted.pop(0)


class MeasurementIntentTests(unittest.TestCase):
    def test_historical_intent_is_domain_general(self):
        for question in (
            "show power usage of the Test Rig last night",
            "plot coolant temperature for the past 24 hours",
            "show water flow readings yesterday",
            "compare humidity levels last 7 days",
            "what was the pressure at 1am?",
            "chart inverter voltage from 20:00 to 08:00",
            "give battery readings on 2026-10-18",
        ):
            self.assertTrue(is_historical_measurement_question(question), question)
            self.assertEqual(review_kind(question), "historical_measurement")
        for question in (
            "show current power reading",
            "list rooms",
            "set heating to 19 degrees last night",
            "turn off heater at 8pm",
        ):
            self.assertFalse(is_historical_measurement_question(question), question)
        self.assertEqual(review_kind("Why did the inverter stop last night?"), "causal")
        self.assertEqual(review_kind("Show device status"), None)

    def test_checkpoint_requires_read_catalog_and_time(self):
        self.assertTrue(should_review_completion(
            "show water flow yesterday", available_tools=True,
            already_reviewed=False, remaining_seconds=30))
        self.assertFalse(should_review_completion(
            "show water flow yesterday", available_tools=False,
            already_reviewed=False, remaining_seconds=30))
        self.assertFalse(should_review_completion(
            "show water flow yesterday", available_tools=True,
            already_reviewed=True, remaining_seconds=30))
        self.assertFalse(should_review_completion(
            "show water flow yesterday", available_tools=True,
            already_reviewed=False, remaining_seconds=2))

    def test_general_guidance_preserves_requested_dimensions(self):
        self.assertIn("historical interval", MEASUREMENT_REVIEW_PROMPT)
        self.assertIn("cumulative energy", MEASUREMENT_REVIEW_PROMPT)
        self.assertIn("READ-ONLY", MEASUREMENT_REVIEW_PROMPT)
        self.assertIn("requested quantity", MEASUREMENT_REVIEW_PROMPT)
        self.assertIn("requested quantity", _SKILL.lower())
        self.assertIn("requested historical measurement", _SKILL.lower())
        self.assertNotIn("Bedroom 3", MEASUREMENT_REVIEW_PROMPT)
        self.assertIn("causal question", review_prompt("causal"))


class MeasurementLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_selects_archive_after_unusable_related_units(self):
        hub = FictionalHistoryHub(archive=_SOURCE_TARGET)
        agent = ScriptedAgent([
            {"content": "", "tool_calls": [
                function_call("hub_read_history", {"attribute": "power"})]},
            {"content": "", "tool_calls": [
                function_call("hub_read_history", {})]},
            {"content": "The PC was active because energy rose by 0.05 kWh.",
             "tool_calls": []},
            {"content": "", "tool_calls": [
                function_call("hub_read_archive", {"metric": "power"})]},
            {"content": ("The fictional archive returned 28 W at 01:15 and "
                         "34 W at 01:25. No full-night peak is established."),
             "tool_calls": []},
        ])
        try:
            reply = await agent.answer("show power usage of the Test Rig last night",
                                       [], hub, 90)
        finally:
            await agent.close()
        self.assertTrue(reply["success"])
        self.assertEqual(reply["source_review_kind"], "historical_measurement")
        self.assertTrue(reply["source_review_invoked"])
        self.assertEqual(reply["rounds"], 5)
        self.assertEqual([name for name, _ in hub.calls],
                         ["hub_read_history", "hub_read_history", "hub_read_archive"])
        self.assertEqual(agent.tools_seen[3],
                         ["hub_read_history", "hub_read_archive"])
        self.assertIn("28 W", reply["answer"])
        self.assertNotIn("was active", reply["answer"])
        self.assertEqual(
            json.loads(reply["tool_calls"][0]["response"])["content"],
            _SOURCE_EMPTY["content"],
        )
        self.assertEqual(
            json.loads(reply["tool_calls"][2]["response"])["content"],
            _SOURCE_TARGET["content"],
        )
        self.assertEqual(agent.messages_seen[3][-1]["role"], "user")
        self.assertIn("Requested-measurement fidelity",
                      agent.messages_seen[3][-1]["content"])

    async def test_model_can_stop_when_requested_measurement_is_missing(self):
        hub = FictionalHistoryHub()
        agent = ScriptedAgent([
            {"content": "", "tool_calls": [
                function_call("hub_read_history", {"attribute": "power"})]},
            {"content": "Energy changed, meaning very little power was used.",
             "tool_calls": []},
            {"content": ("No historical W samples were returned for the requested "
                         "period. Cumulative kWh is not a wattage profile."),
             "tool_calls": []},
        ])
        try:
            reply = await agent.answer("Show pump power usage overnight", [], hub, 90)
        finally:
            await agent.close()
        self.assertTrue(reply["source_review_invoked"])
        self.assertEqual(reply["source_review_kind"], "historical_measurement")
        self.assertEqual(reply["rounds"], 3)
        self.assertEqual(len(hub.calls), 1)
        self.assertIn("No historical W samples", reply["answer"])
        self.assertEqual(len(reply["tool_calls"]), 1)

    async def test_positive_control_preserves_real_historical_measurement(self):
        hub = FictionalHistoryHub()
        hub.call = lambda name, args: original_call(name, args, hub)
        async def original_call(name, args, hub):
            hub.calls.append((name, args))
            return _SOURCE_TARGET
        agent = ScriptedAgent([
            {"content": "", "tool_calls": [
                function_call("hub_read_history", {"attribute": "power"})]},
            {"content": "28 W then 34 W in the returned sample points.",
             "tool_calls": []},
            {"content": ("The returned samples are 28 W at 01:15 and 34 W at "
                         "01:25, without full-night peak coverage."),
             "tool_calls": []},
        ])
        try:
            reply = await agent.answer("show power trend of the test device last night",
                                       [], hub, 90)
        finally:
            await agent.close()
        self.assertEqual(reply["rounds"], 3)
        self.assertEqual(len(hub.calls), 1)
        self.assertEqual(reply["source_review_kind"], "historical_measurement")
        self.assertIn("28 W", reply["answer"])

    async def test_blinded_protocol_can_disable_review_without_extra_calls(self):
        hub = FictionalHistoryHub()
        agent = ScriptedAgent([
            {"content": "Synthetic study answer.", "tool_calls": []},
        ])
        try:
            reply = await agent.answer("show recorded voltage last night", [],
                                       hub, 90, enable_source_review=False)
        finally:
            await agent.close()
        self.assertEqual(reply["rounds"], 1)
        self.assertFalse(reply["source_review_invoked"])
        self.assertIsNone(reply["source_review_kind"])
        self.assertEqual(hub.calls, [])

    async def test_current_snapshot_request_skips_review(self):
        hub = FictionalHistoryHub()
        agent = ScriptedAgent([
            {"content": "The current sensor reports 4 W.", "tool_calls": []},
        ])
        try:
            reply = await agent.answer("Show the power right now", [], hub, 90)
        finally:
            await agent.close()
        self.assertEqual(reply["rounds"], 1)
        self.assertFalse(reply["source_review_invoked"])
        self.assertIsNone(reply["source_review_kind"])
        self.assertEqual(hub.calls, [])

    async def test_historical_review_rejects_write_tool_call(self):
        hub = FictionalHistoryHub()
        agent = ScriptedAgent([
            {"content": "No history found.", "tool_calls": []},
            {"content": "", "tool_calls": [
                function_call("hub_manage_device", {"action": "off"})]},
            {"content": "Only source evidence may be used.", "tool_calls": []},
        ])
        try:
            reply = await agent.answer("show room humidity last night", [], hub, 90)
        finally:
            await agent.close()
        self.assertTrue(reply["source_review_invoked"])
        self.assertEqual(hub.calls, [])
        self.assertFalse(reply["tool_calls"][0]["success"])
        self.assertIn("read-only", reply["tool_calls"][0]["error"])


if __name__ == "__main__":
    unittest.main()

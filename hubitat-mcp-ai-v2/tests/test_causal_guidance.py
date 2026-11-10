"""Contract tests for general causal skill delivery and unchanged model-led calls.

These tests intentionally do NOT assert that an Ollama model will obey the
guidance. Synthetic evidence is only used to check the production interface.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent, _SKILL


class CausalReasoningGuidanceTests(unittest.TestCase):
    def test_causal_reference_is_loaded_from_repository_and_is_not_incident_specific(self):
        reference = (Path(__file__).resolve().parents[1] / "rootfs" / "app" /
                     "skills" / "hubitat" / "causal-investigations.md").read_text()
        self.assertIn(reference.strip(), _SKILL)
        self.assertIn("T-D", _SKILL)
        self.assertIn("configuration at the historical event time", _SKILL)
        self.assertIn("does not explain a later short timer", _SKILL)
        self.assertIn("source timestamp and time zone", _SKILL)
        self.assertIn("only plausible cause", _SKILL)
        self.assertIn("do not trigger", _SKILL.lower() if "do not trigger" in _SKILL.lower()
                      else reference.lower() + " do not trigger")
        for incident in ("Hallway Light", "4012", "7752", "7770", "FP300", "Bedroom 1"):
            self.assertNotIn(incident, reference)

    def test_simple_answer_still_requires_no_extra_round_or_tool_call(self):
        class NoTools:
            def __init__(self):
                self.calls = []
            async def list_tools(self, refresh=False):
                return []
            async def call(self, name, args):
                self.calls.append((name, args))
                raise AssertionError("Unexpected tool request")
        class OneRound(Agent):
            def __init__(self):
                self.rounds_seen = []
            async def round(self, messages, tools, remaining):
                self.rounds_seen.append((messages, tools))
                return {"content": "The earlier measurement was 21 degrees."}

        async def scenario():
            model = OneRound()
            mcp = NoTools()
            result = await model.answer("What was the earlier reading?", [], mcp, 30)
            self.assertTrue(result["success"])
            self.assertEqual(result["rounds"], 1)
            self.assertEqual(result["tool_calls"], [])
            self.assertEqual(mcp.calls, [])
            self.assertEqual(len(model.rounds_seen), 1)
            self.assertIn("causal investigations", model.rounds_seen[0][0][0]["content"].lower())
        asyncio.run(scenario())

    def test_model_selects_sources_and_original_observations_stay_in_receipts(self):
        source_event = {
            "events": [
                {"name": "switch", "value": "off",
                 "date": "2026-11-12T09:45:30.400Z",
                 "producedBy": {"name": "Synthetic Gateway"},
                 "triggered": [{"name": "Synthetic Monitor"}]},
                {"name": "command-off", "date": "2026-11-12T09:45:30.100Z",
                 "producedBy": {"name": "Synthetic Control App"}},
            ], "count": 2,
        }
        source_config = {
            "app": {"name": "Synthetic Control App"},
            "settings": {"delaySeconds": 20,
                         "backupEnabled": True},
            "configuration_observed_at": "2026-11-12T10:30:00Z",
        }

        class TwoSources:
            def __init__(self):
                self.calls = []
            async def list_tools(self, refresh=False):
                return [
                    {"name": "hub_list_device_events", "inputSchema": {
                        "type": "object", "properties": {"deviceId": {"type": "string"}}}},
                    {"name": "hub_get_app_config", "inputSchema": {
                        "type": "object", "properties": {"appId": {"type": "string"}}}},
                ]
            async def call(self, name, args):
                self.calls.append((name, args))
                payload = source_event if name == "hub_list_device_events" else source_config
                return {"content": [{"type": "text", "text": json.dumps(payload)}]}

        class SelectingAgent(Agent):
            def __init__(self):
                self.round_messages = []
            async def round(self, messages, tools, remaining):
                self.round_messages.append(messages)
                if len(self.round_messages) == 1:
                    return {"content": "", "tool_calls": [{
                        "function": {"name": "hub_list_device_events",
                                     "arguments": {"deviceId": "SYN-501"}}}]}
                if len(self.round_messages) == 2:
                    return {"content": "", "tool_calls": [{
                        "function": {"name": "hub_get_app_config",
                                     "arguments": {"appId": "SYN-42"}}}]}
                return {"content": ("The command issuer is recorded. The current "
                                    "settings allow a 20-second timer and a backup; "
                                    "the exact initiating condition is unverified.")}

        async def scenario():
            model = SelectingAgent()
            mcp = TwoSources()
            result = await model.answer("Why did Synthetic Appliance turn off?", [], mcp, 30)
            self.assertTrue(result["success"])
            self.assertEqual(result["rounds"], 3)
            self.assertEqual(len(result["tool_calls"]), 2)
            self.assertEqual([name for name, _ in mcp.calls],
                             ["hub_list_device_events", "hub_get_app_config"])
            self.assertIn("2026-11-12T09:45:30.400Z", result["tool_calls"][0]["response"])
            self.assertIn("Synthetic Gateway", result["tool_calls"][0]["response"])
            self.assertIn("backupEnabled", result["tool_calls"][1]["response"])
            self.assertIn("unverified", result["answer"])
            self.assertIn("T-D", model.round_messages[0][0]["content"])
            self.assertEqual(source_event["count"], 2)  # original was not modified

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()

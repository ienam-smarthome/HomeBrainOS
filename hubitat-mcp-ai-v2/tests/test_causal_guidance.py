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
        self.assertIn("settings at the historical event time", _SKILL)
        self.assertIn("does not explain a later short timer", _SKILL)
        self.assertIn("source timestamp and time zone", _SKILL)
        self.assertIn("only plausible cause", _SKILL)
        self.assertIn("Do not retry a failed write", reference)
        for incident in ("Hallway Light", "4012", "7752", "7770", "FP300", "Bedroom 1"):
            self.assertNotIn(incident, reference)

    def test_negative_claims_distinguish_samples_from_interval_and_absence(self):
        reference = (Path(__file__).resolve().parents[1] / "rootfs" / "app" /
                     "skills" / "hubitat" / "causal-investigations.md").read_text()
        for phrase in (
            "Test claims about what *did not* happen",
            "entire interval",
            "zero/low measurement",
            "same state",
            "reporting path functioned",
            "returned rows",
            "No `command-off` row",
            "Could a different outcome have occurred within a gap",
            "execution trace plus causal trigger",
            "Uncertainty is a consequence of evidence",
        ):
            self.assertIn(phrase, reference)
            self.assertIn(phrase, _SKILL)
        # The production prompt must not be tied to any exposed household
        # incident; synthetic data is not a disguised benchmark replay.
        for actual_target in ("Freezer", "7105", "16:19:12", "Hallway Light 1",
                              "FanBoost", "app 4012"):
            self.assertNotIn(actual_target, reference)

    def test_negative_source_scope_kept_intact_without_forced_tool_reads(self):
        """Model still receives original limited receipts; policy is not a tool router."""
        observations = {
            "events": [
                {"name": "reading", "value": "0",
                 "date": "2026-08-02T10:10:00Z",
                 "producedBy": {"name": "Synthetic Sensor"}},
                {"name": "reading", "value": "2",
                 "date": "2026-08-02T10:12:00Z",
                 "producedBy": {"name": "Synthetic Sensor"}},
            ],
            "count": 2,
        }
        scope = {
            "source_scope": "returned event rows only",
            "events_returned": 2,
            "limit_reached": False,
            "native_store_checked_independently": False,
            "can_infer_requested_window_fully_covered": False,
            "can_infer_uninterrupted_state_between_events": False,
        }
        tool_data = {
            "content": [{"type": "text", "text": json.dumps(observations)}],
            "client_event_source_scope": scope,
        }

        class SyntheticRead:
            def __init__(self):
                self.calls = []
            async def list_tools(self, refresh=False):
                return [{"name": "hub_list_device_events",
                         "inputSchema": {"type": "object", "properties": {
                             "deviceId": {"type": "string"}}}}]
            async def call(self, name, args):
                self.calls.append((name, args))
                return tool_data

        class ScenarioAgent(Agent):
            def __init__(self):
                self.messages = []
            async def round(self, messages, tools, remaining):
                self.messages.append(messages)
                if len(self.messages) == 1:
                    return {"content": "", "tool_calls": [{
                        "function": {"name": "hub_list_device_events",
                                     "arguments": {"deviceId": "SYN-31"}}}]}
                return {"content": ("A low value was reported, then a higher value. "
                                   "The source does not establish continuous "
                                   "state or rule out an unobserved interruption.")}

        async def run():
            client = SyntheticRead()
            model = ScenarioAgent()
            result = await model.answer("Did the synthetic system ever go offline?", [],
                                        client, 30)
            self.assertTrue(result["success"])
            self.assertEqual(result["rounds"], 2)
            self.assertEqual(client.calls, [("hub_list_device_events",
                                             {"deviceId": "SYN-31"})])
            self.assertEqual(len(result["tool_calls"]), 1)
            self.assertIn("can_infer_uninterrupted_state_between_events",
                          result["tool_calls"][0]["response"])
            self.assertIn("Synthetic Sensor", result["tool_calls"][0]["response"])
            self.assertIn("rule out", result["answer"])
            self.assertIn("Test claims about what *did not* happen",
                          model.messages[0][0]["content"])
            self.assertEqual(scope["native_store_checked_independently"], False)
        asyncio.run(run())

    def test_confident_positive_control_is_not_rewritten_to_unknown(self):
        """Preserve model's ability to state genuinely supported causes."""
        class NoTools:
            async def list_tools(self, refresh=False):
                return []
            async def call(self, name, args):
                raise AssertionError("No model tool selection expected")

        class PositiveAgent(Agent):
            def __init__(self):
                pass  # A fixed synthetic responder never connects to Ollama.
            async def round(self, messages, tools, remaining):
                return {"content": ("The synthetic execution trace explicitly names "
                                    "the enabled threshold callback and its state "
                                    "change; that recorded cause is verified.")}

        async def run():
            result = await PositiveAgent().answer("Report the fictional trace", [],
                                                  NoTools(), 30)
            self.assertEqual(result["rounds"], 1)
            self.assertIn("that recorded cause is verified", result["answer"])
            self.assertEqual(result["tool_calls"], [])
        asyncio.run(run())

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
            result = await model.answer("Why did Synthetic Appliance turn off?", [], mcp, 30,
                                        enable_final_claim_audit=False)
            self.assertTrue(result["success"])
            self.assertEqual(result["rounds"], 4)
            self.assertTrue(result["source_review_invoked"])
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

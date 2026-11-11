"""Alpha.43 model-led source-sufficiency lifecycle regressions.

Entirely fictional MCP and model replies. A green result proves that the
model can choose further reads, not that any deployed model will do so.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent
from investigation_review import (
    SOURCE_REVIEW_PROMPT, is_causal_question, should_review_completion,
)


def native_events(rows):
    raw = {"device": "Fictional Relay", "events": rows, "count": len(rows)}
    return {"content": [{"type": "text", "text": json.dumps(raw)}],
            "_meta": {"test": "unchanged-native-receipt"}}


_STATE = {"name": "switch", "value": "off", "type": "physical",
          "date": "2026-03-01T08:00:00.000Z",
          "producedBy": {"name": "Fixture bridge"}}
_COMMAND = {"name": "command-off", "type": "command",
            "date": "2026-03-01T07:59:59.000Z",
            "producedBy": {"name": "Fixture application"}}


class FakeMCP:
    def __init__(self):
        self.calls = []
        self.filtered = native_events([_STATE])
        self.unfiltered = native_events([_COMMAND, _STATE])

    async def list_tools(self, refresh=False):
        return [{"name": "hub_read_history",
                 "description": "Read selected native history. Optional attribute filter.",
                 "inputSchema": {"type": "object",
                                 "properties": {"attribute": {"type": "string"},
                                                "limit": {"type": "integer"}}}}]

    async def call(self, name, args):
        self.calls.append((name, args))
        return self.filtered if "attribute" in args else self.unfiltered


def call_history(args):
    return {"function": {"name": "hub_read_history",
                         "arguments": args}}


class ScriptedAgent(Agent):
    def __init__(self, replies):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 15)
        self.replies = list(replies)
        self.round_messages = []

    async def round(self, messages, tools, remaining):
        self.round_messages.append([dict(row) for row in messages])
        return self.replies.pop(0)


class ReviewDecisionTests(unittest.TestCase):
    def test_causal_intent_without_device_specific_rules(self):
        for text in ("Why did the relay change?", "What triggered this fan cycle?",
                     "What caused that power dip?", "Reason for the alarm",
                     "Who switched the actuator off?"):
            self.assertTrue(is_causal_question(text), text)
        self.assertFalse(is_causal_question("Show current temperature"))
        self.assertFalse(is_causal_question("List all the rooms"))
        self.assertFalse(should_review_completion(
            "Why did this happen?", available_tools=True,
            already_reviewed=False, remaining_seconds=3))
        self.assertFalse(should_review_completion(
            "Why did this happen?", available_tools=True,
            already_reviewed=True, remaining_seconds=30))
        self.assertFalse(should_review_completion(
            "Why did this happen?", available_tools=False,
            already_reviewed=False, remaining_seconds=30))

    def test_prompt_is_general_and_explicitly_read_only(self):
        self.assertIn("READ-ONLY", SOURCE_REVIEW_PROMPT)
        self.assertIn("no prescribed source order", SOURCE_REVIEW_PROMPT)
        self.assertIn("filtered state history", SOURCE_REVIEW_PROMPT)
        self.assertNotIn("Bedroom 3", SOURCE_REVIEW_PROMPT)
        self.assertNotIn("7841", SOURCE_REVIEW_PROMPT)


class ReviewLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_itself_selects_discriminating_followup_read(self):
        hub = FakeMCP()
        scripted = [
            {"content": "", "tool_calls": [call_history({"attribute": "switch", "limit": 20})]},
            {"content": "Probably an external controller.", "tool_calls": []},
            {"content": "", "tool_calls": [call_history({"limit": 50})]},
            {"content": ("A command from Fixture application precedes the report, "
                         "but its internal trigger is unverified."),
             "tool_calls": []},
        ]
        agent = ScriptedAgent(scripted)
        try:
            result = await agent.answer("Why did the relay turn off? Do not change anything.",
                                        [], hub, 90)
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(result["rounds"], 4)
        self.assertEqual(hub.calls, [
            ("hub_read_history", {"attribute": "switch", "limit": 20}),
            ("hub_read_history", {"limit": 50}),
        ])
        self.assertEqual(len(result["tool_calls"]), 2)
        self.assertEqual(json.loads(result["tool_calls"][0]["response"])["content"],
                         hub.filtered["content"])
        self.assertEqual(json.loads(result["tool_calls"][1]["response"])["content"],
                         hub.unfiltered["content"])
        self.assertIn("internal trigger is unverified", result["answer"])
        # The model was shown its own preliminary draft and available tools;
        # the client did not silently inject an MCP call or rewrite the answer.
        prompt_messages = agent.round_messages[2]
        self.assertEqual(prompt_messages[-1]["role"], "user")
        self.assertIn("evidence-sufficiency", prompt_messages[-1]["content"])
        self.assertEqual(prompt_messages[-2]["role"], "assistant")
        self.assertIn("Probably an external controller", prompt_messages[-2]["content"])

    async def test_model_can_stop_at_unknown_without_any_extra_mcp_calls(self):
        hub = FakeMCP()
        agent = ScriptedAgent([
            {"content": "", "tool_calls": [call_history({"attribute": "switch"})]},
            {"content": "A bridge reported OFF; likely external.", "tool_calls": []},
            {"content": ("A bridge reported OFF. The initiator is unverified because "
                         "the history was filtered to switch state."), "tool_calls": []},
        ])
        try:
            result = await agent.answer("Explain why the actuator stopped", [], hub, 60)
        finally:
            await agent.close()
        self.assertEqual(result["rounds"], 3)
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(len(hub.calls), 1)
        self.assertIn("initiator is unverified", result["answer"])

    async def test_noncausal_question_keeps_normal_completion(self):
        hub = FakeMCP()
        agent = ScriptedAgent([{"content": "Relay is off.", "tool_calls": []}])
        try:
            result = await agent.answer("Show relay status", [], hub, 60)
        finally:
            await agent.close()
        self.assertEqual(result["rounds"], 1)
        self.assertFalse(result["source_review_invoked"])
        self.assertEqual(hub.calls, [])

    async def test_no_mcp_call_for_checkpoint_itself(self):
        hub = FakeMCP()
        agent = ScriptedAgent([
            {"content": "Cause unknown from available evidence.", "tool_calls": []},
            {"content": "No discriminating read was obtained. Cause unknown.",
             "tool_calls": []},
        ])
        try:
            result = await agent.answer("Why was the alarm raised?", [], hub, 60)
        finally:
            await agent.close()
        self.assertEqual(result["rounds"], 2)
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(hub.calls, [])
        self.assertEqual(result["tool_calls"], [])


if __name__ == "__main__":
    unittest.main()

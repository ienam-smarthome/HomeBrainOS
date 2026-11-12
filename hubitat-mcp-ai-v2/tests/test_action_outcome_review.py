"""Model-led action outcome review: fictional native MCP receipts only.

Tests the live loop's review opportunity and safety boundaries. Synthetic
scripts are NOT evidence that an external cloud model will select the right
command in a real household. No real Hubitat, networking or router writes.
"""
import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent, _SKILL
from investigation_review import (
    ACTION_OUTCOME_REVIEW_PROMPT, review_prompt, should_review_completion,
)


def call(name, args):
    return {"function": {"name": name, "arguments": args}}


def result(data):
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


class SyntheticHub:
    def __init__(self, *, accepted=True, pending="none"):
        self.calls = []
        self.accepted = accepted
        self.pending = pending
        self.catalog = [
            {"name": "hub_get_device", "inputSchema": {"type": "object"}},
            {"name": "hub_get_device_attribute", "inputSchema": {"type": "object"}},
            {"name": "hub_list_device_dependents", "inputSchema": {"type": "object"}},
            {"name": "hub_call_device_command", "inputSchema": {"type": "object"}},
        ]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, arguments):
        self.calls.append((name, arguments.copy()))
        if name == "hub_call_device_command":
            return result({
                "success": self.accepted, "command": arguments.get("command"),
                "deviceId": arguments.get("deviceId"),
                "state": {"switch": {"value": "on"}},
            })
        if name == "hub_get_device":
            return result({
                "id": "301", "label": "Fictional Network Relay",
                "commands": [{"name": "deferCutoff",
                              "arguments": [{"name": "Minutes", "type": "NUMBER"}]}],
                "attributes": [{"name": "pendingUntil", "value": self.pending}],
            })
        if name == "hub_get_device_attribute":
            return result({"deviceId": "301", "attribute": "pendingUntil",
                           "value": self.pending})
        if name == "hub_list_device_dependents":
            return result({"deviceId": "302", "appsUsing": [],
                           "count": 0})
        raise AssertionError("Unexpected synthetic tool " + name)


class ScriptedAgent(Agent):
    def __init__(self, responses):
        super().__init__("http://localhost:11434", "fake", "", 10)
        self.responses = list(responses)
        self.seen_tools = []
        self.seen_messages = []

    async def round(self, messages, tools, remaining):
        self.seen_tools.append([x["function"]["name"] for x in tools])
        self.seen_messages.append([dict(x) for x in messages])
        if not self.responses:
            raise AssertionError("Unexpected extra model round")
        return self.responses.pop(0)


class ActionReviewLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_indirect_helper_write_does_not_verify_future_target(self):
        hub = SyntheticHub()
        agent = ScriptedAgent([
            {"content": "Switch on the helper to begin the intended delay.",
             "tool_calls": [call("hub_call_device_command",
                                 {"deviceId": "302", "command": "on"})]},
            {"content": "A five-minute cutoff is now scheduled."},
            {"content": "Check the target's own pending timer.",
             "tool_calls": [call("hub_get_device", {"deviceId": "301"})]},
            {"content": ("Only helper 302 was switched on. The target reports "
                         "pendingUntil=none; a five-minute cutoff is not verified.")},
        ])
        try:
            answer = await agent.answer("Cut power to Fictional Network Relay after five minutes",
                                        [], hub, 90)
        finally:
            await agent.close()
        self.assertEqual(answer["source_review_kind"], "action_outcome")
        self.assertTrue(answer["source_review_invoked"])
        self.assertFalse(answer["final_claim_audit_invoked"])
        self.assertEqual(answer["final_claim_audit_status"], "not_applicable_to_action_review")
        self.assertEqual(answer["rounds"], 4)
        self.assertEqual([name for name, _ in hub.calls],
                         ["hub_call_device_command", "hub_get_device"])
        self.assertNotIn("hub_call_device_command", agent.seen_tools[2])
        self.assertIn("hub_get_device", agent.seen_tools[2])
        self.assertIn("homebrain_inspect_mcp_catalog", agent.seen_tools[2])
        self.assertIn("Action/outcome source review", agent.seen_messages[2][-1]["content"])
        self.assertEqual(len(answer["tool_calls"]), 2)
        self.assertTrue(answer["tool_calls"][0]["possible_native_action"])
        self.assertIn("client_action_receipt_scope",
                      answer["tool_calls"][0]["response"])
        self.assertNotIn("scheduled.", answer["answer"])

    async def test_native_deferred_command_receipt_then_readback(self):
        hub = SyntheticHub(pending="2026-02-01T15:07:00Z")
        agent = ScriptedAgent([
            {"content": "Read the native command supported by the target.",
             "tool_calls": [call("hub_get_device", {"deviceId": "301"})]},
            {"content": "Submit the advertised seven-minute command.",
             "tool_calls": [call("hub_call_device_command", {
                 "deviceId": "301", "command": "deferCutoff", "parameters": ["7"]})]},
            {"content": "The native command was accepted; timer not yet read back."},
            {"content": "Verify the pendingUntil attribute.",
             "tool_calls": [call("hub_get_device_attribute", {
                 "deviceId": "301", "attribute": "pendingUntil"})]},
            {"content": ("The target reports pendingUntil="
                         "2026-02-01T15:07:00Z. Subsequent physical cutoff "
                         "has not yet been observed.")},
        ])
        try:
            answer = await agent.answer("Disconnect Fictional Network Relay in seven minutes",
                                        [], hub, 90)
        finally:
            await agent.close()
        self.assertEqual(answer["source_review_kind"], "action_outcome")
        self.assertEqual(answer["rounds"], 5)
        self.assertEqual([name for name, _ in hub.calls], [
            "hub_get_device", "hub_call_device_command", "hub_get_device_attribute",
        ])
        self.assertEqual(hub.calls[1][1]["parameters"], ["7"])
        self.assertNotIn("hub_call_device_command", agent.seen_tools[3])
        self.assertFalse(answer["final_claim_audit_invoked"])
        self.assertIn("Subsequent physical cutoff", answer["answer"])

    async def test_read_only_answer_does_not_trigger_write_outcome_review(self):
        hub = SyntheticHub()
        agent = ScriptedAgent([
            {"tool_calls": [call("hub_get_device", {"deviceId": "301"})]},
            {"content": "The target advertises deferCutoff; no write was requested."},
        ])
        try:
            reply = await agent.answer("Check device capabilities", [], hub, 90)
        finally:
            await agent.close()
        self.assertEqual(reply["rounds"], 2)
        self.assertFalse(reply["source_review_invoked"])
        self.assertEqual([name for name, _ in hub.calls], ["hub_get_device"])

    async def test_review_cannot_dispatch_a_replacement_write(self):
        hub = SyntheticHub()
        agent = ScriptedAgent([
            {"tool_calls": [call("hub_call_device_command",
                                 {"deviceId": "302", "command": "on"})]},
            {"content": "A relay cutoff is scheduled."},
            {"tool_calls": [call("hub_call_device_command",
                                 {"deviceId": "301", "command": "off"})]},
            {"content": "The attempted replacement command was not executed."},
        ])
        try:
            reply = await agent.answer("Disconnect Fictional Network Relay in five minutes",
                                       [], hub, 90)
        finally:
            await agent.close()
        self.assertEqual([name for name, _ in hub.calls],
                         ["hub_call_device_command"])
        self.assertEqual(reply["tool_calls"][-1]["success"], False)
        self.assertIn("read-only", reply["tool_calls"][-1]["error"])
        self.assertEqual(reply["source_review_kind"], "action_outcome")

    def test_review_eligibility_and_prompt_are_general(self):
        self.assertFalse(should_review_completion(
            "Close the valve after five minutes", available_tools=True,
            already_reviewed=False, remaining_seconds=60))
        self.assertTrue(should_review_completion(
            "Close the valve after five minutes", available_tools=True,
            already_reviewed=False, remaining_seconds=60,
            has_action_receipt=True))
        self.assertFalse(should_review_completion(
            "Close the valve after five minutes", available_tools=True,
            already_reviewed=False, remaining_seconds=4,
            has_action_receipt=True))
        self.assertEqual(review_prompt("action_outcome"), ACTION_OUTCOME_REVIEW_PROMPT)
        self.assertIn("TARGET, ACTION and TIMING", _SKILL)
        self.assertIn("READ-ONLY", ACTION_OUTCOME_REVIEW_PROMPT)
        self.assertNotIn("Google TV", ACTION_OUTCOME_REVIEW_PROMPT)
        self.assertNotIn("6923", _SKILL)


if __name__ == "__main__":
    unittest.main()

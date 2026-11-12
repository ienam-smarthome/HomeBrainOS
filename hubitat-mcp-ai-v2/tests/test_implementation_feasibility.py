"""Model-led one-time implementation feasibility, fictional read-only MCP.

Fixtures prove access to current tool-schema and documentation evidence, not
that an LLM can author a real single-use rule. No household IDs, live hub,
device changes or rules are used.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent, _SKILL
from investigation_review import (
    IMPLEMENTATION_FEASIBILITY_REVIEW_PROMPT,
    is_implementation_feasibility_draft, should_review_completion, review_prompt,
)


def call(tool_name, **args):
    return {"function": {"name": tool_name, "arguments": args}}


def receipt(data):
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


class SyntheticHub:
    """A fictional actuator and an unverified one-time rule writer."""

    def __init__(self, has_writer=True):
        self.calls = []
        self.has_writer = has_writer
        self.catalog = [
            {"name": "hub_get_device", "inputSchema": {"type": "object"}},
            {"name": "hub_get_tool_guide",
             "inputSchema": {"type": "object",
                             "properties": {"section": {"type": "string"}}}},
        ]
        if has_writer:
            self.catalog.append({
                "name": "hub_set_rule",
                "description": "Native rule authoring (writes on execution)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "enum": ["create", "update"]},
                        "rule": {"type": "object"},
                        "confirm": {"type": "boolean"},
                    },
                    "required": ["operation", "rule"],
                },
            })

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        if name == "hub_get_device":
            return receipt({
                "id": "LAB-VALVE", "label": "Bench Valve",
                "commands": [{"name": "open"}, {"name": "close"}],
                "attributes": [{"name": "valve", "value": "closed"}],
            })
        if name == "hub_get_tool_guide":
            return receipt({
                "success": True, "section": "set_rule_reference",
                "content": (
                    "Native automation writer supports event-triggered rules "
                    "and delay actions. No immediate one-shot or dated trigger "
                    "contract is established by this excerpt."
                ),
            })
        raise AssertionError("No native write or undisclosed native call allowed")


class ScriptedModel(Agent):
    def __init__(self, script):
        super().__init__("http://localhost:11434", "fixture", "", 10)
        self.script = list(script)
        self.seen_tools = []
        self.seen_messages = []

    async def round(self, messages, tools, remaining):
        self.seen_tools.append([t["function"]["name"] for t in tools])
        self.seen_messages.append(messages[-1]["content"])
        if not self.script:
            raise AssertionError("Unexpected extra model round")
        return self.script.pop(0)


class FeasibilityReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_claim_to_create_rule_requires_live_writer_and_trigger_evidence(self):
        hub = SyntheticHub(has_writer=True)
        model = ScriptedModel([
            {"tool_calls": [call("hub_get_device", deviceId="LAB-VALVE")]},
            {"content": ("A separate automation is required. I can create a "
                         "one-time rule to open Bench Valve after 2 minutes.")},
            {"tool_calls": [call("homebrain_inspect_mcp_catalog",
                                 name="hub_set_rule")]},
            {"tool_calls": [call("hub_get_tool_guide",
                                 section="set_rule_reference")]},
            {"content": (
                "The device advertises only immediate open/close. "
                "hub_set_rule is directly visible and its schema is available, "
                "but neither a currently supported immediate one-time trigger "
                "nor effective authoring permission was established. "
                "A scheduler is a possible design, not a verified creatable "
                "rule; no command or rule was executed."
            )},
        ])
        try:
            result = await model.answer(
                "Investigate opening Bench Valve after two minutes. Do not change anything.",
                [], hub, 90)
        finally:
            await model.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["source_review_kind"], "implementation_feasibility")
        self.assertTrue(result["source_review_invoked"])
        self.assertFalse(result["final_claim_audit_invoked"])
        self.assertEqual(result["final_claim_audit_status"],
                         "not_applicable_to_feasibility_review")
        self.assertEqual(result["rounds"], 5)
        self.assertEqual([name for name, _ in hub.calls],
                         ["hub_get_device", "hub_get_tool_guide"])
        self.assertNotIn("hub_set_rule", model.seen_tools[2])
        self.assertIn("homebrain_inspect_mcp_catalog", model.seen_tools[2])
        self.assertIn("Implementation-feasibility source review",
                      model.seen_messages[2])
        inspected = json.loads(result["tool_calls"][1]["response"])[
            "local_mcp_catalog"]
        self.assertTrue(inspected["direct_top_level_exposed"])
        self.assertEqual(inspected["direct_definition"]["inputSchema"],
                         hub.catalog[2]["inputSchema"])
        self.assertFalse(inspected["write_authorization_verified"])
        self.assertIn("not a verified creatable", result["answer"])
        self.assertFalse(any(t.get("possible_native_action")
                             for t in result["tool_calls"]))

    async def test_absent_rule_writer_remains_unverified_not_impossible_everywhere(self):
        hub = SyntheticHub(has_writer=False)
        model = ScriptedModel([
            {"tool_calls": [call("hub_get_device", deviceId="LAB-VALVE")]},
            {"content": "The valve needs a one-time automation; I can set up a rule."},
            {"tool_calls": [call("homebrain_inspect_mcp_catalog",
                                 name="hub_set_rule")]},
            {"content": (
                "The checked catalog does not expose a direct hub_set_rule "
                "writer or matching gateway candidate. A rule cannot be "
                "promised through this verified path; alternative external "
                "implementations remain unknown."
            )},
        ])
        try:
            result = await model.answer("Can a valve open after two minutes?",
                                        [], hub, 90)
        finally:
            await model.close()
        self.assertEqual(result["source_review_kind"], "implementation_feasibility")
        self.assertEqual(result["rounds"], 4)
        self.assertEqual([c[0] for c in hub.calls], ["hub_get_device"])
        catalog_result = json.loads(result["tool_calls"][1]["response"])[
            "local_mcp_catalog"]
        self.assertFalse(catalog_result["direct_top_level_exposed"])
        self.assertEqual(catalog_result["gateway_candidates_from_live_schema"], [])
        self.assertIn("remain unknown", result["answer"])

    async def test_review_rejects_attempted_rule_creation(self):
        hub = SyntheticHub()
        model = ScriptedModel([
            {"tool_calls": [call("hub_get_device", deviceId="LAB-VALVE")]},
            {"content": "I can create a one-time automation for this valve."},
            {"tool_calls": [call("hub_set_rule", operation="create",
                                 rule={"name": "Synthetic one-shot"})]},
            {"content": "No automation was created; authoring was rejected."},
        ])
        try:
            reply = await model.answer(
                "Can this valve open after two minutes? Do not change anything.",
                [], hub, 90)
        finally:
            await model.close()
        self.assertEqual(reply["source_review_kind"], "implementation_feasibility")
        self.assertEqual([c[0] for c in hub.calls], ["hub_get_device"])
        self.assertFalse(reply["tool_calls"][-1]["success"])
        self.assertIn("read-only", reply["tool_calls"][-1]["error"])

    async def test_no_review_for_existing_rule_description_without_new_promise(self):
        hub = SyntheticHub()
        model = ScriptedModel([
            {"tool_calls": [call("hub_get_device", deviceId="LAB-VALVE")]},
            {"content": "The valve advertises open/close. No rule was created."},
        ])
        try:
            result = await model.answer("Which commands does Bench Valve advertise?",
                                        [], hub, 90)
        finally:
            await model.close()
        self.assertFalse(result["source_review_invoked"])
        self.assertEqual(result["rounds"], 2)


class EligibilityTests(unittest.TestCase):
    def test_generic_positive_and_negative_feasibility_claims(self):
        for phrase in (
            "A separate automation is required.",
            "I can create a one-time rule.",
            "I would need to create a schedule rule to turn on the valve.",
            "This action requires a workflow.",
            "A scheduler is necessary.",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(is_implementation_feasibility_draft(phrase))
        for phrase in (
            "A future actuation remains unknown.",
            "The current rule has a delay action, but its trigger is unclear.",
            "I cannot verify the cause from synthetic evidence.",
            "I can control the valve directly using the available on command.",
            None,
        ):
            with self.subTest(phrase=phrase):
                self.assertFalse(is_implementation_feasibility_draft(phrase))
        self.assertTrue(should_review_completion(
            "Could this valve open later?", available_tools=True,
            already_reviewed=False, remaining_seconds=35,
            draft="I can create a one-time rule."))
        self.assertFalse(should_review_completion(
            "Could this valve open later?", available_tools=True,
            already_reviewed=False, remaining_seconds=5,
            draft="I can create a one-time rule."))
        self.assertEqual(review_prompt("implementation_feasibility"),
                         IMPLEMENTATION_FEASIBILITY_REVIEW_PROMPT)
        self.assertIn("immediate/dated/one-shot trigger", IMPLEMENTATION_FEASIBILITY_REVIEW_PROMPT)
        self.assertIn("one-time", _SKILL)
        self.assertNotIn("Nest Hub", IMPLEMENTATION_FEASIBILITY_REVIEW_PROMPT)
        self.assertNotIn("Google TV", _SKILL)


if __name__ == "__main__":
    unittest.main()

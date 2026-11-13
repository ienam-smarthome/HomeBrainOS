"""Model-selected alternative actuator discovery; fictional read-only MCP."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent, _SKILL
from investigation_review import (
    CAPABILITY_DISCOVERY_REVIEW_PROMPT, is_capability_denial_draft,
    should_review_completion, review_prompt,
)


def tc(name, **kwargs):
    return {"function": {"name": name, "arguments": kwargs}}


def receipt(value):
    return {"content": [{"type": "text", "text": json.dumps(value)}]}


class SyntheticMCP:
    def __init__(self, actuator=True):
        self.actuator = actuator
        self.calls = []
        self.catalog = [
            {"name": n, "inputSchema": {"type": "object"}} for n in
            ("hub_list_devices", "hub_get_device", "hub_call_device_command")
        ]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "hub_call_device_command":
            raise AssertionError("Synthetic review must not execute a write")
        media = {"id": "LAB-MEDIA", "label": "Bench Panel",
                 "physicalRef": "LAB-17"}
        actor = {"id": "LAB-ACTOR", "label": "Boundary Controller",
                 "physicalRef": "LAB-17"}
        if name == "hub_list_devices" and args.get("labelFilter") == "Bench Panel":
            return receipt({"devices": [media], "count": 1, "total": 1,
                            "unfilteredTotal": 3, "labelFilter": "Bench Panel"})
        if name == "hub_list_devices" and args.get("format") == "context":
            devices = [media, {"id": "LAB-OTHER", "label": "Unrelated Sensor",
                               "physicalRef": "LAB-99"}]
            if self.actuator:
                devices.append(actor)
            return receipt({"devices": devices, "count": len(devices),
                            "total": len(devices),
                            "unfilteredTotal": len(devices)})
        if name == "hub_get_device" and args.get("deviceId") == "LAB-MEDIA":
            return receipt({**media, "commands": [{"name": "pause"}]})
        if name == "hub_get_device" and args.get("deviceId") == "LAB-ACTOR":
            return receipt({**actor, "commands": [
                {"name": "deferEnable",
                 "arguments": [{"name": "Delay", "type": "NUMBER"}]}]})
        raise AssertionError("Unexpected synthetic read")


class Model(Agent):
    def __init__(self, script):
        super().__init__("http://localhost:11434", "fixture", "", 10)
        self.script = list(script)
        self.seen_tools = []
        self.seen_messages = []

    async def round(self, messages, tools, remaining):
        self.seen_tools.append([t["function"]["name"] for t in tools])
        self.seen_messages.append(messages[-1]["content"])
        if not self.script:
            raise AssertionError("Unexpected model round")
        return self.script.pop(0)


class DiscoveryLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_denial_then_broader_source_and_actuator_detail(self):
        hub = SyntheticMCP()
        model = Model([
            {"tool_calls": [tc("hub_list_devices", labelFilter="Bench Panel")]},
            {"tool_calls": [tc("hub_get_device", deviceId="LAB-MEDIA")]},
            {"content": "The media device cannot implement delayed activation."},
            {"tool_calls": [tc("hub_list_devices", format="context")]},
            {"tool_calls": [tc("hub_get_device", deviceId="LAB-ACTOR")]},
            {"content": ("The separate controller advertises deferEnable and "
                         "shares a reported physicalRef, but identity and "
                         "authorization still need confirmation. No write sent.")},
        ])
        try:
            reply = await model.answer("Can you enable Bench Panel in three minutes?",
                                       [], hub, 90)
        finally:
            await model.close()
        self.assertTrue(reply["success"])
        self.assertEqual(reply["source_review_kind"], "capability_discovery")
        self.assertTrue(reply["source_review_invoked"])
        self.assertFalse(reply["final_claim_audit_invoked"])
        self.assertEqual(reply["final_claim_audit_status"],
                         "not_applicable_to_capability_review")
        self.assertEqual(reply["rounds"], 6)
        self.assertEqual([x[0] for x in hub.calls],
                         ["hub_list_devices", "hub_get_device",
                          "hub_list_devices", "hub_get_device"])
        self.assertEqual(hub.calls[2][1], {"format": "context"})
        self.assertNotIn("hub_call_device_command", model.seen_tools[3])
        self.assertIn("hub_list_devices", model.seen_tools[3])
        self.assertIn("Capability/control-surface", model.seen_messages[3])
        self.assertIn("deferEnable", reply["answer"])

    async def test_no_matching_actuator_remains_unknown(self):
        hub = SyntheticMCP(actuator=False)
        model = Model([
            {"tool_calls": [tc("hub_list_devices", labelFilter="Bench Panel")]},
            {"tool_calls": [tc("hub_get_device", deviceId="LAB-MEDIA")]},
            {"content": "No matching capability exists; I cannot do this."},
            {"tool_calls": [tc("hub_list_devices", format="context")]},
            {"content": ("The checked inventory contains no verified matching "
                         "controller; unexamined external systems are unknown.")},
        ])
        try:
            reply = await model.answer("Can you enable Bench Panel in three minutes?",
                                       [], hub, 90)
        finally:
            await model.close()
        self.assertEqual(reply["rounds"], 5)
        self.assertEqual(reply["source_review_kind"], "capability_discovery")
        self.assertEqual(len(hub.calls), 3)
        self.assertIn("unknown", reply["answer"])

    async def test_no_extra_review_for_supported_read_only_answer(self):
        hub = SyntheticMCP()
        model = Model([
            {"tool_calls": [tc("hub_get_device", deviceId="LAB-ACTOR")]},
            {"content": "The device advertises a deferred command; not executed."},
        ])
        try:
            reply = await model.answer("What can the Boundary Controller do?",
                                       [], hub, 90)
        finally:
            await model.close()
        self.assertEqual(reply["rounds"], 2)
        self.assertFalse(reply["source_review_invoked"])

    async def test_denial_review_refuses_model_write(self):
        hub = SyntheticMCP()
        model = Model([
            {"tool_calls": [tc("hub_get_device", deviceId="LAB-MEDIA")]},
            {"content": "The media device cannot implement delayed activation."},
            {"tool_calls": [tc("hub_call_device_command",
                                deviceId="LAB-MEDIA", command="on")]},
            {"content": "No write occurred; the review call was rejected."},
        ])
        try:
            reply = await model.answer("Can you enable Bench Panel in three minutes?",
                                       [], hub, 90)
        finally:
            await model.close()
        self.assertEqual(len(hub.calls), 1)
        self.assertEqual(reply["source_review_kind"], "capability_discovery")
        self.assertFalse(reply["tool_calls"][-1]["success"])
        self.assertIn("read-only", reply["tool_calls"][-1]["error"])


class EligibilityTests(unittest.TestCase):
    def test_general_denials_and_eligibility(self):
        for phrase in ("I cannot implement the request.",
                       "Neither can be implemented directly.",
                       "This device doesn't support the capability.",
                       "No suitable command is exposed.",
                       "I am unable to perform this operation."):
            with self.subTest(phrase=phrase):
                self.assertTrue(is_capability_denial_draft(phrase))
        self.assertFalse(is_capability_denial_draft(
            "An alternative device advertises the required command."))
        self.assertFalse(is_capability_denial_draft(None))
        self.assertFalse(is_capability_denial_draft(
            "Cannot verify cause from synthetic returned sources."))
        self.assertTrue(should_review_completion(
            "Enable a lamp", available_tools=True, already_reviewed=False,
            remaining_seconds=30, draft="I cannot do it from this device."))
        self.assertFalse(should_review_completion(
            "Enable a lamp", available_tools=True, already_reviewed=False,
            remaining_seconds=5, draft="I cannot do it from this device."))
        self.assertEqual(review_prompt("capability_discovery"),
                         CAPABILITY_DISCOVERY_REVIEW_PROMPT)
        self.assertIn("NAMED PHYSICAL TARGET", _SKILL)
        self.assertIn("unfilteredTotal", _SKILL)
        self.assertNotIn("Google TV", CAPABILITY_DISCOVERY_REVIEW_PROMPT)
        self.assertNotIn("Nest Hub", _SKILL)


if __name__ == "__main__":
    unittest.main()

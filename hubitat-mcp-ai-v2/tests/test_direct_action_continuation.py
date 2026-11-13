"""Direct ordinary device-action continuation after read-only discovery.

Fictional MCP fixtures only: no live Hubitat, router or household devices.
The model chooses its own tools; this tests the bounded continuation safety
and readback opportunity, not real cloud-model first-answer accuracy.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent, _SKILL
from investigation_review import (
    is_explicit_device_action_request, is_redundant_action_confirmation_draft,
    continuation_command_advertised, should_review_completion,
)


def call(tool_name, **args):
    return {"function": {"name": tool_name, "arguments": args}}


def receipt(data):
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


class FakeMCP:
    def __init__(self, *, allow=True, critical=False):
        self.allow = allow
        self.critical = critical
        self.calls = []
        self.writes = []
        self.catalog = [
            {"name": x, "inputSchema": {"type": "object"}}
            for x in ["hub_list_devices", "hub_get_device",
                      "hub_call_device_command", "hub_get_device_attribute"]
        ]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "hub_list_devices":
            if args.get("labelFilter") == "Bench Panel":
                return receipt({"devices": [{"id": "MEDIA-1", "label": "Bench Panel"}],
                                "count": 1, "unfilteredTotal": 3})
            return receipt({"devices": [
                {"id": "MEDIA-1", "label": "Bench Panel"},
                {"id": "ACT-1", "label": "Bench Network Panel",
                 "driver": "Fictional Network Controller"},
            ], "count": 2, "unfilteredTotal": 3})
        if name == "hub_get_device":
            if args.get("deviceId") == "MEDIA-1":
                return receipt({"id": "MEDIA-1", "label": "Bench Panel",
                                "capabilities": ["MediaTransport"],
                                "commands": [{"name": "pause"}]})
            if args.get("deviceId") == "ACT-1":
                return receipt({"id": "ACT-1", "label": "Bench Network Panel",
                                "capabilities": ["Lock"] if self.critical else ["Switch"],
                                "attributes": [{"name": "access",
                                                "value": "allowed" if self.writes
                                                else "denied"}],
                                "commands": [{"name": "enable"}, {"name": "unlock"}]})
        if name == "hub_call_device_command":
            self.writes.append(dict(args))
            return receipt({"success": self.allow, "deviceId": args["deviceId"],
                            "command": args["command"]})
        if name == "hub_get_device_attribute":
            return receipt({"deviceId": "ACT-1", "attribute": "access",
                            "value": "allowed" if self.writes else "denied"})
        raise AssertionError("Unexpected fictional tool: " + name)


class Model(Agent):
    def __init__(self, script):
        super().__init__("http://localhost:11434", "fixture", "", 10)
        self.script = list(script)
        self.tools_seen = []
        self.messages_seen = []

    async def round(self, messages, tools, remaining):
        self.tools_seen.append([t["function"]["name"] for t in tools])
        self.messages_seen.append(str(messages[-1].get("content", "")))
        if not self.script:
            raise AssertionError("Extra model round")
        return self.script.pop(0)


def scripted_discovery():
    return [
        {"tool_calls": [call("hub_list_devices", labelFilter="Bench Panel")]},
        {"tool_calls": [call("hub_get_device", deviceId="MEDIA-1")]},
        {"content": "This media device cannot implement network access control."},
        {"tool_calls": [call("hub_list_devices", format="context")]},
        {"content": ("The separate controller ACT-1 appears to implement the "
                     "requested access effect. Shall I proceed?")},
    ]


class ContinuationLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_request_continues_single_write_and_readback(self):
        hub = FakeMCP()
        model = Model(scripted_discovery() + [
            {"tool_calls": [call("hub_get_device", deviceId="ACT-1")]},
            {"content": "The verified controller supports enable.",
             "tool_calls": [call("hub_call_device_command",
                                 deviceId="ACT-1", command="enable")]},
            {"tool_calls": [call("hub_get_device_attribute",
                                 deviceId="ACT-1", attribute="access")]},
            {"content": "The enable command was accepted, and the readback reports access allowed."},
        ])
        try:
            res = await model.answer("Enable Bench Panel", [], hub, 90)
        finally:
            await model.close()
        self.assertTrue(res["success"])
        self.assertEqual(res["source_review_kind"], "capability_discovery")
        self.assertTrue(res["source_review_invoked"])
        self.assertTrue(res["action_continuation_invoked"])
        self.assertTrue(res["action_continuation_write_attempted"])
        self.assertEqual(res["rounds"], 9)
        self.assertEqual(len(hub.writes), 1)
        self.assertEqual(hub.writes[0], {"deviceId": "ACT-1", "command": "enable"})
        self.assertEqual([name for name, _ in hub.calls], [
            "hub_list_devices", "hub_get_device", "hub_list_devices",
            "hub_get_device", "hub_call_device_command",
            "hub_get_device_attribute",
        ])
        self.assertNotIn("hub_call_device_command", model.tools_seen[3])
        self.assertIn("hub_call_device_command", model.tools_seen[5])
        self.assertNotIn("hub_call_device_command", model.tools_seen[7])
        self.assertIn("original user gave a direct device-action",
                      model.messages_seen[5].lower())
        self.assertIn("allowed", res["answer"])

    async def test_question_must_not_become_device_write(self):
        hub = FakeMCP()
        model = Model(scripted_discovery())
        try:
            res = await model.answer("Can you enable Bench Panel?", [], hub, 90)
        finally:
            await model.close()
        self.assertEqual(res["source_review_kind"], "capability_discovery")
        self.assertFalse(res["action_continuation_invoked"])
        self.assertEqual(len(hub.writes), 0)
        self.assertEqual(res["rounds"], 5)

    async def test_read_only_imperative_cannot_resume_write(self):
        hub = FakeMCP()
        model = Model(scripted_discovery())
        try:
            res = await model.answer(
                "Enable Bench Panel if possible; do not change anything.",
                [], hub, 90)
        finally:
            await model.close()
        self.assertFalse(res["action_continuation_invoked"])
        self.assertEqual(hub.writes, [])

    async def test_missing_advertised_command_denies_late_write(self):
        hub = FakeMCP()
        model = Model(scripted_discovery() + [
            {"tool_calls": [call("hub_call_device_command",
                                 deviceId="ACT-1", command="enable")]},
            {"content": "No command was sent; fresh target command details are missing."},
        ])
        try:
            res = await model.answer("Enable Bench Panel", [], hub, 90)
        finally:
            await model.close()
        self.assertTrue(res["action_continuation_invoked"])
        self.assertTrue(res["action_continuation_write_attempted"])
        self.assertFalse(res["tool_calls"][-1]["success"])
        self.assertIn("requires a successful hub_get_device", res["tool_calls"][-1]["error"])
        self.assertEqual(hub.writes, [])

    async def test_only_one_write_attempt_after_discovery(self):
        hub = FakeMCP(allow=False)
        model = Model(scripted_discovery() + [
            {"tool_calls": [call("hub_get_device", deviceId="ACT-1")]},
            {"tool_calls": [call("hub_call_device_command",
                                 deviceId="ACT-1", command="enable")]},
            {"tool_calls": [call("hub_call_device_command",
                                 deviceId="ACT-1", command="enable")]},
            {"content": "The first operation was declined; no retry was executed."},
        ])
        try:
            res = await model.answer("Enable Bench Panel", [], hub, 90)
        finally:
            await model.close()
        self.assertEqual(len(hub.writes), 1)
        self.assertFalse(res["tool_calls"][-1]["success"])
        self.assertIn("read-only", res["tool_calls"][-1]["error"])
        self.assertNotIn("hub_call_device_command", model.tools_seen[7])

    async def test_critical_actuator_keeps_separate_approval_requirement(self):
        hub = FakeMCP(critical=True)
        model = Model(scripted_discovery() + [
            {"tool_calls": [call("hub_get_device", deviceId="ACT-1")]},
            {"tool_calls": [call("hub_call_device_command",
                                 deviceId="ACT-1", command="unlock")]},
            {"content": "Critical device needs separate verified approval."},
        ])
        try:
            res = await model.answer("Unlock Bench Panel", [], hub, 90)
        finally:
            await model.close()
        self.assertTrue(res["action_continuation_invoked"])
        self.assertFalse(res["tool_calls"][-1]["success"])
        self.assertIn("critical/ambiguous", res["tool_calls"][-1]["error"])
        self.assertEqual(hub.writes, [])

    async def test_unavailable_writer_is_not_used_as_fallback(self):
        hub = FakeMCP()
        model = Model(scripted_discovery() + [
            {"tool_calls": [call("hub_set_rule", operation="create")]},
            {"content": "No rule or command was executed."},
        ])
        try:
            res = await model.answer("Enable Bench Panel", [], hub, 90)
        finally:
            await model.close()
        self.assertFalse(res["tool_calls"][-1]["success"])
        self.assertIn("read-only", res["tool_calls"][-1]["error"])
        self.assertEqual(hub.writes, [])


class SelectionSafetyTests(unittest.TestCase):
    def test_imperative_vs_question_and_explicit_read_only(self):
        for q in ["Unblock a device", "Please turn on the light", "Enable radiator",
                  "Switch the desk lamp off"]:
            with self.subTest(q=q):
                self.assertTrue(is_explicit_device_action_request(q))
        for q in ["Can you unblock the device?", "Is the lamp on?",
                  "Unblock the device but do not change anything.",
                  "Enable the light, read-only investigation.",
                  "Explain how to unblock", "What if I unblock",
                  "Unblock without making changes.", None]:
            with self.subTest(q=q):
                self.assertFalse(is_explicit_device_action_request(q))
        self.assertTrue(is_redundant_action_confirmation_draft(
            "To enable this device, I will turn it on. Shall I proceed?"))
        self.assertFalse(is_redundant_action_confirmation_draft(
            "The device reports access allowed."))
        self.assertTrue(should_review_completion(
            "Unblock the relay", available_tools=True, already_reviewed=False,
            remaining_seconds=30,
            draft="I found the controller. Shall I proceed?"))
        self.assertIn("redundant", _SKILL.lower())

    def test_original_detail_and_single_device_command_required(self):
        original = {"name": "hub_get_device", "success": True,
                    "response": json.dumps(receipt({
                        "id": "ACT-1",
                        "capabilities": ["Switch"],
                        "commands": [{"name": "enable"}, {"name": "disable"}],
                    }))}
        args = {"deviceId": "ACT-1", "command": "enable"}
        self.assertTrue(continuation_command_advertised([original], args))
        self.assertFalse(continuation_command_advertised(
            [original], {"deviceId": "ACT-2", "command": "enable"}))
        self.assertFalse(continuation_command_advertised(
            [original], {"deviceId": "ACT-1", "command": "unknown"}))
        self.assertFalse(continuation_command_advertised(
            [original], {"commands": [args]}))
        self.assertFalse(continuation_command_advertised(
            [{**original, "success": False}], args))
        lock = {"name": "hub_get_device", "success": True,
                "response": json.dumps(receipt({
                    "id": "ACT-1", "capabilities": ["Lock"],
                    "commands": [{"name": "unlock"}],
                }))}
        self.assertFalse(continuation_command_advertised(
            [lock], {"deviceId": "ACT-1", "command": "unlock"}))


if __name__ == "__main__":
    unittest.main()

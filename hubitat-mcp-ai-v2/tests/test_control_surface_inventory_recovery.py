"""Unfiltered coverage recovery in the alpha.65 native action loop.

All devices, identifiers, commands and timestamps here are synthetic.
The client contributes exactly ONE read-only inventory source. The model
chooses the controller and native command; no live device is contacted.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent
from mcp import MCPError
from control_surface_recovery import (
    is_explicit_device_imperative, should_recover_inventory,
    BROAD_INVENTORY_RECOVERY_PROMPT,
)


def call(name, **arguments):
    return {"function": {"name": name, "arguments": arguments}}


def rpc(payload):
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


class SyntheticHub:
    def __init__(self, *, fail_broad=False):
        self.calls = []
        self.writes = []
        self.fail_broad = fail_broad
        self.catalog = [
            {"name": x, "inputSchema": {"type": "object"}}
            for x in ["hub_list_devices", "hub_get_device",
                      "hub_get_device_attribute", "hub_call_device_command"]
        ]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "hub_list_devices":
            if args.get("labelFilter"):
                return rpc({"devices": [{
                    "id": "SCREEN-17",
                    "label": "Demo Screen",
                    "driver": "Fictional Media",
                    "deviceNetworkId": "player-10.66.0.12",
                }], "count": 1, "unfilteredTotal": 93,
                            "labelFilter": args["labelFilter"]})
            if self.fail_broad:
                raise MCPError("Synthetic inventory read failed")
            return rpc({
                "devices": [
                    {"id": "SCREEN-17", "label": "Demo Screen",
                     "driver": "Fictional Media"},
                    {"id": "ACT-09", "label": "Restrict Media-Demo-Screen",
                     "driver": "Fictional Policy Switch",
                     "deviceNetworkId": "policy-10.66.0.12",
                     "currentStates": {"switch": "on"}},
                    {"id": "OTHER", "label": "Unrelated Switch",
                     "driver": "Fictional Switch"},
                ],
                "count": 3, "unfilteredTotal": 93,
                "format": args.get("format"),
            })
        if name == "hub_get_device":
            if args["deviceId"] == "SCREEN-17":
                return rpc({
                    "id": "SCREEN-17", "label": "Demo Screen",
                    "capabilities": ["MediaTransport", "NetworkDevice"],
                    "attributes": [{"name": "ipAddress", "value": "10.66.0.12"},
                                   {"name": "mute", "value": "unmuted"}],
                    "commands": [{"name": "mute"}, {"name": "stop"}],
                })
            if args["deviceId"] == "ACT-09":
                return rpc({
                    "id": "ACT-09", "label": "Restrict Media-Demo-Screen",
                    "capabilities": ["Switch"],
                    "attributes": [
                        {"name": "deviceIP", "value": "10.66.0.12"},
                        {"name": "internetAccess", "value": "allowed"},
                        {"name": "timedBlockMins",
                         "value": 2 if self.writes else 0},
                    ],
                    "commands": [
                        {"name": "blockInMinutes",
                         "arguments": [{"name": "Minutes", "type": "NUMBER"}]},
                        {"name": "blockInternet", "arguments": None},
                        {"name": "allowInternet", "arguments": None},
                    ],
                })
        if name == "hub_call_device_command":
            self.writes.append(dict(args))
            return rpc({"success": True, "deviceId": args["deviceId"],
                        "command": args["command"],
                        "timedBlockMins": 2})
        if name == "hub_get_device_attribute":
            return rpc({"deviceId": args.get("deviceId"),
                        "attribute": args.get("attribute"),
                        "value": 2 if self.writes else 0})
        raise AssertionError("Unexpected synthetic MCP call: " + name)


class ScriptedModel(Agent):
    def __init__(self, script):
        super().__init__("http://localhost:11434", "fixture", "", 10)
        self.script = list(script)
        self.offered_tools = []
        self.last_messages = []

    async def round(self, messages, tools, remaining):
        self.offered_tools.append([t["function"]["name"] for t in tools])
        self.last_messages.append(str(messages[-1].get("content") or ""))
        if not self.script:
            raise AssertionError("Unexpected extra model round")
        return self.script.pop(0)


def narrow_media_lookup():
    return [
        {"tool_calls": [call("hub_list_devices", labelFilter="Demo Screen")]},
        {"tool_calls": [call("hub_get_device", deviceId="SCREEN-17")]},
        {"content": (
            "The Demo Screen media integration has no network block command. "
            "I cannot block its internet after two minutes."
        )},
    ]


class ControllerCoverageRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_narrow_media_dead_end_recovers_broad_source_and_native_timer(self):
        hub = SyntheticHub()
        agent = ScriptedModel(narrow_media_lookup() + [
            {"tool_calls": [call("hub_get_device", deviceId="ACT-09")]},
            {"content": "The source-corroborated policy controller advertises a native delay.",
             "tool_calls": [call("hub_call_device_command",
                                 deviceId="ACT-09", command="blockInMinutes",
                                 parameters=["2"])]},
            {"content": (
                "The native command was submitted; verify the stored timer."
            )},
            {"tool_calls": [call("hub_get_device_attribute",
                                 deviceId="ACT-09", attribute="timedBlockMins")]},
            {"content": (
                "A native blockInMinutes(2) was accepted; the controller "
                "reports a two-minute pending block. Actual later policy "
                "enforcement has not yet been observed."
            )},
        ])
        try:
            res = await agent.answer("Block Demo Screen after 2 minutes", [], hub, 90)
        finally:
            await agent.close()
        self.assertTrue(res["success"])
        self.assertTrue(res["inventory_recovery_invoked"])
        self.assertEqual(res["inventory_recovery_status"], "source_returned")
        self.assertEqual(res["rounds"], 8)
        self.assertEqual([n for n, _ in hub.calls], [
            "hub_list_devices", "hub_get_device",
            "hub_list_devices", "hub_get_device",
            "hub_call_device_command", "hub_get_device_attribute",
        ])
        self.assertEqual(hub.calls[2][1], {"format": "context"})
        self.assertEqual(len(hub.writes), 1)
        self.assertEqual(hub.writes[0]["command"], "blockInMinutes")
        self.assertEqual(hub.writes[0]["parameters"], ["2"])
        self.assertEqual(res["source_review_kind"], "action_outcome")
        self.assertEqual(res["tool_calls"][2]["client_inventory_coverage_recovery"], True)
        self.assertEqual(res["tool_calls"][2]["arguments"], {"format": "context"})
        self.assertIn("Restrict Media-Demo-Screen", res["tool_calls"][2]["response"])
        self.assertIn("Original native MCP inventory response",
                      agent.last_messages[3])
        self.assertIn("Restrict Media-Demo-Screen", agent.last_messages[3])
        self.assertIn("hub_call_device_command", agent.offered_tools[4])
        self.assertNotIn("hub_call_device_command", agent.offered_tools[6])
        self.assertIn("not yet been observed", res["answer"])

    async def test_read_only_intent_does_not_broaden_or_write(self):
        for question in (
            "Can you block Demo Screen after 2 minutes?",
            "Block Demo Screen after 2 minutes; do not change anything.",
            "Block Demo Screen without making changes.",
            "Investigate whether blocking Demo Screen is possible.",
        ):
            with self.subTest(question=question):
                hub = SyntheticHub()
                agent = ScriptedModel(narrow_media_lookup())
                try:
                    res = await agent.answer(question, [], hub, 90)
                finally:
                    await agent.close()
                self.assertFalse(res["inventory_recovery_invoked"])
                self.assertEqual([n for n, _ in hub.calls], [
                    "hub_list_devices", "hub_get_device",
                ])
                self.assertEqual(hub.writes, [])

    async def test_inventory_source_error_is_reported_without_inventing_target(self):
        hub = SyntheticHub(fail_broad=True)
        agent = ScriptedModel(narrow_media_lookup() + [
            {"content": "Broad inventory unavailable. Another actuator remains unknown."},
        ])
        try:
            res = await agent.answer("Block Demo Screen after two minutes", [], hub, 90)
        finally:
            await agent.close()
        self.assertEqual(res["inventory_recovery_status"], "source_error")
        self.assertFalse(res["tool_calls"][2]["success"])
        self.assertEqual(res["tool_calls"][2]["name"], "hub_list_devices")
        self.assertIn("does not prove", agent.last_messages[3])
        self.assertEqual(hub.writes, [])

    async def test_existing_first_attempt_to_native_timer_is_not_replaced(self):
        hub = SyntheticHub()
        agent = ScriptedModel([
            {"tool_calls": [call("hub_get_device", deviceId="ACT-09")]},
            {"tool_calls": [call("hub_call_device_command",
                                 deviceId="ACT-09", command="blockInMinutes",
                                 parameters=["2"])]},
            {"content": "The native delay command was accepted."},
            {"content": "The native command was accepted; the physical later block is unknown."},
        ])
        try:
            res = await agent.answer("Block Demo Screen after 2 minutes", [], hub, 90)
        finally:
            await agent.close()
        self.assertFalse(res["inventory_recovery_invoked"])
        self.assertEqual(len(hub.writes), 1)
        self.assertEqual(res["source_review_kind"], "action_outcome")


class CoverageEligibilityTests(unittest.TestCase):
    def test_direct_action_and_filtered_inventory_only(self):
        yes = {"name": "hub_list_devices", "success": True,
               "arguments": {"labelFilter": "Demo Screen"}}
        broad = {"name": "hub_list_devices", "success": True,
                 "arguments": {"format": "context"}}
        kw = dict(available_tools={"hub_list_devices", "hub_get_device",
                                   "hub_call_device_command"},
                  already_recovered=False, remaining_seconds=45,
                  source_review_invoked=False, has_native_write_attempt=False)
        self.assertTrue(should_recover_inventory(
            "Block Demo Screen after two minutes", [yes], **kw))
        self.assertFalse(should_recover_inventory(
            "Block Demo Screen after two minutes", [yes, broad], **kw))
        self.assertFalse(should_recover_inventory(
            "Block Demo Screen after two minutes", [yes],
            **{**kw, "has_native_write_attempt": True}))
        self.assertFalse(should_recover_inventory(
            "Block Demo Screen after two minutes", [yes],
            **{**kw, "already_recovered": True}))
        self.assertFalse(should_recover_inventory(
            "Block Demo Screen after two minutes", [yes],
            **{**kw, "remaining_seconds": 5}))
        self.assertFalse(should_recover_inventory(
            "Block Demo Screen after two minutes", [yes],
            **{**kw, "available_tools": {"hub_get_device"}}))
        self.assertFalse(should_recover_inventory(
            "Block Demo Screen after two minutes", [yes],
            **{**kw, "source_review_invoked": True}))
        self.assertFalse(should_recover_inventory(
            "Block Demo Screen after two minutes", [
                {**yes, "success": False}], **kw))
        for q in ("Can you block Demo Screen?", "Please investigate this",
                  "Block Demo Screen; do not change anything.",
                  "Unblock Demo Screen read-only.",
                  "Block Demo Screen without making changes."):
            with self.subTest(q=q):
                self.assertFalse(is_explicit_device_imperative(q))
        self.assertTrue(is_explicit_device_imperative(
            "Please block Demo Screen after 2 minutes"))
        self.assertNotIn("Google", BROAD_INVENTORY_RECOVERY_PROMPT)
        self.assertNotIn("Cudy", BROAD_INVENTORY_RECOVERY_PROMPT)


if __name__ == "__main__":
    unittest.main()

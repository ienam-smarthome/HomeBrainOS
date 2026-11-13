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
    should_follow_through_device_action, DEVICE_ACTION_FOLLOW_THROUGH_PROMPT,
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

    async def test_plan_only_prior_receipts_trigger_fresh_native_action_path(self):
        hub = SyntheticHub()
        agent = ScriptedModel([
            {"content": (
                "Plan: hub_call_device_command(deviceId='ACT-09', "
                "command='blockInMinutes', parameters=['2']). "
                "I will schedule the action."
            )},
            {"tool_calls": [call("hub_get_device", deviceId="ACT-09")]},
            {"content": "Fresh source confirms the native two-minute delay.",
             "tool_calls": [call("hub_call_device_command",
                                 deviceId="ACT-09", command="blockInMinutes",
                                 parameters=["2"])]},
            {"content": "The native command was submitted. Verify its timer."},
            {"tool_calls": [call("hub_get_device_attribute",
                                 deviceId="ACT-09", attribute="timedBlockMins")]},
            {"content": (
                "The native command was accepted and the source returned "
                "timedBlockMins=2; future policy enforcement is unverified."
            )},
        ])
        try:
            res = await agent.answer(
                "Block Demo Screen after 2mins", [], hub, 90,
                prior_evidence="Archived receipt says fictional device ACT-09.",
                prior_receipts=8,
            )
        finally:
            await agent.close()
        self.assertEqual(res["prior_receipts_used"], 8)
        self.assertEqual(res["rounds"], 6)
        self.assertTrue(res["action_follow_through_invoked"])
        self.assertFalse(res["inventory_recovery_invoked"])
        self.assertEqual([n for n, _ in hub.calls], [
            "hub_get_device", "hub_call_device_command",
            "hub_get_device_attribute",
        ])
        self.assertEqual(hub.writes, [{
            "deviceId": "ACT-09", "command": "blockInMinutes",
            "parameters": ["2"],
        }])
        self.assertEqual(res["source_review_kind"], "action_outcome")
        self.assertEqual(agent.last_messages[0], "Block Demo Screen after 2mins")
        self.assertIn("Previous", agent.last_messages[1])
        self.assertIn("not a fresh native reading", agent.last_messages[1])
        self.assertNotIn("hub_call_device_command", agent.offered_tools[4])
        self.assertIn("future policy enforcement is unverified", res["answer"])

    async def test_plan_only_source_unavailable_does_not_fabricate_dispatch(self):
        hub = SyntheticHub()
        agent = ScriptedModel([
            {"content": "I will call the device command."},
            {"content": (
                "I have not read any live device details or sent any "
                "command in this request; the current outcome is unknown."
            )},
        ])
        try:
            res = await agent.answer(
                "Block Demo Screen after 2 minutes", [], hub, 90)
        finally:
            await agent.close()
        self.assertTrue(res["action_follow_through_invoked"])
        self.assertFalse(res["inventory_recovery_invoked"])
        self.assertEqual(hub.calls, [])
        self.assertEqual(res["rounds"], 2)
        self.assertIn("not read any live device", res["answer"])

    async def test_model_must_not_reverse_existing_state_to_manufacture_delay(self):
        class AlreadyBlockedHub(SyntheticHub):
            async def call(self, name, args):
                if name == "hub_get_device":
                    self.calls.append((name, dict(args)))
                    return rpc({
                        "id": "ACT-09",
                        "commands": [{"name": "blockInMinutes",
                                      "arguments": [{"name": "Minutes",
                                                     "type": "NUMBER"}]},
                                     {"name": "allowInternet"}],
                        "attributes": [
                            {"name": "internetAccess", "value": "blocked"},
                            {"name": "timedBlockAt", "value": "none"},
                        ],
                    })
                return await super().call(name, args)

        hub = AlreadyBlockedHub()
        agent = ScriptedModel([
            {"content": "Plan: schedule the native block after two minutes."},
            {"tool_calls": [call("hub_get_device", deviceId="ACT-09")]},
            {"content": (
                "The source currently reports blocked and no pending timer. "
                "I did not schedule a new transition or silently allow access "
                "to create one."
            )},
        ])
        try:
            res = await agent.answer(
                "Block Demo Screen after 2 minutes", [], hub, 90)
        finally:
            await agent.close()
        self.assertTrue(res["action_follow_through_invoked"])
        self.assertEqual(hub.writes, [])
        self.assertEqual(res["tool_calls"][0]["name"], "hub_get_device")
        self.assertIn("did not schedule", res["answer"])

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

    def test_no_source_plan_only_triggers_one_follow_through(self):
        from control_surface_recovery import (
            should_follow_through_device_action, DEVICE_ACTION_FOLLOW_THROUGH_PROMPT,
        )
        kw = dict(inventory_recovery_invoked=False, already_prompted=False,
                  remaining_seconds=60, source_review_invoked=False,
                  has_native_write_attempt=False, available_tools={
                      "hub_list_devices", "hub_get_device", "hub_call_device_command"
                  })
        self.assertTrue(should_follow_through_device_action(
            "Block Demo Screen after 2 mins", [], **kw))
        self.assertFalse(should_follow_through_device_action(
            "Block Demo Screen after 2 mins", [], **{**kw, "already_prompted": True}))
        self.assertFalse(should_follow_through_device_action(
            "Block Demo Screen after 2 mins", [], **{**kw, "remaining_seconds": 4}))
        self.assertFalse(should_follow_through_device_action(
            "Block Demo Screen after 2 mins", [], **{**kw,
                 "available_tools": {"hub_list_devices", "hub_get_device"}}))
        self.assertFalse(should_follow_through_device_action(
            "Can you block Demo Screen?", [], **kw))
        self.assertFalse(should_follow_through_device_action(
            "Block Demo Screen; do not change anything.", [], **kw))
        self.assertTrue(should_follow_through_device_action(
            "Block Demo Screen after 2 mins",
            [{"name": "hub_list_devices", "success": True,
              "client_inventory_coverage_recovery": True},
             {"name": "hub_get_device", "success": True}],
            **{**kw, "inventory_recovery_invoked": True}))
        self.assertIn('"after/in N minutes"', DEVICE_ACTION_FOLLOW_THROUGH_PROMPT)
        self.assertIn('"for N minutes"', DEVICE_ACTION_FOLLOW_THROUGH_PROMPT)
        self.assertNotIn("Google TV", DEVICE_ACTION_FOLLOW_THROUGH_PROMPT)



class ActionFollowThroughTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_delay_followthrough_after_model_asks_unneeded_clarification(self):
        hub = SyntheticHub()
        agent = ScriptedModel(narrow_media_lookup() + [
            {"tool_calls": [call("hub_get_device", deviceId="ACT-09")]},
            {"content": (
                "The source-reported controller has blockInMinutes, but do "
                "you mean block immediately FOR 2 minutes or AFTER 2 minutes?"
            )},
            {"content": "Issue the matching native two-minute delay.",
             "tool_calls": [call("hub_call_device_command",
                                 deviceId="ACT-09", command="blockInMinutes",
                                 parameters=["2"])]},
            {"content": "Native accepted; pending timer requires readback."},
            {"tool_calls": [call("hub_get_device_attribute",
                                 deviceId="ACT-09", attribute="timedBlockMins")]},
            {"content": (
                "The native controller accepted blockInMinutes(2), and "
                "the reported timer is two minutes. Physical later block "
                "is not independently verified."
            )},
        ])
        try:
            res = await agent.answer(
                "Block Demo Screen after 2 minutes", [], hub, 90
            )
        finally:
            await agent.close()
        self.assertTrue(res["action_follow_through_invoked"])
        self.assertTrue(res["inventory_recovery_invoked"])
        self.assertEqual(res["rounds"], 9)
        self.assertEqual(len(hub.writes), 1)
        self.assertEqual(hub.writes[0], {
            "deviceId": "ACT-09", "command": "blockInMinutes",
            "parameters": ["2"],
        })
        self.assertEqual([n for n, _ in hub.calls], [
            "hub_list_devices", "hub_get_device", "hub_list_devices",
            "hub_get_device", "hub_call_device_command",
            "hub_get_device_attribute",
        ])
        self.assertIn("Original user already gave a direct",
                      agent.last_messages[5])
        self.assertIn('"after/in N minutes"', agent.last_messages[5])
        self.assertIn("hub_call_device_command", agent.offered_tools[6])
        self.assertEqual(res["source_review_kind"], "action_outcome")
        self.assertNotIn("for two minutes?", res["answer"].lower())
        self.assertIn("not independently verified", res["answer"])

    async def test_preblocked_device_followthrough_does_not_automatically_allow(self):
        class PreblockedHub(SyntheticHub):
            async def call(self, name, args):
                if name == "hub_get_device" and args.get("deviceId") == "ACT-09":
                    self.calls.append((name, dict(args)))
                    return rpc({
                        "id": "ACT-09", "label": "Restrict Media-Demo-Screen",
                        "capabilities": ["Switch"],
                        "attributes": [
                            {"name": "deviceIP", "value": "10.66.0.12"},
                            {"name": "internetAccess", "value": "blocked"},
                            {"name": "timedBlockAt", "value": "none"},
                            {"name": "timedBlockMins", "value": 0},
                        ],
                        "commands": [
                            {"name": "blockInMinutes",
                             "arguments": [{"name": "Minutes", "type": "NUMBER"}]},
                            {"name": "allowForMinutes",
                             "arguments": [{"name": "Minutes", "type": "NUMBER"}]},
                        ],
                    })
                return await super().call(name, args)

        hub = PreblockedHub()
        agent = ScriptedModel(narrow_media_lookup() + [
            {"tool_calls": [call("hub_get_device", deviceId="ACT-09")]},
            {"content": (
                "I found the delayed-block command, but it is already blocked. "
                "Should I unblock it first so it can block again after 2 minutes?"
            )},
            {"content": (
                "The source currently reports blocked with no pending timer. "
                "I did not change policy. Restoring access for 2 minutes would "
                "be an additional state change needing explicit authorization."
            )},
        ])
        try:
            res = await agent.answer("Block Demo Screen after 2 minutes",
                                     [], hub, 90)
        finally:
            await agent.close()
        self.assertTrue(res["action_follow_through_invoked"])
        self.assertEqual(len(hub.writes), 0)
        self.assertEqual([n for n, _ in hub.calls], [
            "hub_list_devices", "hub_get_device", "hub_list_devices",
            "hub_get_device",
        ])
        self.assertEqual(res["source_review_invoked"], False)
        self.assertIn("no pending timer", res["answer"])
        self.assertIn("did not change policy", res["answer"])

    async def test_followthrough_not_repeated_when_model_still_declines(self):
        hub = SyntheticHub()
        agent = ScriptedModel(narrow_media_lookup() + [
            {"tool_calls": [call("hub_get_device", deviceId="ACT-09")]},
            {"content": "Can you clarify the intent?"},
            {"content": "The requested action was not performed."},
        ])
        try:
            res = await agent.answer("Block Demo Screen after 2 minutes",
                                     [], hub, 90)
        finally:
            await agent.close()
        self.assertTrue(res["action_follow_through_invoked"])
        self.assertEqual(res["rounds"], 6)
        self.assertEqual(hub.writes, [])
        self.assertEqual(len(agent.last_messages), 6)

    def test_followthrough_eligibility_and_safety_limits(self):
        narrow = {"name": "hub_list_devices", "success": True,
                  "arguments": {"labelFilter": "Demo Screen"}}
        broad = {"name": "hub_list_devices", "success": True,
                 "client_inventory_coverage_recovery": True,
                 "arguments": {"format": "context"}}
        detail = {"name": "hub_get_device", "success": True,
                  "arguments": {"deviceId": "ACT-09"}}
        kw = {
            "inventory_recovery_invoked": True, "already_prompted": False,
            "remaining_seconds": 35, "source_review_invoked": False,
            "has_native_write_attempt": False,
        }
        self.assertTrue(should_follow_through_device_action(
            "Block Demo Screen after 2 minutes", [narrow, broad, detail],
            **kw))
        for receipts, overrides in [
            ([narrow, broad], {}),
            ([narrow, broad, {**detail, "success": False}], {}),
            ([narrow, broad, detail], {"already_prompted": True}),
            ([narrow, broad, detail], {"source_review_invoked": True}),
            ([narrow, broad, detail], {"inventory_recovery_invoked": False}),
            ([narrow, broad, detail], {"has_native_write_attempt": True}),
            ([narrow, broad, detail], {"remaining_seconds": 5}),
        ]:
            with self.subTest(receipts=receipts, overrides=overrides):
                self.assertFalse(should_follow_through_device_action(
                    "Block Demo Screen after 2 minutes", receipts,
                    **{**kw, **overrides}))
        for question in (
            "Can you block Demo Screen after 2 minutes?",
            "Block Demo Screen after 2 minutes; do not change anything.",
            "Block Demo Screen without making changes",
        ):
            with self.subTest(question=question):
                self.assertFalse(should_follow_through_device_action(
                    question, [narrow, broad, detail], **kw))
        self.assertNotIn("Google", DEVICE_ACTION_FOLLOW_THROUGH_PROMPT)
        self.assertNotIn("Cudy", DEVICE_ACTION_FOLLOW_THROUGH_PROMPT)
        self.assertIn("ALREADY BLOCKED/OFF", DEVICE_ACTION_FOLLOW_THROUGH_PROMPT)


if __name__ == "__main__":
    unittest.main()

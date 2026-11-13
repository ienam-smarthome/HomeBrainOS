"""One-shot relative delay vs event-driven rule selection.

All devices and effects here are FICTIONAL. No live Hubitat/router calls.
Only the original model chooses any native command; the client prevents an
unauthorised automation trigger, not a user-approved recurring automation.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent
from action_intent_guard import (
    original_one_shot_delay, unrequested_rule_write_reason,
    rule_activation_outcome,
)
from control_surface_recovery import should_follow_through_device_action


def call(tool_name, **kwargs):
    return {"function": {"name": tool_name, "arguments": kwargs}}


def rpc(obj):
    return {"content": [{"type": "text", "text": json.dumps(obj)}]}


class SyntheticMCP:
    def __init__(self, rule_response=None):
        self.calls = []
        self.catalog = [
            {"name": n, "inputSchema": {"type": "object"}}
            for n in ("hub_list_devices", "hub_get_device",
                      "hub_call_device_command", "hub_get_device_attribute",
                      "hub_set_visual_rule", "hub_create_backup")
        ]
        self.rule_response = rule_response or {
            "success": True, "storedSuccessfully": True,
            "activated": True, "activatedSuccessfully": True,
            "appId": 98765, "validationErrors": [],
        }

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "hub_get_device":
            return rpc({
                "id": "BENCH-ACT-4",
                "label": "Demo Access Control",
                "capabilities": ["Switch"],
                "attributes": [
                    {"name": "internetAccess", "value": "allowed"},
                    {"name": "pendingTimerMinutes", "value": 0},
                ],
                "commands": [
                    {"name": "blockInMinutes",
                     "arguments": [{"name": "Minutes", "type": "NUMBER"}]},
                    {"name": "blockInternet", "arguments": None},
                ],
            })
        if name == "hub_list_devices":
            return rpc({"devices": [
                {"id": "BENCH-ACT-4", "label": "Demo Access Control"}
            ], "count": 1})
        if name == "hub_call_device_command":
            return rpc({"success": True, "command": args["command"],
                        "deviceId": args["deviceId"],
                        "scheduled": True})
        if name == "hub_get_device_attribute":
            return rpc({"deviceId": "BENCH-ACT-4", "attribute":
                        args.get("attribute", "pendingTimerMinutes"),
                        "value": 2})
        if name == "hub_set_visual_rule":
            return rpc(self.rule_response)
        if name == "hub_create_backup":
            return rpc({"success": True, "confirmed": True})
        raise AssertionError("unsupported synthetic MCP tool " + name)


class ScriptedAgent(Agent):
    def __init__(self, script):
        super().__init__("http://localhost:11434", "fixture", "", 10)
        self.script = list(script)
        self.incoming = []

    async def round(self, messages, tools, remaining):
        self.incoming.append((messages[-1].get("content", ""),
                              [x["function"]["name"] for x in tools]))
        if not self.script:
            raise AssertionError("Unexpected model round")
        return self.script.pop(0)


class OneShotIntentTests(unittest.TestCase):
    def test_concrete_relative_delay_without_event(self):
        for q in (
            "Block Demo Screen after 2 mins",
            "Please turn off Demo Lamp in 30 seconds",
            "Switch off Demo Heater in 2 hours",
            "Unblock Demo Access after 5 minutes",
        ):
            with self.subTest(q=q):
                self.assertEqual(original_one_shot_delay(q, []), q)
                self.assertIsNotNone(unrequested_rule_write_reason(
                    q, [], "hub_set_visual_rule", {
                        "confirm": True,
                        "definition": {"triggers": [
                            {"type": "systemMode", "config": {"modes": [33]}}
                        ]},
                    }))
        for q in (
            "When motion starts, block Demo Screen after 2 mins",
            "Create a rule to block Demo Screen after 2 mins",
            "Block Demo Screen whenever it turns on and stays on for 2 mins",
            "Block Demo Screen after 2 mins; do not change anything",
            "Can you block Demo Screen after 2 mins?",
        ):
            with self.subTest(q=q):
                self.assertIsNone(original_one_shot_delay(q, []))
                self.assertIsNone(unrequested_rule_write_reason(
                    q, [], "hub_set_visual_rule", {}))

    def test_simple_yes_does_not_authorize_invented_trigger(self):
        history = [
            {"role": "user", "content": "Block Demo Screen after 2 mins"},
            {"role": "assistant", "content": (
                "I can block it now, or create a rule. Which would you like?"
            )},
        ]
        self.assertEqual(original_one_shot_delay("yes", history),
                         "Block Demo Screen after 2 mins")
        self.assertIsNotNone(unrequested_rule_write_reason(
            "yes", history, "hub_set_visual_rule", {}))
        self.assertIsNotNone(unrequested_rule_write_reason(
            "yes", history, "hub_manage_rule_machine",
            {"tool": "hub_set_visual_rule", "args": {}}))
        self.assertIsNone(unrequested_rule_write_reason(
            "yes", history, "hub_call_device_command",
            {"command": "blockInMinutes"}))
        clear_history = [
            {"role": "user", "content": (
                "Create a rule that blocks Demo Screen when its switch "
                "turns on, after 2 minutes"
            )},
        ]
        self.assertIsNone(unrequested_rule_write_reason(
            "yes", clear_history, "hub_set_visual_rule", {}))

    def test_native_activated_and_stored_are_different_facts(self):
        value = rpc({
            "success": True, "appId": 98765,
            "storedSuccessfully": True,
            "activatedSuccessfully": False,
            "validationErrors": [
                "trigger config requires non-empty mode ids",
                "seconds cannot exceed 59",
            ],
        })
        state = rule_activation_outcome(value)
        self.assertEqual(state["stored"], True)
        self.assertEqual(state["activated"], False)
        self.assertEqual(len(state["validation_errors"]), 2)
        self.assertEqual(state["app_id"], 98765)
        self.assertIsNone(rule_activation_outcome(
            rpc({"success": True, "command": "blockInMinutes"})))

    def test_broad_inventory_without_details_gets_one_followthrough(self):
        kw = dict(
            inventory_recovery_invoked=True,
            already_prompted=False,
            remaining_seconds=40, source_review_invoked=False,
            has_native_write_attempt=False, available_tools={
                "hub_list_devices", "hub_get_device",
                "hub_call_device_command",
            },
        )
        result = [{"name": "hub_list_devices",
                   "client_inventory_coverage_recovery": True,
                   "success": True}]
        self.assertTrue(should_follow_through_device_action(
            "Block Demo Screen after 2 mins", result, **kw))
        self.assertFalse(should_follow_through_device_action(
            "Block Demo Screen after 2 mins", result,
            **{**kw, "already_prompted": True}))
        self.assertFalse(should_follow_through_device_action(
            "Block Demo Screen after 2 mins",
            [{**result[0], "success": False}], **kw))


class NativeTimerVsRuleTests(unittest.IsolatedAsyncioTestCase):
    async def test_rule_draft_rejected_before_approval_then_native_timer(self):
        hub = SyntheticMCP()
        model = ScriptedAgent([
            {"tool_calls": [call("hub_get_device", deviceId="BENCH-ACT-4")]},
            {"tool_calls": [call(
                "hub_set_visual_rule", confirm=True,
                name="Temporary Demo Block",
                definition={
                    "triggers": [{"type": "systemMode",
                                  "config": {"modes": [33]}}],
                    "thenActions": [
                        {"type": "wait", "config": {"minutes": 2}},
                        {"type": "turnOff",
                         "config": {"switches": ["BENCH-ACT-4"]}},
                    ],
                },
            )]},
            {"tool_calls": [call(
                "hub_call_device_command", deviceId="BENCH-ACT-4",
                command="blockInMinutes", parameters=["2"],
            )]},
            {"tool_calls": [call(
                "hub_get_device_attribute", deviceId="BENCH-ACT-4",
                attribute="pendingTimerMinutes",
            )]},
            {"content": "The native source reports a two-minute timer; "
                        "actual future blocking remains unverified."},
            {"content": "The native timer is scheduled per original source; "
                        "later enforcement remains unverified."},
        ])
        approvals = []
        async def before_call(name, args, draft):
            approvals.append(name)
        try:
            result = await model.answer(
                "Block Demo Screen after 2 mins", [], hub, 90,
                before_call=before_call,
            )
        finally:
            await model.close()
        self.assertEqual([n for n,_ in hub.calls], [
            "hub_get_device", "hub_call_device_command",
            "hub_get_device_attribute",
        ])
        self.assertEqual(approvals, [
            "hub_get_device", "hub_call_device_command",
            "hub_get_device_attribute",
        ])
        self.assertEqual(result["automation_intent_rejections"], 1)
        guard = result["tool_calls"][1]
        self.assertEqual(guard["result_kind"],
                         "unrequested_automation_preflight")
        self.assertFalse(guard["success"])
        self.assertFalse(guard["operation_executed"])
        self.assertIn("original user request did not specify",
                      guard["response"])
        self.assertEqual(result["source_review_kind"], "action_outcome")
        self.assertIn("later enforcement", result["answer"])

    async def test_yes_followup_cannot_create_ambiguous_mode_rule(self):
        hub = SyntheticMCP()
        model = ScriptedAgent([
            {"tool_calls": [call(
                "hub_set_visual_rule", name="Temporary Demo Block",
                confirm=True, definition={
                    "triggers": [{"type": "systemMode",
                                  "config": {"modes": [33]}}],
                    "thenActions": [{"type": "wait",
                                     "config": {"minutes": 2}}],
                },
            )]},
            {"content": (
                "No rule was created; the original user did not request "
                "a mode-change trigger."
            )},
        ])
        try:
            result = await model.answer(
                "yes", [
                    {"role": "user",
                     "content": "Block Demo Screen after 2 mins"},
                    {"role": "assistant",
                     "content": "Create a rule or block now?"},
                ], hub, 90,
            )
        finally:
            await model.close()
        self.assertEqual(hub.calls, [])
        self.assertEqual(result["automation_intent_rejections"], 1)
        self.assertEqual(result["tool_calls"][0]["result_kind"],
                         "unrequested_automation_preflight")
        self.assertIn("No rule was created", result["answer"])

    async def test_explicit_event_rule_is_not_blocked_by_intent_guard(self):
        hub = SyntheticMCP(rule_response={
            "success": True, "appId": 98765,
            "storedSuccessfully": True, "activatedSuccessfully": False,
            "validationErrors": ["event trigger missing"],
        })
        model = ScriptedAgent([
            {"tool_calls": [call(
                "hub_set_visual_rule", name="Demo Schedule",
                confirm=True, definition={
                    "triggers": [{"type": "switch",
                                  "config": {"switches": [999],
                                             "switchEvent": "Turns on"}}],
                    "thenActions": [{"type": "wait",
                                     "config": {"minutes": 2}}],
                },
            )]},
            {"content": "The rule was stored but native activation failed."},
            {"content": "The source says activated=false; no rule trigger fired."},
        ])
        try:
            result = await model.answer(
                "Create a rule to block Demo Screen when its switch turns "
                "on, after 2 mins", [], hub, 90,
            )
        finally:
            await model.close()
        self.assertEqual([n for n,_ in hub.calls],
                         ["hub_set_visual_rule"])
        self.assertEqual(result["automation_intent_rejections"], 0)
        receipt = result["tool_calls"][0]
        self.assertEqual(receipt["native_rule_outcome"]["activated"], False)
        self.assertEqual(receipt["native_rule_outcome"]["stored"], True)
        self.assertEqual(len(receipt["native_rule_outcome"]["validation_errors"]), 1)
        self.assertEqual(result["source_review_kind"], "action_outcome")


if __name__ == "__main__":
    unittest.main()

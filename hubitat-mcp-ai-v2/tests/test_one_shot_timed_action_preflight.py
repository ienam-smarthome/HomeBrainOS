"""One-shot relative delay vs event-driven rule selection.

All devices and effects here are FICTIONAL. No live Hubitat/router calls.
Only the original model chooses any native command; the client prevents an
unauthorised automation trigger, not a user-approved recurring automation.
"""
import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent
from action_intent_guard import (
    native_automation_writer, automation_write_requires_confirmation,
    rule_activation_outcome,
)
from interaction import Interaction
from mcp import MCPError
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


class StructuredAuthorizationTests(unittest.TestCase):
    def test_real_tool_or_gateway_leaf_not_prompt_controls_approval(self):
        for writer in ("hub_set_visual_rule", "hub_set_rule",
                       "hub_create_custom_rule", "hub_update_custom_rule",
                       "hub_set_native_app"):
            self.assertEqual(native_automation_writer(writer, {}), writer)
            self.assertTrue(automation_write_requires_confirmation(
                "hub_manage_rule_machine", {"tool": writer, "args": {}}
            ))
        self.assertFalse(automation_write_requires_confirmation(
            "hub_call_device_command", {"command": "blockInMinutes"}
        ))
        self.assertFalse(automation_write_requires_confirmation(
            "hub_manage_rule_machine", {"tool": "hub_list_rules", "args": {}}
        ))

    def test_native_stored_is_not_native_activated(self):
        status = rule_activation_outcome(rpc({
            "success": True, "storedSuccessfully": True,
            "activatedSuccessfully": False,
            "validationErrors": ["invalid trigger"]
        }))
        self.assertTrue(status["stored"])
        self.assertFalse(status["activated"])
        self.assertEqual(len(status["validation_errors"]), 1)

    def test_broad_inventory_followthrough_unchanged(self):
        kw = dict(inventory_recovery_invoked=True, already_prompted=False,
                  remaining_seconds=40, source_review_invoked=False,
                  has_native_write_attempt=False,
                  available_tools={"hub_list_devices", "hub_get_device",
                                   "hub_call_device_command"})
        self.assertTrue(should_follow_through_device_action(
            "Block Demo Screen after 2 mins",
            [{"name": "hub_list_devices",
              "client_inventory_coverage_recovery": True, "success": True}],
            **kw))


class NativeApprovalTests(unittest.IsolatedAsyncioTestCase):
    async def wait_for_approval(self, interaction):
        for _ in range(100):
            if interaction.pending:
                return interaction.pending
            await asyncio.sleep(0.01)
        self.fail("Expected a pending operation-specific approval")

    async def test_ui_approval_required_without_confirm_for_direct_and_gateway(self):
        for tool, args in (
            ("hub_set_visual_rule", {"definition": {"triggers": [
                {"type": "systemMode"}]}}),
            ("hub_manage_rule_machine", {"tool": "hub_set_visual_rule",
                                         "args": {"definition": {
                                             "triggers": [{"type": "systemMode"}]
                                         }}}),
        ):
            with self.subTest(tool=tool):
                interaction = Interaction()
                task = asyncio.create_task(interaction.before_call(
                    tool, args, "assistant plan"
                ))
                approval = await self.wait_for_approval(interaction)
                self.assertEqual(approval["approval_kind"], "automation_write")
                self.assertEqual(approval["arguments"], args)
                interaction.decide(approval["id"], False)
                with self.assertRaises(MCPError):
                    await task

    async def test_numeric_spelled_and_chat_yes_cannot_dispatch_a_oneoff_visual_rule(self):
        cases = [
            ("Block Demo Screen after 2 minutes", []),
            ("Block Demo Screen after two minutes", []),
            ("yes", [
                {"role": "user",
                 "content": "Block Demo Screen after two minutes"},
                {"role": "assistant",
                 "content": "Shall I create a mode-change rule instead?"}
            ]),
        ]
        for question, history in cases:
            with self.subTest(question=question):
                hub = SyntheticMCP()
                model = ScriptedAgent([
                    {"tool_calls": [call(
                        "hub_set_visual_rule", name="Unexpected Mode Rule",
                        definition={"triggers": [
                            {"type": "systemMode", "config": {"modes": [33]}}
                        ]}
                    )]},
                    {"content": "The proposed recurring rule was not sent."},
                ])
                interaction = Interaction()
                try:
                    result = await model.answer(
                        question, history, hub, 90,
                        before_call=interaction.before_call,
                        enable_action_proposal_review=False,
                    )
                finally:
                    await model.close()
                self.assertEqual(hub.calls, [])
                self.assertIsNone(interaction.pending)
                self.assertEqual(result["automation_confirmation_requests"], 0)
                self.assertEqual(result["one_off_rule_preflight_rejections"], 1)
                self.assertEqual(
                    result["tool_calls"][0]["result_kind"],
                    "one_off_rule_preflight_rejected"
                )

    async def test_approved_rule_dispatches_and_reports_native_flags(self):
        hub = SyntheticMCP(rule_response={
            "success": True, "storedSuccessfully": True,
            "activatedSuccessfully": False,
            "validationErrors": ["invalid trigger"],
        })
        model = ScriptedAgent([
            {"tool_calls": [call(
                "hub_set_visual_rule", name="Test Rule",
                definition={"triggers": [{"type": "switch",
                                         "config": {"switches": [999]}}]},
            )]},
            {"content": "Stored but not activated in source."},
            {"content": "No rule-trigger execution is established."},
        ])
        interaction = Interaction()
        task = asyncio.create_task(model.answer(
            "Create a rule when test switch turns on", [], hub, 90,
            before_call=interaction.before_call,
                    enable_action_proposal_review=False,
        ))
        try:
            pending = await self.wait_for_approval(interaction)
            interaction.decide(pending["id"], True)
            result = await task
        finally:
            await model.close()
        self.assertEqual([name for name, args in hub.calls],
                         ["hub_set_visual_rule"])
        receipt = result["tool_calls"][0]["native_rule_outcome"]
        self.assertEqual(receipt["stored"], True)
        self.assertEqual(receipt["activated"], False)

    async def test_no_ui_callback_fails_closed(self):
        hub = SyntheticMCP()
        model = ScriptedAgent([
            {"tool_calls": [call("hub_set_visual_rule",
                                 definition={"triggers": []})]},
            {"content": "Approval missing; nothing executed."},
        ])
        try:
            result = await model.answer("Create a native rule", [], hub, 90)
        finally:
            await model.close()
        self.assertEqual(hub.calls, [])
        self.assertEqual(result["tool_calls"][0]["result_kind"],
                         "native_automation_approval_not_completed")

    async def test_native_device_timer_path_needs_no_rule_approval(self):
        hub = SyntheticMCP()
        model = ScriptedAgent([
            {"tool_calls": [call(
                "hub_call_device_command", deviceId="BENCH-ACT-4",
                command="blockInMinutes", parameters=["2"],
            )]},
            {"content": "Native timer accepted; later effect not yet known."},
            {"content": "No physical future outcome established."},
        ])
        interaction = Interaction()
        try:
            result = await model.answer(
                "Block Demo Screen after two minutes", [], hub, 90,
                before_call=interaction.before_call,
                    enable_action_proposal_review=False,
            )
        finally:
            await model.close()
        self.assertIsNone(interaction.pending)
        self.assertEqual([n for n, args in hub.calls],
                         ["hub_call_device_command"])
        self.assertEqual(result["automation_confirmation_requests"], 0)


if __name__ == "__main__":
    unittest.main()

"""Agent-level one-off native Rule Machine integration, synthetic MCP only."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent
from one_off_rule_policy import OWNED


def mcp_value(data):
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


class Hub:
    def __init__(self):
        self.calls = []
        self.catalog = [{"name": n, "inputSchema": {"type": "object"}}
                        for n in ("hub_get_app_config", "hub_get_device",
                                  "hub_manage_rule_machine",
                                  "hub_set_visual_rule")]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_get_app_config":
            return mcp_value({"app": {
                "id": 169, "label": "Rule Machine",
                "appType": {"namespace": "hubitat",
                            "name": "Rule Machine"},
            }})
        if name == "hub_get_device":
            return mcp_value({
                "id": "8899", "label": "Fictional Switch",
                "commands": [{"name": "on"}, {"name": "off"}],
                "attributes": [{"name": "switch", "value": "on"}]
            })
        if name == "hub_manage_rule_machine":
            if args.get("tool") != "hub_set_rule":
                raise AssertionError("Unexpected native writer")
            return mcp_value({
                "success": True, "rule_id": 8853, "created": True,
                "note": "Native source accepted dated create; not fired",
            })
        if name == "hub_set_visual_rule":
            raise AssertionError("Recurring Visual Rule must not be dispatched")
        raise AssertionError(name)


class AgentScript(Agent):
    def __init__(self, script):
        super().__init__("http://localhost:11434", "fictional", "", 10)
        self.script = list(script)

    async def round(self, messages, tools, remaining):
        if not self.script:
            raise AssertionError("Unexpected model round")
        return self.script.pop(0)


def call(tool_name, **args):
    return {"tool_calls": [{"function": {"name": tool_name,
                                        "arguments": args}}]}


def dated_rule():
    return {
        "operation": "create",
        "args": {
            "parent_id": 169,
            "name": "HB one-shot | Fictional OFF (One-time 2099-11-13 18:50)",
            "changes": [
                {"part": "trigger", "value": {
                    "capability": "Certain Time (and optional date)",
                    "fields": [
                        {"name": "time#", "type": "enum",
                         "value": "A specific time"},
                        {"name": "atTime#", "type": "time",
                         "value": "2099-11-13T18:50:00.000+0000"},
                        {"name": "date#", "type": "bool", "value": True},
                        {"name": "atDate#", "type": "date",
                         "value": "2099-11-13"},
                    ]
                }},
                {"part": "action", "value": {
                    "type": "switchActs", "subtype": "getOnOffSwitch",
                    "fields": [
                        {"name": "onOffSwitch.#", "type": "capability.switch",
                         "value": ["8899"]},
                        {"name": "onOff.#", "type": "bool", "value": False},
                    ]
                }}
            ]
        }, "confirm": True
    }


class AgentLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_wrong_recurring_rule_is_never_sent_for_single_time(self):
        hub = Hub()
        model = AgentScript([
            call("hub_set_visual_rule", confirm=True,
                 name="Fictional Daily", definition={
                     "triggers": [{"type": "timeOfDay",
                                   "config": {"timeOfDay": "1850"}}],
                     "thenActions": [{"type": "turnOn",
                                      "config": {"switches": [8899]}}],
                 }),
            {"content": "Could not create a one-time rule without its native contract."},
        ])
        approvals = []
        async def approve(*args):
            approvals.append(args)
        try:
            response = await model.answer(
                "Turn off fictional device at 6:50pm", [], hub, 90,
                before_call=approve, enable_action_proposal_review=False,
                enable_source_review=False, enable_final_claim_audit=False,
            )
        finally:
            await model.close()
        self.assertEqual(hub.calls, [])
        self.assertEqual(approvals, [])
        self.assertEqual(response["one_off_rule_preflight_rejections"], 1)
        self.assertEqual(
            response["tool_calls"][0]["result_kind"],
            "one_off_rule_preflight_rejected"
        )

    async def test_dated_native_single_rule_reaches_normal_user_approval(self):
        hub = Hub()
        model = AgentScript([
            call("hub_get_app_config", appId=169),
            call("hub_get_device", deviceId="8899"),
            call("hub_manage_rule_machine",
                 tool="hub_set_rule", args=dated_rule()),
            {"content": "Native source accepted a dated one-off rule. Firing remains unverified."},
        ])
        approved = []
        async def approve(name, args, explanation):
            approved.append((name, args))
        try:
            response = await model.answer(
                "Turn fictional device off once at 6:50pm on 13 November 2099",
                [], hub, 90, before_call=approve,
                enable_action_proposal_review=False, enable_source_review=False,
                enable_final_claim_audit=False,
            )
        finally:
            await model.close()
        self.assertEqual(response["one_off_rule_preflight_rejections"], 0)
        self.assertEqual([name for name, _ in hub.calls],
                         ["hub_get_app_config", "hub_get_device",
                          "hub_manage_rule_machine"])
        self.assertEqual(response["automation_confirmation_requests"], 1)
        self.assertEqual(approved[-1][0], "hub_manage_rule_machine")
        self.assertEqual(approved[-1][1]["tool"], "hub_set_rule")


if __name__ == "__main__":
    unittest.main()

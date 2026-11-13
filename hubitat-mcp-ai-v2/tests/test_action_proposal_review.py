"""Model-led action-proposal reconsideration across fictional control domains.

These are scripted contracts, NOT independent evidence that a cloud model
will select the correct actuator or that a future physical action occurred.
No real Hubitat commands, devices or router traffic.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent
from action_proposal_review import (
    PREWRITE_PROPOSAL_PROMPT, has_current_native_evidence,
    is_native_action_proposal, is_persistent_construct,
)


def tool(name, **kwargs):
    return {"tool_calls": [{"function": {"name": name, "arguments": kwargs}}]}


def receipt(value):
    return {"content": [{"type": "text", "text": json.dumps(value)}]}


class FictionalHub:
    def __init__(self):
        self.calls = []
        self.catalog = [
            {"name": name, "inputSchema": {"type": "object"}}
            for name in (
                "hub_list_devices", "hub_get_device", "hub_get_device_attribute",
                "hub_call_device_command", "hub_set_visual_rule",
                "hub_get_tool_guide",
            )
        ]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "hub_list_devices":
            if args.get("labelFilter"):
                return receipt({"devices": [
                    {"id": "TEST-MEDIA", "label": "Demo Screen Media"},
                    {"id": "TEST-PLAYER", "label": "Demo Screen Player"},
                ], "count": 2, "unfilteredTotal": 3})
            return receipt({"devices": [
                {"id": "TEST-MEDIA", "label": "Demo Screen Media"},
                {"id": "TEST-PLAYER", "label": "Demo Screen Player"},
                {"id": "TEST-NET", "label": "Fictional Policy Controller"},
            ], "count": 3})
        if name == "hub_get_device":
            if args.get("deviceId") == "TEST-MEDIA":
                return receipt({
                    "id": "TEST-MEDIA", "label": "Demo Screen Media",
                    "driver": "Media Transport",
                    "attributes": [{"name": "networkStatus", "value": "online"}],
                    "commands": [{"name": "off"}, {"name": "on"}],
                })
            return receipt({
                "id": "TEST-NET", "label": "Fictional Policy Controller",
                "attributes": [{"name": "accessPolicy", "value": "allowed"}],
                "commands": [
                    {"name": "deferDisconnect",
                     "arguments": [{"name": "minutes", "type": "NUMBER"}]},
                    {"name": "allowConnection"},
                ],
            })
        if name == "hub_call_device_command":
            return receipt({
                "success": True, "deviceId": args["deviceId"],
                "command": args["command"],
                "scheduled": True, "pendingUntil": "2026-11-13T16:42:00Z",
            })
        if name == "hub_get_device_attribute":
            return receipt({
                "deviceId": args.get("deviceId"),
                "attribute": args.get("attribute"),
                "value": "2026-11-13T16:42:00Z",
            })
        if name == "hub_set_visual_rule":
            return receipt({
                "success": True, "storedSuccessfully": True,
                "activatedSuccessfully": True, "validationErrors": [],
                "appId": 30001,
            })
        if name == "hub_get_tool_guide":
            return receipt({"success": True, "section": "rules"})
        raise AssertionError("Unexpected native tool: " + name)


class ScriptedAgent(Agent):
    def __init__(self, script):
        super().__init__("http://localhost:11434", "fiction", "", 10)
        self.script = list(script)
        self.inputs = []

    async def round(self, messages, tools, remaining):
        self.inputs.append(messages[-1].get("content", ""))
        if not self.script:
            raise AssertionError("Unexpected extra model round")
        return self.script.pop(0)


class NativeProposalContractTests(unittest.TestCase):
    def test_selected_mutating_tool_and_gateway_leaf_not_question_text(self):
        catalog = [{"name": "hub_manage_devices",
                    "annotations": {"readOnlyHint": False}}]
        self.assertTrue(is_native_action_proposal(
            "hub_manage_devices", {"tool": "hub_call_device_command"},
            catalog))
        self.assertFalse(is_native_action_proposal(
            "hub_manage_devices", {"tool": "hub_get_device"}, catalog))
        self.assertTrue(is_native_action_proposal(
            "hub_set_visual_rule", {"definition": {}}, []))
        self.assertFalse(is_native_action_proposal(
            "hub_get_device", {"deviceId": 42}, []))
        self.assertTrue(is_persistent_construct(
            "hub_manage_virtual_device", {"action": "create"}))
        self.assertFalse(is_persistent_construct(
            "hub_call_device_command", {"command": "deferDisconnect"}))

    def test_guide_and_prior_receipts_are_not_live_target_state(self):
        self.assertFalse(has_current_native_evidence([
            {"name": "hub_get_tool_guide", "success": True},
            {"name": "homebrain_read_prior_evidence", "success": True},
            {"name": "hub_get_device", "success": False},
        ]))
        self.assertTrue(has_current_native_evidence([
            {"name": "hub_list_devices", "success": True}
        ]))
        self.assertIn("ONE-OFF", PREWRITE_PROPOSAL_PROMPT)
        self.assertNotIn("Google TV", PREWRITE_PROPOSAL_PROMPT)


class ProposalLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_reconsiders_wrong_media_target_before_dispatch(self):
        hub = FictionalHub()
        assistant = ScriptedAgent([
            tool("hub_list_devices", labelFilter="Demo Screen"),
            tool("hub_get_device", deviceId="TEST-MEDIA"),
            # Model's initial WRONG media action is unexecuted, and the
            # model chooses more source evidence in the reflection.
            tool("hub_call_device_command", deviceId="TEST-MEDIA",
                 command="off"),
            tool("hub_list_devices", format="context"),
            tool("hub_get_device", deviceId="TEST-NET"),
            tool("hub_call_device_command", deviceId="TEST-NET",
                 command="deferDisconnect", parameters=["2"]),
            tool("hub_get_device_attribute", deviceId="TEST-NET",
                 attribute="pendingUntil"),
            {"content": "Native controller reported a pending deadline; execution later is unverified."},
            {"content": "Controller accepted a delayed request; later physical outcome remains unknown."},
        ])
        approvals = []

        async def permit(name, args, explanation):
            approvals.append(name)

        try:
            result = await assistant.answer(
                "Restrict Demo Screen access after two minutes", [], hub, 90,
                before_call=permit,
            )
        finally:
            await assistant.close()
        self.assertTrue(result["prewrite_model_review_invoked"])
        self.assertTrue(any("Proposed but NOT executed" in item
                            for item in assistant.inputs))
        sent = [(n, a.get("deviceId"), a.get("command")) for n, a in hub.calls]
        self.assertNotIn(("hub_call_device_command", "TEST-MEDIA", "off"), sent)
        self.assertIn(("hub_call_device_command", "TEST-NET",
                       "deferDisconnect"), sent)
        self.assertEqual(approvals.count("hub_call_device_command"), 1)
        self.assertEqual(result["prewrite_no_fresh_evidence_rejections"], 0)
        self.assertIn("later physical outcome", result["answer"])

    async def test_no_new_persistent_rule_from_old_chat_only(self):
        hub = FictionalHub()
        assistant = ScriptedAgent([
            tool("hub_set_visual_rule", name="Fictional Rule",
                 confirm=True, definition={"triggers": []}),
            # Checkpoint invoked, then model stubbornly repeats an
            # unsupported persistent write: MUST fail locally, no UI.
            tool("hub_set_visual_rule", name="Fictional Rule",
                 confirm=True, definition={"triggers": []}),
            tool("hub_get_device", deviceId="TEST-NET"),
            tool("hub_call_device_command", deviceId="TEST-NET",
                 command="deferDisconnect", parameters=["2"]),
            tool("hub_get_device_attribute", deviceId="TEST-NET",
                 attribute="pendingUntil"),
            {"content": "Native deadline reported, later execution unverified."},
            {"content": "Native acceptance is not future physical proof."},
        ])
        approvals = []

        async def permit(name, args, explanation):
            approvals.append(name)

        try:
            result = await assistant.answer(
                "Schedule a fictional access restriction in two minutes",
                [], hub, 90, before_call=permit,
                prior_receipts=4, prior_evidence="Older read is not current",
            )
        finally:
            await assistant.close()
        self.assertEqual(result["prewrite_no_fresh_evidence_rejections"], 1)
        self.assertNotIn("hub_set_visual_rule", [n for n, a in hub.calls])
        self.assertNotIn("hub_set_visual_rule", approvals)
        self.assertEqual(result["tool_calls"][0]["result_kind"],
                         "persistent_write_missing_current_evidence")
        self.assertFalse(result["tool_calls"][0]["operation_executed"])
        self.assertEqual([n for n, a in hub.calls], [
            "hub_get_device", "hub_call_device_command",
            "hub_get_device_attribute",
        ])

    async def test_genuine_event_rule_after_read_still_uses_normal_approval(self):
        hub = FictionalHub()
        proposal = tool("hub_set_visual_rule", name="Fictional Event Rule",
                        confirm=True, definition={"triggers": [
                            {"type": "switch", "config": {"switches": [1234]}}
                        ]})
        assistant = ScriptedAgent([
            tool("hub_get_device", deviceId="TEST-NET"),
            proposal,
            proposal,
            {"content": "The native rule is stored and active; no trigger execution is confirmed."},
            {"content": "Storage and activation are not trigger execution."},
        ])
        approvals = []

        async def permit(name, args, explanation):
            approvals.append((name, args))

        try:
            result = await assistant.answer(
                "Create an event rule when the fictional test switch turns on",
                [], hub, 90, before_call=permit,
            )
        finally:
            await assistant.close()
        self.assertTrue(result["prewrite_model_review_invoked"])
        self.assertEqual(result["prewrite_no_fresh_evidence_rejections"], 0)
        self.assertEqual([n for n, a in hub.calls],
                         ["hub_get_device", "hub_set_visual_rule"])
        self.assertEqual(len(approvals), 2)  # read + separately approved write
        self.assertTrue(result["tool_calls"][1]["native_rule_outcome"]["activated"])


if __name__ == "__main__":
    unittest.main()

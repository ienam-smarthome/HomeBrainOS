"""Action-goal completion: the original imperative, not draft wording, governs review.

Fictional devices and scripted model decisions only. No real MCP server,
household target, network side effect, background scheduler or implicit write.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent
from investigation_review import (
    ACTION_GOAL_REVIEW_PROMPT, is_explicit_device_action_request,
    is_redundant_action_confirmation_draft, review_prompt,
    should_review_completion, continuation_command_advertised,
)


def tc(name, **args):
    return {"function": {"name": name, "arguments": args}}


def rpc(data):
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


class LabHub:
    def __init__(self, *, writer=True, initial_state="denied"):
        self.calls = []
        self.writes = []
        self.initial_state = initial_state
        self.catalog = [
            {"name": n, "inputSchema": {"type": "object"}} for n in
            ("hub_list_devices", "hub_get_device", "hub_get_device_attribute")
        ]
        if writer:
            self.catalog.append({
                "name": "hub_call_device_command",
                "inputSchema": {"type": "object"},
            })

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        self.calls.append((name, dict(args)))
        media = {
            "id": "LAB-PLAYER", "label": "Fictional Screen",
            "physicalRef": "physical-lab-a",
        }
        access = {
            "id": "LAB-NET", "label": "Access Gateway",
            "physicalRef": "physical-lab-a",
        }
        if name == "hub_list_devices":
            if args.get("labelFilter"):
                return rpc({"devices": [media], "count": 1, "total": 1,
                            "unfilteredTotal": 3, "labelFilter": "Fictional Screen"})
            return rpc({"devices": [media, access], "count": 2,
                        "total": 2, "unfilteredTotal": 3})
        if name == "hub_get_device":
            if args.get("deviceId") == "LAB-PLAYER":
                return rpc({**media, "capabilities": ["MediaTransport"],
                            "commands": [{"name": "play"},
                                         {"name": "unmute"}],
                            "attributes": [{"name": "networkStatus",
                                            "value": "online"},
                                           {"name": "mute",
                                            "value": "unmuted"}]})
            if args.get("deviceId") == "LAB-NET":
                return rpc({**access, "capabilities": ["Switch"],
                            "commands": [{"name": "allowAccess"},
                                         {"name": "denyAccess"}],
                            "attributes": [{"name": "access",
                                            "value": self.current_state}]})
        if name == "hub_call_device_command":
            self.writes.append(dict(args))
            return rpc({"success": True, "command": args.get("command"),
                        "deviceId": args.get("deviceId")})
        if name == "hub_get_device_attribute":
            return rpc({"deviceId": "LAB-NET", "attribute": "access",
                        "value": self.current_state})
        raise AssertionError("No unsupported synthetic command: " + name)

    @property
    def current_state(self):
        return "allowed" if self.writes else self.initial_state


class ScriptedModel(Agent):
    def __init__(self, script):
        super().__init__("http://localhost:11434", "fixture", "", 10)
        self.script = list(script)
        self.messages_seen = []
        self.offered_tools = []

    async def round(self, messages, tools, remaining):
        self.messages_seen.append(str(messages[-1].get("content", "")))
        self.offered_tools.append([t["function"]["name"] for t in tools])
        if not self.script:
            raise AssertionError("Script exhausted: extra model round")
        return self.script.pop(0)


def initial_ambiguous_media_read():
    return [
        {"tool_calls": [tc("hub_list_devices",
                           labelFilter="Fictional Screen")]},
        {"tool_calls": [tc("hub_get_device", deviceId="LAB-PLAYER")]},
        {"content": (
            "Fictional Screen is online and unmuted. Could you clarify "
            "whether you want audio unmuted or a network policy changed?"
        )},
    ]


class ActionGoalEndToEnd(unittest.IsolatedAsyncioTestCase):
    async def test_clarification_after_media_read_triggers_discovery_and_one_write(self):
        hub = LabHub()
        model = ScriptedModel(initial_ambiguous_media_read() + [
            {"tool_calls": [tc("hub_list_devices", format="context")]},
            {"tool_calls": [tc("hub_get_device", deviceId="LAB-NET")]},
            {"content": (
                "The second native record shares a source-reported physicalRef; "
                "the Access Gateway advertises allowAccess and currently denies access. "
                "The requested action has not been executed yet."
            )},
            {"tool_calls": [tc("hub_get_device", deviceId="LAB-NET")]},
            {"content": "The matched controller advertises allowAccess.",
             "tool_calls": [tc("hub_call_device_command",
                               deviceId="LAB-NET", command="allowAccess")]},
            {"tool_calls": [tc("hub_get_device_attribute",
                               deviceId="LAB-NET", attribute="access")]},
            {"content": (
                "The native command was submitted and accepted; a later native "
                "read reports the access attribute allowed. Independent network "
                "connectivity is unverified."
            )},
        ])
        try:
            result = await model.answer("Unblock Fictional Screen", [], hub, 90)
        finally:
            await model.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["source_review_kind"], "action_goal")
        self.assertTrue(result["source_review_invoked"])
        self.assertTrue(result["action_continuation_invoked"])
        self.assertTrue(result["action_continuation_write_attempted"])
        self.assertEqual(result["final_claim_audit_status"],
                         "not_applicable_to_action_goal_review")
        self.assertEqual(result["rounds"], 10)
        self.assertEqual([n for n, _ in hub.calls], [
            "hub_list_devices", "hub_get_device", "hub_list_devices",
            "hub_get_device", "hub_get_device", "hub_call_device_command",
            "hub_get_device_attribute",
        ])
        self.assertEqual(hub.writes, [
            {"deviceId": "LAB-NET", "command": "allowAccess"}
        ])
        self.assertIn("Action-goal evidence sufficiency",
                      model.messages_seen[3])
        self.assertNotIn("hub_call_device_command", model.offered_tools[3])
        self.assertIn("hub_call_device_command", model.offered_tools[6])
        self.assertNotIn("hub_call_device_command", model.offered_tools[8])
        self.assertFalse(is_redundant_action_confirmation_draft(
            initial_ambiguous_media_read()[-1]["content"]))
        self.assertIn("unverified", result["answer"])

    async def test_draft_claims_completed_but_without_receipt_still_gets_review(self):
        hub = LabHub(writer=False)
        model = ScriptedModel([
            {"tool_calls": [tc("hub_get_device", deviceId="LAB-PLAYER")]},
            {"content": "Done. The requested access was restored."},
            {"content": ("Correction: no native write receipt exists. "
                         "This media device does not verify network access.")},
        ])
        try:
            result = await model.answer("Unblock Fictional Screen", [], hub, 90)
        finally:
            await model.close()
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(result["source_review_kind"], "action_goal")
        self.assertFalse(result["action_continuation_invoked"])
        self.assertEqual(len(hub.writes), 0)
        self.assertEqual(result["rounds"], 3)
        self.assertIn("no native write receipt", result["answer"])

    async def test_unknown_controller_only_means_ask_after_review_not_guess(self):
        hub = LabHub()
        model = ScriptedModel(initial_ambiguous_media_read() + [
            {"content": (
                "The returned media record does not establish the real "
                "network-control actuator. Another source could resolve it."
            )},
            {"content": (
                "Physical target-to-controller identity was not established. "
                "I will not guess or issue an access command."
            )},
        ])
        try:
            result = await model.answer("Unblock Fictional Screen", [], hub, 90)
        finally:
            await model.close()
        self.assertTrue(result["action_continuation_invoked"])
        self.assertFalse(result["action_continuation_write_attempted"])
        self.assertEqual(len(hub.writes), 0)

    async def test_media_command_before_new_detail_cannot_be_late_executed(self):
        hub = LabHub()
        model = ScriptedModel(initial_ambiguous_media_read() + [
            {"tool_calls": [tc("hub_list_devices", format="context")]},
            {"content": "Controller requires further detail."},
            {"tool_calls": [tc("hub_call_device_command",
                               deviceId="LAB-PLAYER", command="unmute")]},
            {"content": "The missing fresh command-detail requirement denied this action."},
        ])
        try:
            result = await model.answer("Unblock Fictional Screen", [], hub, 90)
        finally:
            await model.close()
        self.assertTrue(result["action_continuation_invoked"])
        self.assertTrue(result["action_continuation_write_attempted"])
        self.assertEqual(hub.writes, [])
        self.assertFalse(result["tool_calls"][-1]["success"])
        self.assertIn("requires a successful hub_get_device",
                      result["tool_calls"][-1]["error"])

    async def test_capability_question_and_read_only_imperative_do_not_widen(self):
        for question in (
            "Can you unblock Fictional Screen?",
            "Unblock Fictional Screen; do not change anything.",
            "Unblock Fictional Screen without making changes.",
        ):
            with self.subTest(question=question):
                hub = LabHub()
                model = ScriptedModel(initial_ambiguous_media_read())
                try:
                    result = await model.answer(question, [], hub, 90)
                finally:
                    await model.close()
                self.assertFalse(result["action_continuation_invoked"])
                self.assertEqual(hub.writes, [])

    async def test_no_second_action_after_first_refusal(self):
        hub = LabHub()
        model = ScriptedModel([
            {"content": "I am going to attempt the requested operation.",
             "tool_calls": [tc("hub_call_device_command",
                               deviceId="LAB-NET", command="allowAccess")]},
            {"content": "The command was submitted. No second action is warranted."},
            {"content": "The command result is the only action receipt; no retry was attempted."},
        ])
        try:
            result = await model.answer("Unblock Fictional Screen", [], hub, 90)
        finally:
            await model.close()
        self.assertFalse(result["action_continuation_invoked"])
        self.assertEqual(len(hub.writes), 1)


class ActionGoalTriggerTests(unittest.TestCase):
    def test_direct_imperative_without_action_checks_goal_not_draft(self):
        self.assertTrue(is_explicit_device_action_request(
            "Unblock Fictional Screen"))
        for draft in (
            "Please clarify: sound or network?",
            "The device is online.",
            "Done. Access granted.",
            "I don't know which controller handles the effect.",
        ):
            with self.subTest(draft=draft):
                self.assertTrue(should_review_completion(
                    "Unblock Fictional Screen", available_tools=True,
                    already_reviewed=False, remaining_seconds=30,
                    action_attempted=False, has_action_receipt=False,
                    draft=draft))
        self.assertFalse(should_review_completion(
            "Unblock Fictional Screen", available_tools=True,
            already_reviewed=False, remaining_seconds=30,
            action_attempted=True, draft="I could not send the command."))
        self.assertFalse(should_review_completion(
            "Unblock Fictional Screen", available_tools=True,
            already_reviewed=False, remaining_seconds=4,
            action_attempted=False, draft="Please clarify."))
        self.assertFalse(should_review_completion(
            "Unblock Fictional Screen", available_tools=False,
            already_reviewed=False, remaining_seconds=30,
            action_attempted=False, draft="Please clarify."))
        self.assertFalse(should_review_completion(
            "Can you unblock Fictional Screen?", available_tools=True,
            already_reviewed=False, remaining_seconds=30,
            draft="The device is online."))
        self.assertFalse(should_review_completion(
            "Unblock Fictional Screen; do not change anything.",
            available_tools=True, already_reviewed=False, remaining_seconds=30,
            draft="The device is online."))
        self.assertEqual(review_prompt("action_goal"), ACTION_GOAL_REVIEW_PROMPT)
        self.assertNotIn("Nest Hub", ACTION_GOAL_REVIEW_PROMPT)
        self.assertNotIn("6992", ACTION_GOAL_REVIEW_PROMPT)


if __name__ == "__main__":
    unittest.main()

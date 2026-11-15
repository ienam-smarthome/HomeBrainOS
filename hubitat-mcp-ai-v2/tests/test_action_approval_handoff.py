"""V2 prose-only action confirmation → native UI approval handoff.

Fictional MCP/model only. This checks the lifecycle contract and UI safety;
it cannot prove a deployed model will select a real target or command.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from interaction import Interaction
from control_surface_recovery import (
    ACTION_APPROVAL_HANDOFF_PROMPT, prose_only_action_confirmation,
    should_recover_action_approval_handoff,
    draft_has_source_backed_native_command,
)

QUESTION = "Restrict Fictional TV internet access after ten minutes"


def tool(name, args):
    return {"tool_calls": [{"function": {"name": name, "arguments": args}}]}


def response(payload):
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


class FictionalMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": name, "inputSchema": {"type": "object"}}
            for name in ("hub_list_devices", "hub_get_device",
                         "hub_create_variable", "hub_call_device_command")
        ]

    async def call(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "hub_list_devices":
            return response({"devices": [{"id": "101",
                                         "label": "Fictional Policy TV"}],
                             "total": 1, "count": 1})
        if name == "hub_get_device":
            return response({
                "id": "101", "label": "Fictional Policy TV",
                "driver": "Fictional Policy Driver",
                "attributes": [{"name": "access", "value": "allowed"},
                               {"name": "timedActionAt", "value": "none"}],
                "commands": [{"name": "disconnectInMinutes",
                              "arguments": [{"name": "minutes",
                                             "type": "NUMBER"}]}],
            })
        if name == "hub_call_device_command":
            return response({"deviceId": "101",
                             "scheduled": True,
                             "acceptedCommand": args.get("command")})
        raise AssertionError("Unexpected native write: " + name)


class ScriptedModel(Agent):
    def __init__(self, script):
        super().__init__("http://127.0.0.1:11434", "synthetic", "", 20)
        self.script = list(script)
        self.seen = []
        self.offered = []

    async def round(self, messages, tools, remaining):
        self.seen.append(messages[-1].get("content", ""))
        self.offered.append([t["function"]["name"] for t in tools])
        if not self.script:
            raise AssertionError("Unexpected extra model round")
        return self.script.pop(0)


def source_reads():
    return [
        tool("hub_list_devices", {}),
        tool("hub_get_device", {"deviceId": "101", "mode": "summary"}),
        tool("hub_create_variable", {"name": "fictional_helper",
                                     "type": "Boolean", "value": "false",
                                     "confirm": True}),
    ]


class ApprovalRecoveryDecisionTests(unittest.TestCase):
    def test_text_confirmation_is_not_tool_approval(self):
        self.assertTrue(prose_only_action_confirmation(
            QUESTION, "Please confirm you'd like me to proceed."))
        self.assertTrue(prose_only_action_confirmation(
            QUESTION, "Once you confirm, I will execute the command."))
        self.assertFalse(prose_only_action_confirmation(
            QUESTION, "Action scheduled and confirmed by native receipt."))
        self.assertFalse(prose_only_action_confirmation(
            "Check TV status. Do not change anything.",
            "Please confirm you'd like me to proceed."))
        self.assertIn("NOT queue", ACTION_APPROVAL_HANDOFF_PROMPT)
        self.assertIn("explicit UI approval", ACTION_APPROVAL_HANDOFF_PROMPT)

    def test_required_receipts_and_authorization_boundaries(self):
        supported = {"hub_get_device", "hub_list_devices",
                     "hub_call_device_command"}
        good = {
            "name": "hub_get_device",
            "arguments": {"deviceId": "101", "mode": "summary"},
            "success": True,
            "result_kind": "tool_result",
            "response": json.dumps(response({
                "id": "101", "commands": [{"name": "disconnectInMinutes"}]})),
        }
        kwargs = {
            "available_tools": supported, "already_prompted": False,
            "has_native_write_attempt": False, "remaining_seconds": 60,
            "ui_approval_available": True, "source_review_invoked": False,
        }
        draft = "Please confirm before I proceed."
        self.assertTrue(should_recover_action_approval_handoff(
            QUESTION, draft, [good], **kwargs))
        bad = [
            dict(good, success=False),
            dict(good, response=json.dumps(response({
                "id": "999", "commands": [{"name": "disconnectInMinutes"}]}))),
            dict(good, response=json.dumps(response({
                "id": "101", "commands": []}))),
            dict(good, response="{broken"),
        ]
        for item in bad:
            with self.subTest(item=item):
                self.assertFalse(should_recover_action_approval_handoff(
                    QUESTION, draft, [item], **kwargs))
        for change in (
            {"ui_approval_available": False}, {"already_prompted": True},
            {"has_native_write_attempt": True}, {"remaining_seconds": 3},
            {"source_review_invoked": True},
            {"available_tools": {"hub_get_device"}},
        ):
            with self.subTest(change=change):
                self.assertFalse(should_recover_action_approval_handoff(
                    QUESTION, draft, [good], **{**kwargs, **change}))


class ApprovalRecoveryLifecycleTests(unittest.IsolatedAsyncioTestCase):

    async def test_fresh_source_backed_prose_skips_broad_and_queues_real_approval(self):
        """A model's source-grounded first plan needs no 200-device restart."""
        hub = FictionalMCP()
        model = ScriptedModel([
            tool("hub_list_devices", {"labelFilter": "Fictional TV"}),
            tool("hub_get_device", {"deviceId": "101", "mode": "summary"}),
            # First model proposal is a bad helper: prewrite must hold it.
            tool("hub_create_variable", {
                "name": "fictional_helper", "type": "Boolean",
                "value": "false", "confirm": True,
            }),
            {"content": (
                "Proposed native command: hub_call_device_command("
                "deviceId='101', command='disconnectInMinutes', "
                "parameters=[10]). Please confirm before I proceed."
            )},
            tool("hub_call_device_command", {
                "deviceId": "101", "command": "disconnectInMinutes",
                "parameters": [10],
            }),
            {"content": (
                "Native MCP accepted the delayed request. "
                "No future disconnection has been observed."
            )},
        ])
        gate = Interaction(require_native_write_approval=True)
        task = asyncio.create_task(model.answer(
            QUESTION, [], hub, 60, before_call=gate.before_call,
            enable_source_review=False, enable_final_claim_audit=False,
        ))
        try:
            for _ in range(200):
                if gate.pending is not None or task.done():
                    break
                await asyncio.sleep(0.01)
            self.assertIsNotNone(gate.pending)
            self.assertFalse(task.done())
            self.assertEqual(
                gate.pending["preview"]["verb"], "disconnectInMinutes")
            self.assertEqual(
                gate.pending["preview"]["fields"]["parameters"], "10")
            self.assertNotIn("hub_call_device_command",
                             [n for n, _ in hub.calls])
            gate.decide(gate.pending["id"], True)
            result = await asyncio.wait_for(task, 4)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            await model.close()
        self.assertTrue(result["success"])
        self.assertTrue(result["prewrite_model_review_invoked"])
        self.assertTrue(result["action_approval_handoff_invoked"])
        self.assertFalse(result["inventory_recovery_invoked"])
        self.assertFalse(result["action_follow_through_invoked"])
        self.assertEqual(result["rounds"], 6)
        self.assertEqual(len(hub.calls), 3)
        self.assertEqual([n for n, _ in hub.calls], [
            "hub_list_devices", "hub_get_device", "hub_call_device_command"
        ])
        self.assertTrue(result["prewrite_dispatch_changed"])
        self.assertEqual(
            result["action_source_sufficiency"], "not_established"
        )  # Final answer doesn't need to quote command syntax.

    async def test_source_backed_draft_refusal_gets_choices_without_broad_read(self):
        hub = FictionalMCP()
        draft = (
            "I plan hub_call_device_command("
            "deviceId=101, command=\"disconnectInMinutes\", parameters=[10])."
        )
        model = ScriptedModel([
            tool("hub_list_devices", {"labelFilter": "Fictional TV"}),
            tool("hub_get_device", {"deviceId": "101", "mode": "summary"}),
            {"content": draft},
            {"content": draft},
        ])
        gate = Interaction(require_native_write_approval=True)
        try:
            result = await model.answer(
                QUESTION, [], hub, 60, before_call=gate.before_call,
                enable_source_review=False, enable_final_claim_audit=False,
            )
        finally:
            await model.close()
        self.assertFalse(result["inventory_recovery_invoked"])
        self.assertTrue(result["action_approval_handoff_invoked"])
        self.assertEqual(result["rounds"], 4)
        self.assertEqual(result["action_selection"]["status"],
                         "unprepared_confirmation")
        self.assertEqual(result["action_source_sufficiency"],
                         "model_draft_matched_fresh_native_command")
        self.assertEqual(len(hub.calls), 2)
        self.assertIsNone(gate.pending)


    async def test_delay_output_is_source_grounded_after_real_ui_approval(self):
        """Model's final 'for N' must not erase actual delayed-onset command."""
        class AcceptedTimedHub(FictionalMCP):
            async def call(self, name, args):
                if name == "hub_call_device_command":
                    self.calls.append((name, dict(args)))
                    return response({
                        "success": True,
                        "device": "Fictional Policy TV",
                        "command": args["command"],
                        "parameters": [5],
                        "state": {
                            "pendingActionAt": {
                                "value": "2026-11-15 12:05:00",
                                "timestamp": "2026-11-15 12:00:00",
                            },
                        },
                    })
                return await super().call(name, args)

        hub = AcceptedTimedHub()
        model = ScriptedModel([
            tool("hub_list_devices", {}),
            tool("hub_get_device", {"deviceId": "101", "mode": "summary"}),
            tool("hub_call_device_command", {
                "deviceId": "101", "command": "disconnectInMinutes",
                "parameters": ["5"],
            }),  # Unsent prewrite draft: still requires reconsideration.
            {"content": "Please confirm before I proceed."},
            tool("hub_call_device_command", {
                "deviceId": "101", "command": "disconnectInMinutes",
                "parameters": ["5"],
            }),
            {"content": (
                "Fictional TV is blocked for 5 minutes; it will "
                "automatically reconnect at the end of that window."
            )},
            {"content": (
                "The device will definitely restore after five minutes."
            )},
        ])
        gate = Interaction(require_native_write_approval=True)
        task = asyncio.create_task(model.answer(
            "Disconnect Fictional TV after 5 minutes", [], hub, 60,
            before_call=gate.before_call, enable_source_review=True,
            enable_final_claim_audit=False,
        ))
        try:
            for _ in range(250):
                if gate.pending is not None or task.done():
                    break
                await asyncio.sleep(0.01)
            self.assertIsNotNone(gate.pending)
            preview = gate.pending["preview"]
            self.assertEqual(preview["fields"]["device"], "Fictional Policy TV")
            self.assertEqual(preview["fields"]["device_id"], "101")
            self.assertEqual(preview["fields"]["parameters"], "5")
            self.assertIn("After 5 minutes", preview["fields"]["timing"])
            self.assertFalse(task.done())
            self.assertNotIn("hub_call_device_command",
                             [name for name, _ in hub.calls])
            gate.decide(gate.pending["id"], True)
            result = await asyncio.wait_for(task, 4)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            await model.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"], 7)
        self.assertEqual(result["prewrite_unsent_proposals"][0]["name"],
                         "hub_call_device_command")
        self.assertTrue(result["source_review_invoked"])
        self.assertTrue(result["action_approval_handoff_invoked"])
        self.assertEqual(
            result["action_semantics_verification"]["status"],
            "source_derived_native_acceptance")
        self.assertIn("after 5 minutes", result["answer"])
        self.assertIn("pendingActionAt = 2026-11-15 12:05:00",
                      result["answer"])
        self.assertNotIn("will definitely restore", result["answer"])
        self.assertEqual(
            [name for name, _ in hub.calls].count("hub_call_device_command"), 1)
        self.assertFalse(result["action_semantics_verification"]["independent_readback"])

    async def test_native_action_handoff_waits_for_ui_approval(self):
        hub = FictionalMCP()
        model = ScriptedModel(source_reads() + [
            {"content": "Please confirm you'd like me to proceed."},
            tool("hub_call_device_command",
                 {"deviceId": "101", "command": "disconnectInMinutes",
                  "parameters": [10]}),
            {"content": "Native call accepted the future request; later effect unverified."},
        ])
        interaction = Interaction(require_native_write_approval=True)
        task = asyncio.create_task(model.answer(
            QUESTION, [], hub, 60,
            before_call=interaction.before_call,
            enable_source_review=False,
            enable_final_claim_audit=False,
        ))
        try:
            for _ in range(200):
                if interaction.pending or task.done():
                    break
                await asyncio.sleep(0.01)
            self.assertIsNotNone(interaction.pending, "Must show a native approval card")
            self.assertFalse(task.done(), "No write can execute before UI approval")
            self.assertEqual(interaction.pending["preview"]["device"], "101") if (
                "device" in interaction.pending["preview"]
            ) else None
            self.assertEqual(
                interaction.pending["preview"]["verb"], "disconnectInMinutes")
            self.assertNotIn(
                "hub_call_device_command", [name for name, _ in hub.calls],
                "Write must not execute on text confirmation")
            interaction.decide(interaction.pending["id"], True)
            result = await asyncio.wait_for(task, 4)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            await model.close()
        self.assertTrue(result["success"])
        self.assertTrue(result["prewrite_model_review_invoked"])
        self.assertEqual(result["prewrite_unsent_proposals"][0]["name"],
                         "hub_create_variable")
        self.assertTrue(result["action_approval_handoff_invoked"])
        self.assertEqual(result["action_approval_handoff_status"],
                         "native_write_selected")
        self.assertIsNone(result["action_selection"])
        self.assertEqual(len(model.seen), 6)
        self.assertIn("Native write approval handoff", model.seen[4])
        self.assertEqual([x for x in hub.calls if x[0] == "hub_call_device_command"],
                         [("hub_call_device_command", {
                             "deviceId": "101", "command": "disconnectInMinutes",
                             "parameters": [10]
                         })])

    async def test_model_still_refuses_without_queued_action(self):
        hub = FictionalMCP()
        model = ScriptedModel(source_reads() + [
            {"content": "Please confirm you'd like me to proceed."},
            {"content": "Once you confirm I can send the command."},
        ])
        interaction = Interaction(require_native_write_approval=True)
        try:
            result = await model.answer(
                QUESTION, [], hub, 60, before_call=interaction.before_call,
                enable_source_review=False, enable_final_claim_audit=False,
            )
        finally:
            await model.close()
        self.assertTrue(result["action_approval_handoff_invoked"])
        self.assertEqual(result["action_approval_handoff_status"],
                         "still_no_native_write")
        self.assertEqual(result["rounds"], 5)
        self.assertEqual(result["action_selection"]["status"],
                         "unprepared_confirmation")
        self.assertEqual(result["action_selection"]["options"],
                         ["prepare_action", "edit_request", "dismiss"])
        self.assertFalse(result["action_selection"]["native_write_queued"])
        self.assertIsNone(interaction.pending)
        self.assertNotIn("hub_create_variable", [x[0] for x in hub.calls])
        self.assertNotIn("hub_call_device_command", [x[0] for x in hub.calls])

    async def test_no_write_mode_never_produces_ui_authority(self):
        hub = FictionalMCP()
        model = ScriptedModel([
            tool("hub_get_device", {"deviceId": "101"}),
            {"content": "Please confirm you'd like me to proceed."},
        ])
        try:
            result = await model.answer(
                QUESTION, [], hub, 60, before_call=None,
                enable_source_review=False, enable_final_claim_audit=False,
            )
        finally:
            await model.close()
        self.assertFalse(result["action_approval_handoff_invoked"])
        self.assertIsNone(result["action_selection"])
        self.assertEqual(len(hub.calls), 1)


if __name__ == "__main__":
    unittest.main()

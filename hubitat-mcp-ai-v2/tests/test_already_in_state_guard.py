"""A plain on/off command is not sent when this request's own read already shows that state."""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from action_proposal_review import already_in_state_refusal  # noqa: E402
from agent import Agent  # noqa: E402
from interaction import Interaction  # noqa: E402


def read_receipt(state, device_id="7829", activity="2026-11-26T14:28:42+0000"):
    doc = {"devices": [{"id": device_id, "label": "Fictional Lamp",
                        "lastActivity": activity,
                        "currentStates": {"switch": state, "level": "60"}}], "count": 1}
    return {"name": "hub_read_devices", "success": True, "result_kind": "tool_result",
            "arguments": {"tool": "hub_list_devices", "args": {}},
            "response": json.dumps({"content": [{"type": "text", "text": json.dumps(doc)}]})}


def write_receipt(command, device_id="7829"):
    return {"name": "hub_manage_devices", "success": True, "result_kind": "tool_result",
            "possible_native_action": True,
            "arguments": {"tool": "hub_call_device_command",
                          "args": {"deviceId": device_id, "command": command}},
            "response": "{}"}


def gateway(command, device_id="7829", **extra):
    return "hub_manage_devices", {"tool": "hub_call_device_command",
                                  "args": {"deviceId": device_id, "command": command, **extra}}


class RefusalRule(unittest.TestCase):
    def test_on_when_the_read_says_on_is_refused_with_evidence(self):
        refusal = already_in_state_refusal(*gateway("on"), [read_receipt("on")])
        self.assertIsNotNone(refusal)
        message, info = refusal
        self.assertIn("NOT sent", message)
        self.assertEqual(info, {"device_id": "7829", "command": "on", "observed_switch": "on",
                                "last_activity": "2026-11-26T14:28:42+0000"})

    def test_opposite_state_is_not_refused(self):
        self.assertIsNone(already_in_state_refusal(*gateway("on"), [read_receipt("off")]))

    def test_no_read_means_no_refusal(self):
        self.assertIsNone(already_in_state_refusal(*gateway("on"), []))

    def test_other_device_read_does_not_count(self):
        self.assertIsNone(already_in_state_refusal(
            *gateway("on"), [read_receipt("on", device_id="1")]))

    def test_later_accepted_write_makes_the_read_stale(self):
        self.assertIsNone(already_in_state_refusal(
            *gateway("on"), [read_receipt("on"), write_receipt("off")]))

    def test_batch_parameters_and_other_commands_are_left_alone(self):
        for name, args in (
            gateway("on", parameters=[50]),
            gateway("setLevel"),
            ("hub_manage_devices", {"tool": "hub_call_device_command",
                                    "args": {"commands": [{"deviceId": "7829", "command": "on"}]}}),
            ("hub_manage_devices", {"tool": "hub_set_mode", "args": {"mode": "on"}}),
        ):
            self.assertIsNone(already_in_state_refusal(name, args, [read_receipt("on")]))

    def test_refused_once_then_an_identical_resend_is_the_models_choice(self):
        first = already_in_state_refusal(*gateway("on"), [read_receipt("on")])
        refused_row = {"name": "hub_manage_devices", "success": False,
                       "arguments": gateway("on")[1], "error": first[0][:240]}
        self.assertIsNone(already_in_state_refusal(
            *gateway("on"), [read_receipt("on"), refused_row]))

    def test_context_listing_state_counts(self):
        summary = ("Mode: Day\nDevices: 1 of 1\n- Fictional Lamp (7829, Hallway) - Switch, "
                   "Light; switch=on, level=60")
        doc = {"mode": "Day", "summary": summary, "count": 1, "total": 1}
        receipt = {"name": "hub_read_devices", "success": True, "result_kind": "tool_result",
                   "arguments": {}, "response": json.dumps(
                       {"content": [{"type": "text", "text": json.dumps(doc)}]})}
        refusal = already_in_state_refusal(*gateway("on"), [receipt])
        self.assertIsNotNone(refusal)
        self.assertIsNone(refusal[1]["last_activity"])


class Hub:
    def __init__(self, state):
        self.state = state
        self.calls = []
        self.catalog = [
            {"name": "hub_read_devices", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "hub_manage_devices", "inputSchema": {"type": "object", "properties": {}}},
        ]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_read_devices":
            doc = {"devices": [{"id": "7829", "label": "Fictional Lamp", "room": "Hallway",
                                "lastActivity": "2026-11-26T14:28:42+0000",
                                "currentStates": {"switch": self.state, "level": "60"}}],
                   "count": 1, "total": 1}
        else:
            doc = {"success": True, "device": "Fictional Lamp", "command": args["args"]["command"]}
        return {"content": [{"type": "text", "text": json.dumps(doc)}]}


class Scripted(Agent):
    def __init__(self, script):
        super().__init__("http://127.0.0.1:11434", "fixture", "", 15)
        self.script = list(script)

    async def round(self, messages, tools, remaining):
        return self.script.pop(0)


def call(name, args):
    return {"function": {"name": name, "arguments": args}}


READ = call("hub_read_devices", {"tool": "hub_list_devices", "args": {"labelFilter": "Fictional Lamp"}})
ON = call("hub_manage_devices", {"tool": "hub_call_device_command",
                                 "args": {"deviceId": "7829", "command": "on"}})


class AgentLoop(unittest.IsolatedAsyncioTestCase):
    async def _run(self, state, script):
        hub = Hub(state)
        agent = Scripted(script)
        gate = Interaction(require_native_write_approval=True)
        task = asyncio.create_task(agent.answer(
            "Turn on fictional lamp", [], hub, 60, before_call=gate.before_call))
        try:
            for _ in range(1500):
                if gate.pending or task.done():
                    break
                await asyncio.sleep(0.002)
            pending = gate.pending
            if pending:
                gate.decide(pending["id"], True)
            result = await asyncio.wait_for(task, 5)
        finally:
            if not task.done():
                gate.invalidate()
                task.cancel()
            await agent.close()
        return hub, pending, result

    async def test_already_on_sends_nothing_shows_no_card_and_keeps_the_answer(self):
        answer = "Fictional Lamp is already on according to the hub (since 14:28:42). Nothing was sent."
        hub, pending, result = await self._run("on", [
            {"content": "", "tool_calls": [READ]},
            {"content": "", "tool_calls": [ON]},
            {"content": answer, "tool_calls": []},
        ])
        self.assertIsNone(pending)
        self.assertNotIn("hub_manage_devices", [n for n, _ in hub.calls])
        self.assertEqual(result["action_lifecycle"]["status"], "already_in_requested_state")
        self.assertIn("already on", result["answer"])
        self.assertNotIn("No action queued", result["answer"])

    async def test_off_state_still_goes_through_approval_and_dispatch(self):
        hub, pending, result = await self._run("off", [
            {"content": "", "tool_calls": [READ]},
            {"content": "", "tool_calls": [ON]},
            {"content": "", "tool_calls": [ON]},
            {"content": "Done.", "tool_calls": []},
            {"content": "Done.", "tool_calls": []},
            {"content": "Done.", "tool_calls": []},
        ])
        self.assertIsNotNone(pending)
        self.assertEqual([n for n, _ in hub.calls].count("hub_manage_devices"), 1)


if __name__ == "__main__":
    unittest.main()

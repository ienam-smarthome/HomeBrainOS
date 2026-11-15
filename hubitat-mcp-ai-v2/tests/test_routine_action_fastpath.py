"""V2 routine-action fast-path proof, approval and fail-closed fixtures.

Fictional local MCP and scripted inference only: NO external model, Hubitat,
real devices, or real native writes. No physical-outcome acceptance is implied.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from interaction import Interaction
from routine_action_fastpath import routine_candidate, accepted_routine_answer


def mcp_result(document):
    return {"content": [{"type": "text", "text": json.dumps(document)}]}


def previous_receipt(name, arguments, original, success=True):
    return {
        "name": name, "arguments": arguments, "success": success,
        "result_kind": "tool_result",
        "response": json.dumps(mcp_result(original)),
    }


def device(label="Fictional Office Lamp", switch="on"):
    return {
        "id": "LAB-LAMP-1", "name": "Laboratory Dimmer",
        "label": label, "capabilities": ["Actuator", "Switch", "Light"],
        "attributes": [{"name": "switch", "value": switch},
                       {"name": "level", "value": 80}],
        "commands": [{"name": "off", "arguments": None},
                     {"name": "on", "arguments": None}],
    }


def proposal(command="off", identifier="LAB-LAMP-1", **kwargs):
    return {"function": {
        "name": "hub_call_device_command",
        "arguments": {"deviceId": identifier, "command": command, **kwargs}
    }}


def eligible(question="turn off Fictional Office Lamp", *, original=None):
    return routine_candidate(
        question, [proposal()],
        [previous_receipt("hub_get_device", {"deviceId": "LAB-LAMP-1"},
                          original or device())],
        approval_available=True,
    )


def native_write(success=True, command="off", identifier="LAB-LAMP-1"):
    return {
        **previous_receipt(
            "hub_call_device_command",
            {"deviceId": identifier, "command": command},
            {"success": success, "deviceId": identifier, "command": command,
             "parameters": None, "state": {"switch": {"value": "on"}}},
        ),
        "possible_native_action": True,
    }


class RoutineEligibilityTests(unittest.TestCase):
    def test_source_verified_exact_simple_switch_action_only(self):
        found = eligible()
        self.assertIsNotNone(found)
        self.assertEqual(found["device_id"], "LAB-LAMP-1")
        self.assertEqual(found["label"], "Fictional Office Lamp")
        self.assertEqual(found["command"], "off")
        self.assertIsNotNone(eligible("Switch off the fictional office lamp"))
        self.assertIsNotNone(eligible("Please turn off Fictional Office Lamp."))

    def test_no_scheduling_multi_action_or_side_effect_semantics(self):
        for q in (
            "turn off Fictional Office Lamp after 5 minutes",
            "turn off Fictional Office Lamp for 5 minutes",
            "turn off Fictional Office Lamp and Bedroom Light",
            "turn off Fictional Office Lamp, then turn off the heater",
            "block internet for Fictional Office Lamp",
            "turn off Fictional Office Lamp. Do not change anything",
            "turn off Fictional Office Lamp\nread-only evidence",
            "turn off Fictional Office Lamp?",
            "make Fictional Office Lamp off",
        ):
            with self.subTest(question=q):
                self.assertIsNone(eligible(q))

    def test_no_guesses_from_wrong_id_label_capability_state_or_source(self):
        source = device()
        for value in (
            {**source, "label": "Fictional Office Lamp Alternate"},
            {**source, "id": "LAB-LAMP-2"},
            {**source, "capabilities": ["SwitchLevel"]},
            {**source, "attributes": []},
            {**source, "attributes": [{"name": "switch", "value": "off"}]},
            {**source, "commands": [{"name": "off", "arguments": [1]}]},
        ):
            with self.subTest(value=value):
                self.assertIsNone(eligible(original=value))
        self.assertIsNone(eligible("Turn on Fictional Office Lamp"))
        self.assertIsNone(routine_candidate(
            "Turn off Fictional Office Lamp", [proposal()],
            [], approval_available=True,
        ))
        self.assertIsNone(routine_candidate(
            "Turn off Fictional Office Lamp", [proposal()],
            [previous_receipt("hub_get_device", {"deviceId": "LAB-LAMP-1"},
                              source, success=False)],
            approval_available=True,
        ))
        self.assertIsNone(routine_candidate(
            "Turn off Fictional Office Lamp", [proposal()],
            [previous_receipt("hub_get_device", {"deviceId": "LAB-LAMP-1"},
                              source),
             previous_receipt("hub_get_device", {"deviceId": "LAB-LAMP-2"},
                              source)],
            approval_available=True,
        ))
        self.assertIsNone(routine_candidate(
            "Turn off Fictional Office Lamp", [proposal()],
            [previous_receipt("hub_get_device", {"deviceId": "LAB-LAMP-1"},
                              source)], approval_available=False,
        ))

    def test_wrong_arguments_multiple_operations_and_unrelated_sources(self):
        detail = previous_receipt("hub_get_device",
                                  {"deviceId": "LAB-LAMP-1"}, device())
        for calls in (
            [proposal(), proposal()],
            [proposal(parameters=[1])],
            [proposal(confirm=True)],
            [proposal(identifier="WRONG")],
            [proposal(command="on")],
            [{"function": {"name": "hub_set_visual_rule",
                           "arguments": {"name": "unrelated"}}}],
        ):
            with self.subTest(calls=calls):
                self.assertIsNone(routine_candidate(
                    "turn off Fictional Office Lamp", calls, [detail],
                    approval_available=True,
                ))
        self.assertIsNone(routine_candidate(
            "turn off Fictional Office Lamp", [proposal()],
            [detail, previous_receipt("hub_get_rule",
                                      {"id": 123}, {"rules": []})],
            approval_available=True,
        ))

    def test_native_receipt_acceptance_and_negative_receipt_scope(self):
        match = eligible()
        answer = accepted_routine_answer(match, [native_write()])
        self.assertIn("Fictional Office Lamp: OFF command accepted", answer)
        self.assertIn("not been independently verified", answer)
        self.assertIsNone(accepted_routine_answer(match, [native_write(False)]))
        self.assertIsNone(accepted_routine_answer(match, [native_write(identifier="LAB-LAMP-2")]))
        self.assertIsNone(accepted_routine_answer(match, [native_write(command="on")]))
        self.assertIsNone(accepted_routine_answer(match, [native_write(), native_write()]))
        no_write_doc = native_write()
        no_write_doc["response"] = json.dumps(mcp_result(
            {"success": True, "command": "wrong", "deviceId": "LAB-LAMP-1"}))
        self.assertIsNone(accepted_routine_answer(match, [no_write_doc]))


class FictionalHub:
    def __init__(self):
        self.calls = []
        self.catalog = [{
            "name": n, "inputSchema": {"type": "object"},
        } for n in ("hub_list_devices", "hub_get_device",
                    "hub_call_device_command")]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, arguments):
        self.calls.append((name, deepcopy(arguments)))
        if name == "hub_list_devices":
            return mcp_result({
                "devices": [{"id": "LAB-LAMP-1",
                             "label": "Fictional Office Lamp"}],
                "count": 1,
            })
        if name == "hub_get_device":
            return mcp_result(device())
        if name == "hub_call_device_command":
            return mcp_result({
                "success": True,
                "deviceId": arguments["deviceId"],
                "command": arguments["command"], "parameters": None,
                "state": {"switch": {"value": "on"}},  # write snapshot, NOT readback
            })
        raise AssertionError("Unapproved or invented native tool: " + name)


class ScriptedAgent(Agent):
    def __init__(self, script):
        super().__init__("http://127.0.0.1:11434", "fiction", "", 10)
        self.script = list(script)
        self.rounds_seen = 0

    async def round(self, messages, tools, remaining):
        self.rounds_seen += 1
        if not self.script:
            raise AssertionError("Unexpected extra AI model round")
        return self.script.pop(0)


def tool(name, **args):
    return {"tool_calls": [{
        "function": {"name": name, "arguments": args}
    }]}


class RoutineLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_selects_and_real_approval_required_before_dispatch(self):
        hub = FictionalHub()
        model = ScriptedAgent([
            tool("hub_list_devices", labelFilter="Fictional Office Lamp",
                 format="summary"),
            tool("hub_get_device", deviceId="LAB-LAMP-1"),
            tool("hub_call_device_command", deviceId="LAB-LAMP-1",
                 command="off"),
        ])
        gate = Interaction(require_native_write_approval=True)
        task = asyncio.create_task(model.answer(
            "Turn off Fictional Office Lamp", [], hub, 60,
            before_call=gate.before_call,
        ))
        try:
            for _ in range(1000):
                if gate.pending:
                    break
                if task.done():
                    break
                await asyncio.sleep(0.002)
            self.assertIsNotNone(gate.pending, "Real native approval is required")
            self.assertNotIn("hub_call_device_command", [
                n for n, _ in hub.calls
            ], "No write may cross transport before approval")
            gate.decide(gate.pending["id"], True)
            result = await asyncio.wait_for(task, 5)
        finally:
            if not task.done():
                gate.invalidate()
                task.cancel()
            await model.close()
        self.assertEqual([n for n, _ in hub.calls], [
            "hub_list_devices", "hub_get_device", "hub_call_device_command",
        ])
        self.assertEqual(model.rounds_seen, 3)
        self.assertEqual(result["rounds"], 3)
        self.assertFalse(result["prewrite_model_review_invoked"])
        self.assertFalse(result["source_review_invoked"])
        self.assertTrue(result["routine_action_fastpath"]["prewrite_model_review_skipped"])
        self.assertTrue(result["routine_action_fastpath"]["terminal_native_acceptance_used"])
        self.assertEqual(result["action_lifecycle"]["status"], "native_accepted")
        self.assertTrue(result["action_lifecycle"]["native_write_submitted"])
        self.assertEqual(result["tool_calls"][-1]["name"], "hub_call_device_command")
        self.assertIn("OFF command accepted", result["answer"])
        self.assertIn("physical state has not been independently verified", result["answer"])

    async def test_unverified_effect_keeps_prewrite_review(self):
        hub = FictionalHub()
        model = ScriptedAgent([
            tool("hub_get_device", deviceId="LAB-LAMP-1"),
            # Wrong claimed effect: no source-backed fast path.
            tool("hub_call_device_command", deviceId="LAB-LAMP-1",
                 command="off"),
            {"content": "Insufficient source evidence for the requested policy effect."},
        ])
        gate = Interaction(require_native_write_approval=True)
        try:
            result = await model.answer(
                "Block the fictional office device internet access", [],
                hub, 60, before_call=gate.before_call,
            )
        finally:
            await model.close()
        self.assertTrue(result["prewrite_model_review_invoked"])
        self.assertFalse(result["routine_action_fastpath"]["prewrite_model_review_skipped"])
        self.assertFalse(result["routine_action_fastpath"]["terminal_native_acceptance_used"])
        self.assertNotIn("hub_call_device_command", [n for n, _ in hub.calls])


if __name__ == "__main__":
    unittest.main()

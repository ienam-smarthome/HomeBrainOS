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
from routine_action_fastpath import (
    routine_candidate, accepted_routine_answer, verification_target,
)


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



def context_receipt(*, target_label="Fictional Office Lamp",
                    identifier="LAB-LAMP-1", reported="on",
                    label_filter="fictional", has_more=False,
                    capabilities="Actuator, Light, Switch",
                    count=2, total=2):
    summary = (
        "Mode: Sunset\nDevices: 2 of 2\n"
        f"- {target_label} ({identifier}, Lab) - {capabilities}; "
        f"switch={reported}, level=80\n"
        "- Fictional Office Sensor (LAB-SENSE-2, Lab) - "
        "MotionSensor, Sensor; motion=inactive"
    )
    return previous_receipt(
        "hub_list_devices",
        {"format": "context", "labelFilter": label_filter},
        {"summary": summary, "count": count, "total": total,
         "hasMore": has_more, "labelFilter": label_filter,
         "offset": 0, "limit": 50},
    )


def wait_proposal(*, command="off", **kwargs):
    return proposal(
        command=command,
        waitFor={"attribute": "switch", "expectedValue": command,
                 "timeoutMs": 5000}, **kwargs
    )


class ContextVerificationTests(unittest.TestCase):
    def test_filtered_native_context_proves_only_verification_read_target(self):
        receipts = [
            previous_receipt("hub_list_devices", {"format": "context"},
                             {"summary": "partial", "count": 50,
                              "total": 203, "hasMore": True}),
            context_receipt(),
        ]
        chosen = verification_target(
            "Turn off Fictional Office Lamp", [wait_proposal()], receipts,
            approval_available=True,
        )
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["device_id"], "LAB-LAMP-1")
        self.assertEqual(chosen["command"], "off")
        self.assertIsNone(routine_candidate(
            "Turn off Fictional Office Lamp", [wait_proposal()], receipts,
            approval_available=True,
        ), "Inventory alone must NOT authorize fast native dispatch")
        qualified = routine_candidate(
            "Turn off Fictional Office Lamp", [wait_proposal()],
            receipts + [previous_receipt(
                "hub_get_device", {"deviceId": "LAB-LAMP-1"},
                device(),
            )],
            approval_available=True,
        )
        self.assertIsNotNone(qualified)
        self.assertEqual(qualified["wait_for"]["timeoutMs"], 5000)

    def test_unverified_inventory_cannot_trigger_client_targeted_read(self):
        for source in (
            context_receipt(has_more=True),
            context_receipt(count=2, total=3),
            context_receipt(target_label="Fictional Office Lamp Alternate"),
            context_receipt(identifier="LAB-LAMP-OTHER"),
            context_receipt(reported="off"),
            context_receipt(capabilities="Switch, Sensor"),
            context_receipt(count=50, total=50),
            context_receipt(label_filter="nonmatching"),
            previous_receipt("hub_list_devices", {"format": "context"},
                             {"summary": "Devices: 2 of 2\n"
                              "- Fictional Office Lamp (LAB-LAMP-1, Lab) - "
                              "Actuator, Light, Switch; switch=on",
                              "count": 2, "total": 2,
                              "hasMore": False, "labelFilter": "fictional"}),
        ):
            with self.subTest(source=source):
                self.assertIsNone(verification_target(
                    "Turn off Fictional Office Lamp", [wait_proposal()],
                    [source], approval_available=True,
                ))
        self.assertIsNone(verification_target(
            "Turn off Fictional Office Lamp", [wait_proposal()],
            [context_receipt(), previous_receipt(
                "hub_get_device", {"deviceId": "LAB-LAMP-1"}, device())],
            approval_available=True,
        ))
        self.assertIsNone(verification_target(
            "Turn off Fictional Office Lamp", [wait_proposal()],
            [context_receipt()], approval_available=False,
        ))

    def test_strict_waitfor_semantics_reject_mismatch_and_extra_arguments(self):
        for extra in (
            {"waitFor": {"attribute": "contact", "expectedValue": "off",
                         "timeoutMs": 5000}},
            {"waitFor": {"attribute": "switch", "expectedValue": "on",
                         "timeoutMs": 5000}},
            {"waitFor": {"attribute": "switch", "expectedValue": "off",
                         "timeoutMs": 12000}},
            {"waitFor": {"attribute": "switch", "expectedValue": "off",
                         "timeoutMs": True}},
            {"waitFor": {"attribute": "switch", "expectedValue": "off",
                         "timeoutMs": 5000, "extra": True}},
            {"parameters": [1]},
            {"confirm": True},
        ):
            args = {"deviceId": "LAB-LAMP-1", "command": "off", **extra}
            with self.subTest(args=args):
                self.assertIsNone(verification_target(
                    "Turn off Fictional Office Lamp",
                    [{"function": {"name": "hub_call_device_command",
                                   "arguments": args}}],
                    [context_receipt()], approval_available=True,
                ))

    def test_waitfor_acceptance_is_in_command_not_independent_physical_proof(self):
        chosen = routine_candidate(
            "Turn off Fictional Office Lamp", [wait_proposal()],
            [previous_receipt("hub_get_device",
                              {"deviceId": "LAB-LAMP-1"}, device())],
            approval_available=True,
        )
        self.assertIsNotNone(chosen)
        original_args = {
            "deviceId": "LAB-LAMP-1", "command": "off",
            "waitFor": {"attribute": "switch", "expectedValue": "off",
                        "timeoutMs": 5000},
        }
        source = {
            "success": True, "device": "Fictional Office Lamp",
            "command": "off", "parameters": None,
            "waitFor": {"attribute": "switch", "expected": "off",
                        "converged": True, "finalValue": "off",
                        "elapsedMs": 384},
            "state": {"switch": {"value": "off",
                                "timestamp": "2026-11-15 18:38:56"}},
        }
        accepted = {
            **previous_receipt("hub_call_device_command",
                               original_args, source),
            "possible_native_action": True,
        }
        output = accepted_routine_answer(chosen, [accepted])
        self.assertIn("in-command check reported switch OFF", output)
        self.assertIn("not independently verified", output)
        self.assertNotIn("has been turned off", output)
        for bad in (
            {**source, "waitFor": {**source["waitFor"], "converged": False}},
            {**source, "waitFor": {**source["waitFor"], "expected": "on"}},
            {**source, "waitFor": {**source["waitFor"], "finalValue": "on"}},
            {**source, "device": "Different Fixture"},
            {**source, "success": False},
        ):
            with self.subTest(bad=bad):
                record = {
                    **previous_receipt("hub_call_device_command",
                                       original_args, bad),
                    "possible_native_action": True,
                }
                self.assertIsNone(accepted_routine_answer(chosen, [record]))


class ContextHub(FictionalHub):
    async def call(self, name, arguments):
        if name == "hub_list_devices":
            self.calls.append((name, deepcopy(arguments)))
            if arguments.get("labelFilter"):
                source = json.loads(context_receipt()["response"])
                return source
            return mcp_result({
                "summary": "Mode: Sunset\nDevices: 50 of 203",
                "count": 50, "total": 203, "hasMore": True,
                "offset": 0, "limit": 50,
            })
        if name == "hub_get_device":
            self.calls.append((name, deepcopy(arguments)))
            source = device()
            source["currentStates"] = {"switch": "on"}
            return mcp_result(source)
        if name == "hub_call_device_command":
            self.calls.append((name, deepcopy(arguments)))
            return mcp_result({
                "success": True, "device": "Fictional Office Lamp",
                "command": arguments["command"], "parameters": None,
                "waitFor": {"attribute": "switch", "expected": "off",
                            "converged": True, "finalValue": "off",
                            "elapsedMs": 384},
                "state": {"switch": {"value": "off"}},
            })
        return await super().call(name, arguments)


class ContextIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_shape_skips_redundant_ai_turns_but_not_real_approval(self):
        hub = ContextHub()
        model = ScriptedAgent([
            tool("hub_list_devices", format="context"),
            tool("hub_list_devices", format="context",
                 labelFilter="fictional"),
            tool("hub_call_device_command", deviceId="LAB-LAMP-1",
                 command="off",
                 waitFor={"attribute": "switch",
                          "expectedValue": "off", "timeoutMs": 5000}),
        ])
        gate = Interaction(require_native_write_approval=True)
        task = asyncio.create_task(model.answer(
            "Turn off Fictional Office Lamp", [], hub, 60,
            before_call=gate.before_call,
        ))
        try:
            for _ in range(1500):
                if gate.pending or task.done():
                    break
                await asyncio.sleep(0.002)
            self.assertIsNotNone(gate.pending)
            self.assertEqual(
                [n for n, _ in hub.calls],
                ["hub_list_devices", "hub_list_devices", "hub_get_device"],
            )
            self.assertEqual(
                gate.pending["preview"]["fields"]["device"],
                "Fictional Office Lamp",
            )
            gate.decide(gate.pending["id"], True)
            result = await asyncio.wait_for(task, 5)
        finally:
            if not task.done():
                gate.invalidate()
                task.cancel()
            await model.close()
        self.assertEqual(
            [n for n, _ in hub.calls],
            ["hub_list_devices", "hub_list_devices", "hub_get_device",
             "hub_call_device_command"],
        )
        self.assertEqual(model.rounds_seen, 3)
        self.assertEqual(result["rounds"], 3)
        self.assertEqual(result["action_lifecycle"]["status"], "native_accepted")
        self.assertTrue(result["routine_action_fastpath"]
                        ["prewrite_model_review_skipped"])
        self.assertTrue(result["routine_action_fastpath"]
                        ["terminal_native_acceptance_used"])
        self.assertEqual(result["routine_action_fastpath"]
                         ["detail_verification_status"], "read_succeeded")
        self.assertEqual(result["tool_calls"][2]["name"], "hub_get_device")
        self.assertTrue(result["tool_calls"][2]
                        ["client_routine_verification_read"])
        self.assertIn("in-command check reported switch OFF", result["answer"])
        self.assertIn("not independently verified", result["answer"])



if __name__ == "__main__":
    unittest.main()

"""Alpha.117 lightweight native postwrite READ — fictional device / model only.

No cloud model, real Hubitat, network or home write is involved. All tests
require the existing source-first model tool selection and native approval.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from interaction import Interaction
from routine_post_write_readback import (
    inspect_routine_post_write_state, routine_readback_answer,
)
from test_routine_action_fastpath import (
    BootstrappedHub, BootstrapModel, device, mcp_result, tool,
)


class FictionalStatefulHub(BootstrappedHub):
    def __init__(self, *, followup_mode="matched", reject_write=False):
        super().__init__(label="Fictional Office Lamp", initial="off")
        self.after_write = False
        self.followup_mode = followup_mode
        self.reject_write = reject_write

    async def call(self, name, arguments):
        if name == "hub_call_device_command":
            self.calls.append((name, deepcopy(arguments)))
            self.after_write = True
            if self.reject_write:
                return mcp_result({
                    "success": False, "device": self.label,
                    "command": arguments["command"],
                    "error": "native operation rejected",
                })
            return mcp_result({
                "success": True, "device": self.label,
                "command": arguments["command"], "parameters": None,
                "state": {"switch": {"value": "off"}},
            })
        if name == "hub_get_device" and self.after_write:
            self.calls.append((name, deepcopy(arguments)))
            if self.followup_mode == "error":
                return {"isError": True, "content": [
                    {"type": "text", "text": "Native detail unavailable"}
                ]}
            if self.followup_mode == "slow":
                await asyncio.sleep(2)
            source = device(
                label=self.label,
                switch=("on" if self.followup_mode in
                        ("matched", "wrong_id", "contradiction") else "off"),
            )
            if self.followup_mode == "wrong_id":
                source["id"] = "LAB-OTHER"
            if self.followup_mode == "contradiction":
                source["currentStates"] = {"switch": "off"}
            if self.followup_mode == "missing_state":
                source["attributes"] = []
            return mcp_result(source)
        return await super().call(name, arguments)


async def run_case(*, followup_mode="matched", reject_write=False):
    hub = FictionalStatefulHub(
        followup_mode=followup_mode, reject_write=reject_write
    )
    model = BootstrapModel([
        tool("hub_call_device_command", deviceId="LAB-LAMP-1", command="on")
    ])
    gate = Interaction(
        require_native_write_approval=True, auto_approve_lights=True
    )
    try:
        result = await model.answer(
            "Turn on Fictional Office Lamp", [], hub, 60,
            before_call=gate.before_call,
            enable_routine_bootstrap=True,
            enable_routine_post_write_readback=True,
        )
    finally:
        await model.close()
    return hub, model, gate, result


class ReadbackUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_validated_readback_does_not_prove_physical_effect(self):
        hub = FictionalStatefulHub()
        hub.after_write = True
        candidate = {
            "device_id": "LAB-LAMP-1",
            "label": "Fictional Office Lamp", "command": "on",
        }
        result, receipt = await inspect_routine_post_write_state(hub, candidate)
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["reported_switch"], "on")
        self.assertFalse(result["physical_state_verified"])
        self.assertTrue(receipt["read_only"])
        self.assertTrue(receipt["client_routine_post_write_readback"])
        answer = routine_readback_answer("accepted", candidate, result)
        self.assertIn("separate Hubitat read afterward", answer)
        self.assertIn("Physical operation was not independently verified", answer)
        self.assertNotIn("physically turned on", answer)

    async def test_separate_native_state_conflict_and_identity_mismatch(self):
        candidate = {
            "device_id": "LAB-LAMP-1",
            "label": "Fictional Office Lamp", "command": "on",
        }
        for mode, status in (
            ("not_matched", "not_matched"),
            ("wrong_id", "identity_mismatch"),
            ("contradiction", "state_unavailable"),
            ("missing_state", "state_unavailable"),
            ("error", "read_unavailable"),
        ):
            with self.subTest(mode=mode):
                hub = FictionalStatefulHub(followup_mode=mode)
                hub.after_write = True
                result, receipt = await inspect_routine_post_write_state(
                    hub, candidate
                )
                self.assertEqual(result["status"], status)
                self.assertEqual(len(hub.calls), 1)
                self.assertEqual(receipt["name"], "hub_get_device")
                self.assertFalse(result["physical_state_verified"])
                answer = routine_readback_answer("accepted", candidate, result)
                self.assertNotIn("physically turned on", answer)

    async def test_readback_timeout_is_bounded_without_retry(self):
        hub = FictionalStatefulHub(followup_mode="slow")
        hub.after_write = True
        candidate = {
            "device_id": "LAB-LAMP-1",
            "label": "Fictional Office Lamp", "command": "on",
        }
        result, receipt = await inspect_routine_post_write_state(
            hub, candidate, max_seconds=0.10
        )
        self.assertEqual(result["status"], "read_unavailable")
        self.assertEqual(receipt["name"], "hub_get_device")
        self.assertEqual(len(hub.calls), 1)
        self.assertLess(result["elapsed_ms"], 1000)


class RoutineReadbackIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_uses_one_round_one_write_then_one_read(self):
        hub, model, gate, result = await run_case()
        self.assertEqual(model.rounds_seen, 1)
        self.assertTrue(gate.routine_auto_approval_used)
        self.assertIsNone(gate.pending)
        self.assertEqual([n for n, _ in hub.calls], [
            "hub_list_devices", "hub_get_device",
            "hub_call_device_command", "hub_get_device",
        ])
        self.assertEqual(result["action_lifecycle"]["status"], "native_accepted")
        self.assertEqual(result["rounds"], 1)
        fast = result["routine_action_fastpath"]
        self.assertEqual(fast["post_write_readback"]["status"], "matched")
        self.assertTrue(fast["terminal_native_acceptance_used"])
        self.assertEqual(result["tool_calls"][-1]["name"], "hub_get_device")
        self.assertTrue(result["tool_calls"][-1]
                        ["client_routine_post_write_readback"])
        self.assertIn("separate Hubitat read afterward reported switch ON",
                      result["answer"])
        self.assertIn("Physical operation was not independently verified",
                      result["answer"])
        times = result["action_performance"]
        self.assertIsInstance(times["first_native_write_submission_elapsed_ms"], int)
        self.assertIsInstance(
            times["first_native_write_response_received_elapsed_ms"], int)
        self.assertIsInstance(times["routine_readback_started_elapsed_ms"], int)
        self.assertIsInstance(times["routine_readback_finished_elapsed_ms"], int)
        self.assertLessEqual(
            times["first_native_write_submission_elapsed_ms"],
            times["first_native_write_response_received_elapsed_ms"])
        self.assertLessEqual(
            times["first_native_write_response_received_elapsed_ms"],
            times["routine_readback_started_elapsed_ms"])
        self.assertLessEqual(
            times["routine_readback_started_elapsed_ms"],
            times["routine_readback_finished_elapsed_ms"])
        self.assertGreaterEqual(times["routine_readback_elapsed_ms"], 0)

    async def test_mismatch_reports_not_confirmed_never_resubmits(self):
        hub, model, gate, result = await run_case(followup_mode="not_matched")
        self.assertEqual(result["action_lifecycle"]["status"], "native_accepted")
        self.assertEqual(result["routine_action_fastpath"]
                         ["post_write_readback"]["status"], "not_matched")
        self.assertIn("still reported switch OFF", result["answer"])
        self.assertIn("requested state was not confirmed", result["answer"])
        self.assertEqual(
            [n for n, _ in hub.calls].count("hub_call_device_command"), 1)

    async def test_unavailable_read_keeps_true_write_acceptance(self):
        hub, model, gate, result = await run_case(followup_mode="error")
        self.assertEqual(result["action_lifecycle"]["status"], "native_accepted")
        self.assertEqual(result["routine_action_fastpath"]
                         ["post_write_readback"]["status"], "read_unavailable")
        self.assertIn("command accepted", result["answer"])
        self.assertIn("state remains unverified", result["answer"])
        self.assertEqual(
            [n for n, _ in hub.calls].count("hub_call_device_command"), 1)

    async def test_rejected_write_must_not_generate_post_write_read(self):
        hub, model, gate, result = await run_case(reject_write=True)
        self.assertNotEqual(result["action_lifecycle"]["status"], "native_accepted")
        self.assertEqual(result["routine_action_fastpath"]
                         ["post_write_readback"]["status"], "not_invoked")
        self.assertEqual(
            [n for n, _ in hub.calls].count("hub_call_device_command"), 1)
        self.assertEqual(
            [n for n, _ in hub.calls].count("hub_get_device"), 1)
        self.assertEqual(model.rounds_seen, 1)


if __name__ == "__main__":
    unittest.main()

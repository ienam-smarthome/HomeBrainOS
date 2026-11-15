"""V2 original-Ask authorisation boundary — synthetic only, no home writes.

The current user's text is only sufficient for a single source-verified,
model-selected, harmless ON/OFF with an active local policy. It never bypasses
the upstream native MCP write gate. All fictional device IDs and receipts.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from mcp import MCPError
from interaction import Interaction
from routine_action_fastpath import routine_candidate
from routine_approval_policy import (
    source_verified_auto_approval_class,
    matches_original_native_write,
    trusted_switch_ids,
)
from test_routine_action_fastpath import (
    BootstrappedHub, BootstrapModel, device, previous_receipt, proposal, tool,
)


IDENTITY = "LAB-LAMP-1"


def source_pair(*, label="Fictional Office Lamp", capabilities=None,
                protocol="matter", driver="Matter Generic Dimmer",
                state="on", name="Laboratory Dimmer"):
    detail = device(label=label, switch=state)
    detail["capabilities"] = (
        list(capabilities) if capabilities is not None
        else ["Switch", "Light", "SwitchLevel"]
    )
    detail["name"] = name
    receipts = [
        previous_receipt(
            "hub_list_devices",
            {"labelFilter": label, "format": "summary"},
            {"devices": [{
                "id": IDENTITY, "label": label,
                "driver": driver, "protocol": protocol,
                "disabled": False, "currentStates": {"switch": state},
            }], "count": 1, "total": 1, "labelFilter": label},
        ),
        previous_receipt("hub_get_device", {"deviceId": IDENTITY}, detail),
    ]
    return receipts


def candidate_for(label="Fictional Office Lamp", **kwargs):
    receipts = source_pair(label=label, **kwargs)
    candidate = routine_candidate(
        f"Turn off {label}", [proposal()],
        receipts, approval_available=True,
    )
    return candidate, receipts


class SourcePolicyTests(unittest.TestCase):
    def test_explicit_safe_switch_id_parser_rejects_globs(self):
        self.assertEqual(trusted_switch_ids("123, 456"), {"123", "456"})
        self.assertEqual(trusted_switch_ids(""), frozenset())
        self.assertEqual(trusted_switch_ids("123, *"), frozenset())
        self.assertEqual(trusted_switch_ids("12a"), frozenset())

    def test_light_auto_approval_requires_enabled_policy_and_source(self):
        candidate, receipts = candidate_for()
        self.assertIsNotNone(candidate)
        result = source_verified_auto_approval_class(
            candidate, receipts, auto_lights=True,
            safe_switch_ids=frozenset(),
        )
        self.assertEqual(result, "verified_light")
        self.assertIsNone(source_verified_auto_approval_class(
            candidate, receipts, auto_lights=False,
            safe_switch_ids=frozenset(),
        ))
        self.assertIsNone(source_verified_auto_approval_class(
            candidate, receipts[1:], auto_lights=True,
            safe_switch_ids=frozenset(),
        ))

    def test_switch_requires_explicit_source_proved_physical_allowlist(self):
        candidate, receipts = candidate_for(
            label="Fictional Safe Plug",
            capabilities=["Switch", "Outlet", "PowerMeter"],
            protocol="zigbee", driver="Tuya Zigbee Outlet",
        )
        self.assertIsNotNone(candidate)
        self.assertIsNone(source_verified_auto_approval_class(
            candidate, receipts, auto_lights=True,
            safe_switch_ids=frozenset(),
        ))
        self.assertEqual(source_verified_auto_approval_class(
            candidate, receipts, auto_lights=True,
            safe_switch_ids=frozenset({IDENTITY}),
        ), "explicitly_trusted_physical_switch")
        for altered in ("virtual", "lan", "", "wifi"):
            changed = deepcopy(receipts)
            import json
            source = json.loads(changed[0]["response"])
            doc = json.loads(source["content"][0]["text"])
            doc["devices"][0]["protocol"] = altered
            source["content"][0]["text"] = json.dumps(doc)
            changed[0]["response"] = json.dumps(source)
            with self.subTest(protocol=altered):
                self.assertIsNone(source_verified_auto_approval_class(
                    candidate, changed, auto_lights=True,
                    safe_switch_ids=frozenset({IDENTITY}),
                ))

    def test_sensitive_capabilities_or_effect_words_never_auto_approve(self):
        cases = (
            ("Fictional Heater", ["Switch", "Outlet"]),
            ("Fictional Internet Block", ["Switch", "Outlet"]),
            ("Fictional Security Light", ["Switch", "Light"]),
            ("Fictional Garage Light", ["Switch", "Light"]),
            ("Fictional Heating Lamp", ["Switch", "Light"]),
            ("Fictional Light", ["Switch", "Light", "Thermostat"]),
            ("Fictional Lamp", ["Switch", "Light", "Lock"]),
            ("Fictional Desk Outlet", ["Switch", "Outlet", "FanControl"]),
        )
        for label, caps in cases:
            with self.subTest(label=label):
                candidate, receipts = candidate_for(
                    label=label, capabilities=caps,
                    protocol="zigbee",
                )
                self.assertIsNotNone(candidate)
                self.assertIsNone(source_verified_auto_approval_class(
                    candidate, receipts, auto_lights=True,
                    safe_switch_ids=frozenset({IDENTITY}),
                ))

    def test_wrong_write_arguments_never_match_original_ask_permission(self):
        candidate, receipts = candidate_for()
        self.assertIsNotNone(candidate)
        self.assertTrue(matches_original_native_write(
            candidate, "hub_call_device_command",
            {"deviceId": IDENTITY, "command": "off"},
        ))
        for args in (
            {"deviceId": "OTHER", "command": "off"},
            {"deviceId": IDENTITY, "command": "on"},
            {"deviceId": IDENTITY, "command": "off", "parameters": [7]},
            {"deviceId": IDENTITY, "command": "off", "confirm": True},
            {"deviceId": IDENTITY, "command": "off", "commands": []},
        ):
            with self.subTest(args=args):
                self.assertFalse(matches_original_native_write(
                    candidate, "hub_call_device_command", args,
                ))
        self.assertFalse(matches_original_native_write(
            candidate, "hub_set_rule", {"deviceId": IDENTITY, "command": "off"},
        ))


class ActualGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_ask_one_round_sends_only_model_selected_native_write(self):
        hub = BootstrappedHub()
        model = BootstrapModel([
            tool("hub_call_device_command", deviceId=IDENTITY, command="off")
        ])
        gate = Interaction(
            require_native_write_approval=True,
            auto_approve_lights=True,
        )
        try:
            result = await model.answer(
                "Turn off Fictional Office Lamp", [], hub, 60,
                before_call=gate.before_call, enable_routine_bootstrap=True,
            )
        finally:
            await model.close()
        self.assertEqual(model.rounds_seen, 1)
        self.assertIsNone(gate.pending)
        self.assertTrue(gate.routine_auto_approval_used)
        self.assertEqual(gate.routine_auto_approval_class, "verified_light")
        self.assertEqual([name for name, _ in hub.calls], [
            "hub_list_devices", "hub_get_device", "hub_call_device_command",
        ])
        self.assertEqual(result["action_lifecycle"]["status"], "native_accepted")
        self.assertTrue(result["routine_native_authorization"]
                        ["automatic_authorization_used"])
        self.assertLess(result["action_performance"]["native_approval_wait_ms"], 100)
        self.assertIn("OFF command accepted", result["answer"])
        self.assertIn("not been independently verified", result["answer"])

    async def test_disabled_setting_retains_true_separate_approval(self):
        hub = BootstrappedHub()
        model = BootstrapModel([
            tool("hub_call_device_command", deviceId=IDENTITY, command="off")
        ])
        gate = Interaction(
            require_native_write_approval=True,
            auto_approve_lights=False,
        )
        task = asyncio.create_task(model.answer(
            "Turn off Fictional Office Lamp", [], hub, 60,
            before_call=gate.before_call, enable_routine_bootstrap=True,
        ))
        try:
            for _ in range(1500):
                if gate.pending or task.done():
                    break
                await asyncio.sleep(0.002)
            self.assertIsNotNone(gate.pending)
            self.assertFalse(gate.routine_auto_approval_used)
            self.assertNotIn("hub_call_device_command",
                             [n for n, _ in hub.calls])
            gate.decide(gate.pending["id"], True)
            result = await asyncio.wait_for(task, 5)
        finally:
            if not task.done():
                gate.invalidate()
                task.cancel()
            await model.close()
        self.assertEqual(result["action_lifecycle"]["status"], "native_accepted")
        self.assertFalse(result["routine_native_authorization"]
                         ["automatic_authorization_used"])

    async def test_one_shot_permission_not_reused_for_second_or_changed_write(self):
        candidate, receipts = candidate_for()
        gate = Interaction(
            require_native_write_approval=True,
            auto_approve_lights=True,
        )
        self.assertTrue(gate.offer_current_ask_routine_authorization(
            candidate, receipts,
        ))
        await gate.before_call(
            "hub_call_device_command",
            {"deviceId": IDENTITY, "command": "off"},
            "source verified",
        )
        self.assertTrue(gate.routine_auto_approval_used)
        self.assertIsNone(gate.pending)
        task = asyncio.create_task(gate.before_call(
            "hub_call_device_command",
            {"deviceId": IDENTITY, "command": "off"},
            "second attempted write",
        ))
        try:
            for _ in range(200):
                if gate.pending or task.done():
                    break
                await asyncio.sleep(0.001)
            self.assertIsNotNone(gate.pending)
            gate.decide(gate.pending["id"], False)
            with self.assertRaises(MCPError):
                await task
        finally:
            gate.invalidate()
            task.cancel()

    async def test_sensitive_and_changed_requests_still_trigger_real_gate(self):
        candidate, receipts = candidate_for()
        gate = Interaction(
            require_native_write_approval=True,
            auto_approve_lights=True,
        )
        self.assertTrue(gate.offer_current_ask_routine_authorization(
            candidate, receipts,
        ))
        task = asyncio.create_task(gate.before_call(
            "hub_call_device_command",
            {"deviceId": IDENTITY, "command": "on"},
            "not the original user requested direction",
        ))
        try:
            for _ in range(200):
                if gate.pending or task.done():
                    break
                await asyncio.sleep(0.001)
            self.assertIsNotNone(gate.pending)
            self.assertFalse(gate.routine_auto_approval_used)
            gate.decide(gate.pending["id"], False)
            with self.assertRaises(MCPError):
                await task
        finally:
            gate.invalidate()
            task.cancel()
        # Even a matched native call with an explicit confirm flag must not
        # be silently auto-approved; native confirm always wins.
        gate2 = Interaction(
            require_native_write_approval=True,
            auto_approve_lights=True,
        )
        gate2.offer_current_ask_routine_authorization(candidate, receipts)
        task2 = asyncio.create_task(gate2.before_call(
            "hub_call_device_command",
            {"deviceId": IDENTITY, "command": "off", "confirm": True},
            "upstream-confirm-required operation",
        ))
        try:
            for _ in range(200):
                if gate2.pending or task2.done():
                    break
                await asyncio.sleep(0.001)
            self.assertIsNotNone(gate2.pending)
            gate2.decide(gate2.pending["id"], False)
            with self.assertRaises(MCPError):
                await task2
        finally:
            gate2.invalidate()
            task2.cancel()

    async def test_cancel_invalidates_pending_permission(self):
        candidate, receipts = candidate_for()
        gate = Interaction(
            require_native_write_approval=True,
            auto_approve_lights=True,
        )
        self.assertTrue(gate.offer_current_ask_routine_authorization(
            candidate, receipts,
        ))
        gate.invalidate()
        with self.assertRaises(MCPError):
            await gate.before_call(
                "hub_call_device_command",
                {"deviceId": IDENTITY, "command": "off"},
                "cancelled request",
            )
        self.assertFalse(gate.routine_auto_approval_used)



# Source-real SHAPE only: a physical lighting bridge's native child can
# legitimately report protocol=virtual and a Generic Component Dimmer driver.
# Fictional identifiers and labels deliberately avoid a household-specific
# control shortcut.
from routine_component_light import (
    component_parent_id, verified_physical_bridge_parent,
)
from test_routine_action_fastpath import mcp_result


PARENT_ID = "900"
PARENT_LABEL = "Matter Lighting Bridge"


def _set_original_receipt_document(row, update):
    import json
    envelope = json.loads(row["response"])
    doc = json.loads(envelope["content"][0]["text"])
    update(doc)
    envelope["content"][0]["text"] = json.dumps(doc)
    row["response"] = json.dumps(envelope)


def fictional_component_sources(
    *, child_driver="Generic Component Dimmer",
    parent_protocol="matter",
    parent_label=PARENT_LABEL,
    parent_driver="Matter Generic Bridge",
    parent_id=PARENT_ID,
    parent_enabled=True,
):
    candidate, rows = candidate_for(
        label="Fictional Study Light",
        capabilities=["Actuator", "ChangeLevel", "Light", "Switch",
                      "SwitchLevel"],
    )
    assert candidate is not None
    _set_original_receipt_document(rows[0], lambda doc: doc["devices"][0].update({
        "protocol": "virtual",
        "driver": child_driver,
        "parentDeviceId": parent_id,
    }))
    parent_detail = previous_receipt(
        "hub_get_device", {"deviceId": parent_id},
        {"id": parent_id, "name": parent_label,
         "label": parent_label, "capabilities": ["Bridge"],
         "attributes": [], "commands": []},
    )
    parent_list = previous_receipt(
        "hub_list_devices",
        {"format": "summary", "labelFilter": parent_label},
        {"devices": [{
            "id": parent_id, "name": parent_label,
            "label": parent_label, "protocol": parent_protocol,
            "driver": parent_driver, "disabled": not parent_enabled,
        }],
         "count": 1, "total": 1, "labelFilter": parent_label},
    )
    return candidate, rows, [parent_detail, parent_list]


class NativeComponentLightApprovalTests(unittest.TestCase):
    def test_verified_virtual_child_requires_original_physical_bridge_proof(self):
        candidate, child, parent = fictional_component_sources()
        self.assertEqual(component_parent_id(candidate, child), PARENT_ID)
        self.assertFalse(verified_physical_bridge_parent(candidate, child))
        self.assertIsNone(source_verified_auto_approval_class(
            candidate, child, auto_lights=True,
            safe_switch_ids=frozenset(),
        ))
        self.assertTrue(verified_physical_bridge_parent(
            candidate, child + parent))
        self.assertEqual(source_verified_auto_approval_class(
            candidate, child + parent, auto_lights=True,
            safe_switch_ids=frozenset(),
        ), "verified_physical_bridge_component_light")

    def test_no_auto_approval_for_fake_virtual_and_sensitive_bridge_roles(self):
        cases = [
            {"child_driver": "Virtual Switch"},
            {"child_driver": "Generic Component Switch"},
            {"parent_protocol": "virtual"},
            {"parent_protocol": "lan"},
            {"parent_label": "Network Bridge"},
            {"parent_label": "Security Bridge"},
            {"parent_driver": "Virtual Generic Bridge"},
            {"parent_enabled": False},
        ]
        for modified in cases:
            with self.subTest(modified=modified):
                candidate, child, parent = fictional_component_sources(
                    **modified)
                self.assertIsNone(source_verified_auto_approval_class(
                    candidate, child + parent,
                    auto_lights=True, safe_switch_ids=frozenset(),
                ))
        candidate, child, parent = fictional_component_sources()
        self.assertIsNone(source_verified_auto_approval_class(
            candidate, child + parent,
            auto_lights=False, safe_switch_ids=frozenset(),
        ))

    def test_original_parent_id_and_inventory_identity_must_agree(self):
        candidate, child, parent = fictional_component_sources()
        modified = deepcopy(parent)
        _set_original_receipt_document(modified[0],
            lambda doc: doc.update({"id": "901"}))
        self.assertFalse(verified_physical_bridge_parent(
            candidate, child + modified))
        modified = deepcopy(parent)
        _set_original_receipt_document(modified[1],
            lambda doc: doc["devices"][0].update({"id": "901"}))
        self.assertFalse(verified_physical_bridge_parent(
            candidate, child + modified))
        modified = deepcopy(parent)
        _set_original_receipt_document(modified[1],
            lambda doc: doc.update({"total": 2}))
        self.assertFalse(verified_physical_bridge_parent(
            candidate, child + modified))
        modified = deepcopy(child)
        _set_original_receipt_document(modified[0],
            lambda doc: doc["devices"][0].update(
                {"parentDeviceId": "901"}))
        self.assertFalse(verified_physical_bridge_parent(
            candidate, modified + parent))
        modified = deepcopy(child)
        _set_original_receipt_document(modified[1],
            lambda doc: doc["capabilities"].remove("SwitchLevel"))
        self.assertIsNone(component_parent_id(candidate, modified))
        modified = deepcopy(child)
        _set_original_receipt_document(modified[0],
            lambda doc: doc["devices"][0].update({"parentDeviceId": None}))
        self.assertIsNone(component_parent_id(candidate, modified))


class FictionalNativeBridgeHub(BootstrappedHub):
    """All data are synthetic. No real Hubitat/light connections."""

    def __init__(self, *, parent_protocol="matter", parent_label=PARENT_LABEL,
                 parent_ok=True):
        super().__init__(label="Fictional Study Light", initial="on")
        self.parent_protocol = parent_protocol
        self.parent_label = parent_label
        self.parent_ok = parent_ok

    async def call(self, name, args):
        self.calls.append((name, deepcopy(args)))
        if name == "hub_list_devices":
            term = args.get("labelFilter", "")
            if term == "Fictional Study Light":
                return mcp_result({
                    "devices": [{
                        "id": IDENTITY, "label": "Fictional Study Light",
                        "name": "Generic Dimmable Light", "disabled": False,
                        "driver": "Generic Component Dimmer",
                        "protocol": "virtual", "parentDeviceId": PARENT_ID,
                        "currentStates": {"switch": "on", "level": 70},
                    }],
                    "count": 1, "total": 1,
                    "labelFilter": term,
                })
            if term == self.parent_label:
                return mcp_result({
                    "devices": [{
                        "id": PARENT_ID, "label": self.parent_label,
                        "name": self.parent_label, "disabled": False,
                        "protocol": self.parent_protocol,
                        "driver": "Matter Generic Bridge",
                    }],
                    "count": 1, "total": 1, "labelFilter": term,
                })
            return mcp_result({"devices": [], "count": 0,
                               "total": 0, "labelFilter": term})
        if name == "hub_get_device":
            if str(args["deviceId"]) == PARENT_ID:
                if not self.parent_ok:
                    return {"isError": True, "content": [{
                        "type": "text", "text": "Parent metadata unavailable"
                    }]}
                return mcp_result({
                    "id": PARENT_ID, "label": self.parent_label,
                    "name": self.parent_label, "capabilities": ["Bridge"],
                    "commands": [], "attributes": [],
                })
            child = device(label="Fictional Study Light", switch="on")
            child["capabilities"] = [
                "Actuator", "Light", "Switch", "SwitchLevel"
            ]
            child["name"] = "Generic Dimmable Light"
            return mcp_result(child)
        if name == "hub_call_device_command":
            return mcp_result({
                "success": True,
                "device": "Fictional Study Light",
                "command": args["command"], "parameters": None,
                "state": {"switch": {"value": "on"}},
            })
        raise AssertionError("Unexpected native tool")


class ComponentBridgeLiveShapeTests(unittest.IsolatedAsyncioTestCase):
    async def _attempt(self, *, protocol="matter", parent_ok=True,
                       auto_lights=True):
        hub = FictionalNativeBridgeHub(
            parent_protocol=protocol, parent_ok=parent_ok)
        model = BootstrapModel([
            tool("hub_call_device_command", deviceId=IDENTITY, command="off")
        ])
        gate = Interaction(
            require_native_write_approval=True,
            auto_approve_lights=auto_lights,
        )
        task = asyncio.create_task(model.answer(
            "Turn off Fictional Study Light", [], hub, 60,
            before_call=gate.before_call, enable_routine_bootstrap=True,
        ))
        try:
            for _ in range(1600):
                if gate.pending or task.done():
                    break
                await asyncio.sleep(0.002)
            pending = gate.pending is not None
            if pending:
                self.assertNotIn(
                    "hub_call_device_command",
                    [name for name, _ in hub.calls])
                gate.decide(gate.pending["id"], True)
            result = await asyncio.wait_for(task, 5)
        finally:
            if not task.done():
                gate.invalidate()
                task.cancel()
            await model.close()
        return hub, model, gate, pending, result

    async def test_real_gate_bypassed_only_for_verified_bridge_component_light(self):
        hub, model, gate, pending, result = await self._attempt()
        self.assertFalse(pending, "A safe bridge light needs no second click")
        self.assertTrue(gate.routine_auto_approval_used)
        self.assertEqual(
            gate.routine_auto_approval_class,
            "verified_physical_bridge_component_light",
        )
        self.assertEqual([name for name, _ in hub.calls], [
            "hub_list_devices", "hub_get_device",
            "hub_get_device", "hub_list_devices",
            "hub_call_device_command",
        ])
        self.assertEqual(model.rounds_seen, 1)
        self.assertEqual(result["action_lifecycle"]["status"],
                         "native_accepted")
        self.assertEqual(result["routine_native_authorization"]
                         ["component_parent_source_status"],
                         "physical_bridge_verified")
        self.assertTrue(result["routine_native_authorization"]
                        ["automatic_authorization_used"])
        self.assertIn("OFF command accepted", result["answer"])
        self.assertIn("not independently verified", result["answer"])

    async def test_unverified_virtual_parent_keeps_actual_approval_card(self):
        for kwargs in (
            {"protocol": "virtual"}, {"parent_ok": False},
            {"auto_lights": False},
        ):
            with self.subTest(kwargs=kwargs):
                hub, model, gate, pending, result = await self._attempt(**kwargs)
                self.assertTrue(pending)
                self.assertFalse(gate.routine_auto_approval_used)
                self.assertFalse(result["routine_native_authorization"]
                                 ["automatic_authorization_used"])
                self.assertEqual(result["action_lifecycle"]["status"],
                                 "native_accepted")



if __name__ == "__main__":
    unittest.main()

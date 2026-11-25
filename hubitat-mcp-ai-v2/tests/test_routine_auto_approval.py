"""V2 original-Ask authorisation boundary — synthetic only, no home writes.

The current user's text is only sufficient for a single source-verified,
model-selected, harmless ON/OFF with an active local policy. It never bypasses
the upstream native MCP write gate. All fictional device IDs and receipts.
"""
from __future__ import annotations

import asyncio
import sys
import json
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
        self.assertIn("has not been independently verified", result["answer"])

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


class BatchLightPolicyTests(unittest.TestCase):
    def _receipts(self, rows):
        out = [previous_receipt("hub_list_devices", {"format": "summary"}, {
            "devices": [{"id": i, "label": label, "driver": "Matter Generic Dimmer",
                         "protocol": "matter", "disabled": False,
                         "currentStates": {"switch": "off"}} for i, label, _ in rows],
            "count": len(rows), "total": len(rows)})]
        for i, label, caps in rows:
            d = device(label=label, switch="off")
            d["capabilities"] = list(caps)
            d["name"] = "Dimmer"
            d["id"] = i
            out.append(previous_receipt("hub_get_device", {"deviceId": i}, d))
        return out

    def test_batch_of_plain_lights_is_authorised(self):
        from routine_approval_policy import batch_light_authorization, batch_light_candidates
        rows = [("L1", "Fictional Hall Lamp", ["Switch", "Light", "SwitchLevel"]),
                ("L2", "Fictional Study Lamp", ["Switch", "Light", "SwitchLevel"])]
        receipts = self._receipts(rows)
        args = {"commands": [{"command": "on", "deviceId": "L1"}, {"command": "on", "deviceId": "L2"}]}
        # ids must be numeric; use numeric fictional ids
        rows = [("5001", rows[0][1], rows[0][2]), ("5002", rows[1][1], rows[1][2])]
        receipts = self._receipts(rows)
        args = {"commands": [{"command": "on", "deviceId": "5001"}, {"command": "on", "deviceId": "5002"}]}
        cands = batch_light_candidates(args, receipts)
        self.assertEqual(len(cands), 2)
        self.assertTrue(batch_light_authorization(cands, receipts))

    def test_one_sensitive_target_or_extra_key_blocks_the_whole_batch(self):
        from routine_approval_policy import batch_light_authorization, batch_light_candidates
        rows = [("5001", "Fictional Hall Lamp", ["Switch", "Light", "SwitchLevel"]),
                ("5002", "Fictional Heater Socket", ["Switch"])]
        receipts = self._receipts(rows)
        args = {"commands": [{"command": "on", "deviceId": "5001"}, {"command": "on", "deviceId": "5002"}]}
        cands = batch_light_candidates(args, receipts)
        self.assertFalse(batch_light_authorization(cands, receipts))
        bad = {"commands": [{"command": "setLevel", "deviceId": "5001"}, {"command": "on", "deviceId": "5002"}]}
        self.assertIsNone(batch_light_candidates(bad, receipts))
        extra = {"commands": [{"command": "on", "deviceId": "5001"}, {"command": "on", "deviceId": "5002"}], "waitFor": {}}
        self.assertIsNone(batch_light_candidates(extra, receipts))


class BatchProofConsumptionTests(unittest.IsolatedAsyncioTestCase):
    async def _gate_with_proof(self):
        helper = BatchLightPolicyTests()
        rows = [("5001", "Fictional Hall Lamp", ["Switch", "Light", "SwitchLevel"]),
                ("5002", "Fictional Study Lamp", ["Switch", "Light", "SwitchLevel"])]
        receipts = helper._receipts(rows)
        args = {"commands": [{"command": "on", "deviceId": "5001"}, {"command": "on", "deviceId": "5002"}]}
        from routine_approval_policy import batch_light_candidates
        gate = Interaction(require_native_write_approval=True, auto_approve_lights=True)
        self.assertTrue(gate.offer_batch_routine_authorization(
            args, batch_light_candidates(args, receipts), receipts))
        return gate, args

    async def test_exact_batch_is_auto_approved_once(self):
        gate, args = await self._gate_with_proof()
        await gate.before_call("hub_call_device_command", dict(args), "")
        self.assertTrue(gate.routine_auto_approval_used)
        self.assertEqual(gate.routine_auto_approval_class, "verified_light_batch")

    async def test_changed_batch_still_needs_a_card(self):
        gate, args = await self._gate_with_proof()
        changed = {"commands": args["commands"][:1] + [{"command": "off", "deviceId": "5002"}]}
        task = asyncio.ensure_future(gate.before_call("hub_call_device_command", changed, ""))
        await asyncio.sleep(0.05)
        self.assertFalse(gate.routine_auto_approval_used)
        self.assertIsNotNone(gate.pending)
        gate.decide(gate.pending["id"], False)
        with self.assertRaises(MCPError):
            await task


def block_detail(*, device_id="7001", label="Block Fictional-Gadget", internet="allowed",
                 with_ip=True, command="blockInternet", extra_caps=()):
    attrs = [{"name": "internetAccess", "value": internet}]
    if with_ip:
        attrs += [{"name": "deviceIP", "value": "192.0.2.9"}, {"name": "deviceMAC", "value": "aa:bb:cc:dd:ee:ff"}]
    return {"id": device_id, "label": label, "name": "Cudy Device-192.0.2.9",
            "capabilities": ["Actuator", "Refresh", "Sensor", "Switch", *extra_caps],
            "attributes": attrs,
            "commands": [{"name": command, "arguments": None}, {"name": "allowInternet", "arguments": None}]}


class InternetBlockPolicyTests(unittest.TestCase):
    def _receipts(self, **kw):
        d = block_detail(**kw)
        return [previous_receipt("hub_get_device", {"deviceId": d["id"]}, d)]

    def test_exact_block_and_allow_on_a_per_device_switch_qualify(self):
        from routine_approval_policy import internet_block_candidate
        receipts = self._receipts()
        for command in ("blockInternet", "allowInternet"):
            self.assertIsNotNone(internet_block_candidate({"deviceId": 7001, "command": command}, receipts))

    def test_everything_else_fails_closed(self):
        from routine_approval_policy import internet_block_candidate
        args = {"deviceId": "7001", "command": "blockInternet"}
        self.assertIsNone(internet_block_candidate(dict(args, parameters=[]), self._receipts()))
        self.assertIsNone(internet_block_candidate({"deviceId": "7001", "command": "off"}, self._receipts()))
        self.assertIsNone(internet_block_candidate({"deviceId": "7001", "command": "blockInMinutes"}, self._receipts()))
        # An all-devices style switch has no per-device IP/MAC.
        self.assertIsNone(internet_block_candidate(args, self._receipts(with_ip=False)))
        # Wrong/unread device, or a sensitive capability, never qualifies.
        self.assertIsNone(internet_block_candidate({"deviceId": "7002", "command": "blockInternet"}, self._receipts()))
        self.assertIsNone(internet_block_candidate(args, self._receipts(extra_caps=("Lock",))))
        self.assertIsNone(internet_block_candidate(args, []))

    def test_answer_reports_stored_state_without_overclaiming(self):
        from routine_approval_policy import internet_block_answer, internet_block_candidate
        receipts = self._receipts()
        args = {"deviceId": 7001, "command": "blockInternet"}
        cand = internet_block_candidate(args, receipts)
        write = previous_receipt("hub_call_device_command", args, {
            "success": True, "device": "Block Fictional-Gadget", "command": "blockInternet",
            "parameters": None, "state": {"internetAccess": {"value": "blocked"}}})
        write["possible_native_action"] = True
        text = internet_block_answer(cand, receipts + [write])
        self.assertIn("blocked", text)
        self.assertIn("not a network test", text)


class InternetBlockProofTests(unittest.IsolatedAsyncioTestCase):
    async def test_proof_is_exact_single_use_and_option_gated(self):
        args = {"deviceId": 7001, "command": "blockInternet"}
        cand = {"device_id": "7001"}
        off = Interaction(require_native_write_approval=True)
        self.assertFalse(off.offer_internet_block_authorization(args, cand))
        gate = Interaction(require_native_write_approval=True, auto_approve_internet_block=True)
        self.assertTrue(gate.offer_internet_block_authorization(args, cand))
        await gate.before_call("hub_call_device_command", dict(args), "")
        self.assertEqual(gate.routine_auto_approval_class, "verified_internet_block")
        changed = Interaction(require_native_write_approval=True, auto_approve_internet_block=True)
        changed.offer_internet_block_authorization(args, cand)
        task = asyncio.ensure_future(changed.before_call(
            "hub_call_device_command", {"deviceId": 7001, "command": "allowInternet"}, ""))
        await asyncio.sleep(0.05)
        self.assertIsNotNone(changed.pending)
        changed.decide(changed.pending["id"], False)
        with self.assertRaises(MCPError):
            await task


class BlockHub:
    def __init__(self):
        self.calls = []
        self.catalog = [{"name": n, "inputSchema": {"type": "object"}} for n in (
            "hub_list_devices", "hub_get_device", "hub_call_device_command")]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        from test_routine_action_fastpath import mcp_result
        self.calls.append((name, deepcopy(args)))
        if name == "hub_get_device":
            return mcp_result(block_detail())
        if name == "hub_call_device_command":
            return mcp_result({"success": True, "device": "Block Fictional-Gadget",
                               "command": args["command"], "parameters": None,
                               "state": {"internetAccess": {"value": "blocked"}}})
        raise AssertionError(name)


class InternetBlockAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_verified_block_skips_review_card_and_final_model_round(self):
        from test_routine_action_fastpath import ScriptedAgent
        hub = BlockHub()
        model = ScriptedAgent([
            tool("hub_get_device", deviceId="7001"),
            tool("hub_call_device_command", deviceId=7001, command="blockInternet"),
        ])
        gate = Interaction(require_native_write_approval=True, auto_approve_internet_block=True)
        result = await model.answer("block Fictional Gadget", [], hub, 60, before_call=gate.before_call)
        self.assertEqual(model.rounds_seen, 2)
        self.assertIsNone(gate.pending)
        self.assertEqual(gate.routine_auto_approval_class, "verified_internet_block")
        self.assertIn("block command accepted", result["answer"])
        self.assertEqual([c[0] for c in hub.calls], ["hub_get_device", "hub_call_device_command"])


class InternetBlockAfterReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_call_changed_by_prewrite_review_is_judged_as_dispatched(self):
        from test_routine_action_fastpath import ScriptedAgent
        hub = BlockHub()
        model = ScriptedAgent([
            tool("hub_get_device", deviceId="7001"),
            tool("hub_call_device_command", deviceId=7001, command="on"),   # draft: plain switch command
            tool("hub_call_device_command", deviceId=7001, command="blockInternet"),  # after review
        ])
        gate = Interaction(require_native_write_approval=True, auto_approve_internet_block=True)
        result = await model.answer("block Fictional Gadget", [], hub, 60, before_call=gate.before_call)
        self.assertTrue(result["prewrite_model_review_invoked"])
        self.assertIsNone(gate.pending)
        self.assertEqual(gate.routine_auto_approval_class, "verified_internet_block")
        self.assertEqual([c[1]["command"] for c in hub.calls if c[0] == "hub_call_device_command"],
                         ["blockInternet"])


class RoomListedBatchTests(unittest.IsolatedAsyncioTestCase):
    def _room(self):
        return previous_receipt("hub_get_room", {"roomId": "34"}, {"id": "34", "devices": [
            {"id": "5001", "label": "Fictional Hall Lamp", "accessible": True},
            {"id": "5002", "label": "Fictional Study Lamp", "accessible": True},
            {"id": "5003", "label": "(device not accessible via MCP)", "accessible": False}]})

    async def test_room_membership_names_targets_and_missing_inventory_is_read(self):
        from routine_approval_policy import (batch_light_authorization, batch_light_candidates,
                                             read_batch_light_evidence)
        from test_routine_action_fastpath import mcp_result

        class Mcp:
            def __init__(self):
                self.calls = []

            async def call(self, name, args):
                self.calls.append((name, deepcopy(args)))
                if name == "hub_get_device":
                    d = device(label="Fictional Hall Lamp" if args["deviceId"] == "5001" else "Fictional Study Lamp",
                               switch="on")
                    d["id"] = args["deviceId"]
                    d["capabilities"] = ["Switch", "Light", "SwitchLevel"]
                    d["name"] = "Dimmer"
                    return mcp_result(d)
                if name == "hub_list_devices":
                    return mcp_result({"devices": [
                        {"id": i, "label": "Fictional Hall Lamp" if i == "5001" else "Fictional Study Lamp",
                         "driver": "Matter Generic Dimmer", "protocol": "matter", "disabled": False}
                        for i in args["deviceIds"]], "count": 2, "total": 2})
                raise AssertionError(name)

        receipts = [self._room()]
        args = {"commands": [{"command": "off", "deviceId": "5001"}, {"command": "off", "deviceId": "5002"}]}
        cands = batch_light_candidates(args, receipts)
        self.assertEqual(len(cands), 2)
        mcp = Mcp()
        receipts.extend(await read_batch_light_evidence(mcp, cands, receipts, budget_seconds=6.0))
        self.assertEqual([c[0] for c in mcp.calls].count("hub_list_devices"), 1)
        self.assertTrue(batch_light_authorization(cands, receipts))

    def test_inaccessible_room_member_is_never_a_target(self):
        from routine_approval_policy import batch_light_candidates
        args = {"commands": [{"command": "off", "deviceId": "5001"}, {"command": "off", "deviceId": "5003"}]}
        self.assertIsNone(batch_light_candidates(args, [self._room()]))

    def test_reinstatement_accepts_ids_seen_in_a_room_listing_only_for_listing_reads(self):
        from action_proposal_review import reinstate_reviewed_proposal
        calls = [proposal(identifier="5001")]
        self.assertIsNotNone(reinstate_reviewed_proposal(calls, [self._room()]))
        detail_only = [previous_receipt("hub_get_device", {"deviceId": "5001"}, device())]
        detail_only[0]["response"] = '{"id":"5001"}'
        self.assertIsNone(reinstate_reviewed_proposal(calls, detail_only))


class LightHub:
    """Two Matter-style dimmers discovered through an inventory read, as in a live full-inventory search."""

    def __init__(self, state="off"):
        self.calls = []
        self.state = state
        self.catalog = [{"name": n, "inputSchema": {"type": "object"}} for n in (
            "hub_list_devices", "hub_get_device", "hub_call_device_command")]

    async def list_tools(self, refresh=False):
        return self.catalog

    def _label(self, i):
        return {"5001": "Fictional Hall Lamp", "5002": "Fictional Study Lamp"}[i]

    async def call(self, name, args):
        from test_routine_action_fastpath import mcp_result
        self.calls.append((name, deepcopy(args)))
        if name == "hub_list_devices":
            ids = args.get("deviceIds") or ["5001", "5002"]
            return mcp_result({"devices": [
                {"id": i, "label": self._label(i), "driver": "Matter Generic Dimmer", "protocol": "matter",
                 "disabled": False, "currentStates": {"switch": self.state}} for i in ids],
                "count": len(ids), "total": len(ids)})
        if name == "hub_get_device":
            d = device(label=self._label(args["deviceId"]), switch=self.state)
            d["id"] = args["deviceId"]
            d["capabilities"] = ["Switch", "Light", "SwitchLevel"]
            d["name"] = "Dimmer"
            return mcp_result(d)
        if name == "hub_call_device_command":
            if "commands" in args:
                return mcp_result({"success": True, "count": len(args["commands"]),
                                   "sentCount": len(args["commands"]), "failedCount": 0,
                                   "results": [{"deviceId": c["deviceId"], "command": c["command"], "success": True,
                                                "device": self._label(c["deviceId"]), "parameters": None}
                                               for c in args["commands"]]})
            return mcp_result({"success": True, "device": self._label(args["deviceId"]),
                               "command": args["command"], "parameters": None})
        raise AssertionError(name)


class FastLightOnOffTests(unittest.IsolatedAsyncioTestCase):
    async def test_batch_skips_review_card_and_review_rounds(self):
        from test_routine_action_fastpath import ScriptedAgent
        hub = LightHub()
        model = ScriptedAgent([
            tool("hub_list_devices", format="summary"),
            tool("hub_get_device", deviceId="5001"),
            tool("hub_get_device", deviceId="5002"),
            tool("hub_call_device_command", commands=[
                {"command": "on", "deviceId": "5001"}, {"command": "on", "deviceId": "5002"}]),
        ])
        gate = Interaction(require_native_write_approval=True, auto_approve_lights=True)
        result = await model.answer("turn on the fictional lamps", [], hub, 60, before_call=gate.before_call)
        self.assertEqual(model.rounds_seen, 4)
        self.assertFalse(result["prewrite_model_review_invoked"])
        self.assertIsNone(gate.pending)
        self.assertEqual(gate.routine_auto_approval_class, "verified_light_batch")
        self.assertIn("ON command accepted", result["answer"])
        self.assertIn("2 of 2", result["answer"])

    async def test_single_draft_from_a_listing_is_also_fast(self):
        from test_routine_action_fastpath import ScriptedAgent
        hub = LightHub()
        model = ScriptedAgent([
            tool("hub_list_devices", format="summary"),
            tool("hub_get_device", deviceId="5001"),
            tool("hub_call_device_command", deviceId="5001", command="on"),
        ])
        gate = Interaction(require_native_write_approval=True, auto_approve_lights=True)
        result = await model.answer("turn on the hall lamp please", [], hub, 60, before_call=gate.before_call)
        self.assertEqual(model.rounds_seen, 3)
        self.assertIsNone(gate.pending)
        self.assertIn("Fictional Hall Lamp", result["answer"])

    async def test_unread_id_still_needs_the_normal_path(self):
        from routine_approval_policy import batch_light_candidates
        self.assertIsNone(batch_light_candidates(
            {"commands": [{"command": "on", "deviceId": "5001"}]}, []))


class BridgeLightHub:
    """Two virtual component dimmers under a Matter bridge parent, as in the live bathroom."""

    LABELS = {"6001": "Fictional Bath One", "6002": "Fictional Bath Two"}

    def __init__(self):
        self.calls = []
        self.catalog = [{"name": n, "inputSchema": {"type": "object"}} for n in (
            "hub_list_devices", "hub_get_device", "hub_call_device_command")]

    async def list_tools(self, refresh=False):
        return self.catalog

    async def call(self, name, args):
        from test_routine_action_fastpath import mcp_result
        self.calls.append((name, deepcopy(args)))
        if name == "hub_list_devices":
            if args.get("labelFilter") == "Fictional Bridge":
                return mcp_result({"devices": [{"id": "6000", "label": "Fictional Bridge", "name": "Bridge",
                                                "driver": "Matter Advanced Bridge", "protocol": "matter",
                                                "disabled": False}],
                                   "count": 1, "total": 1, "labelFilter": "Fictional Bridge"})
            return mcp_result({"devices": [
                {"id": i, "label": label, "driver": "Generic Component Dimmer", "protocol": "virtual",
                 "parentDeviceId": "6000", "disabled": False, "currentStates": {"switch": "off"}}
                for i, label in self.LABELS.items()], "count": 2, "total": 2})
        if name == "hub_get_device":
            if args["deviceId"] == "6000":
                return mcp_result({"id": "6000", "label": "Fictional Bridge", "name": "Generic Matter Bridge",
                                   "capabilities": ["Actuator", "Battery", "HealthCheck", "Refresh", "Sensor"],
                                   "commands": [], "attributes": []})
            d = device(label=self.LABELS[args["deviceId"]], switch="off")
            d["id"] = args["deviceId"]
            d["capabilities"] = ["Actuator", "Light", "Switch", "SwitchLevel"]
            d["name"] = "Dimmer"
            return mcp_result(d)
        if name == "hub_call_device_command" and "commands" not in args:
            return mcp_result({"success": True, "device": self.LABELS[str(args["deviceId"])],
                               "command": args["command"], "parameters": None})
        if name == "hub_call_device_command":
            cmds = args["commands"]
            return mcp_result({"success": True, "count": len(cmds), "sentCount": len(cmds), "failedCount": 0,
                               "results": [{"deviceId": c["deviceId"], "command": c["command"], "success": True,
                                            "device": self.LABELS[c["deviceId"]], "parameters": None}
                                           for c in cmds]})
        raise AssertionError(name)


class BridgeBatchSingleParentReadTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_bridge_lights_read_parent_once_and_skip_card(self):
        from test_routine_action_fastpath import ScriptedAgent
        hub = BridgeLightHub()
        model = ScriptedAgent([
            tool("hub_list_devices", format="summary"),
            tool("hub_get_device", deviceId="6001"),
            tool("hub_get_device", deviceId="6002"),
            tool("hub_call_device_command", commands=[
                {"command": "on", "deviceId": "6001"}, {"command": "on", "deviceId": "6002"}]),
        ])
        gate = Interaction(require_native_write_approval=True, auto_approve_lights=True)
        result = await model.answer("turn on the fictional bath lights", [], hub, 60,
                                    before_call=gate.before_call)
        self.assertIsNone(gate.pending)
        self.assertEqual(gate.routine_auto_approval_class, "verified_light_batch")
        parent_reads = [c for c in hub.calls if c == ("hub_get_device", {"deviceId": "6000"})]
        self.assertEqual(len(parent_reads), 1)
        self.assertIn("2 of 2", result["answer"])

    def test_duplicate_identical_parent_reads_still_authorize(self):
        from routine_approval_policy import batch_light_authorization, batch_light_candidates
        import asyncio
        hub = BridgeLightHub()

        async def gather():
            from routine_component_light import _original_read_receipt
            out = []
            for name, args in [("hub_list_devices", {"format": "summary"}),
                               ("hub_get_device", {"deviceId": "6001"}),
                               ("hub_get_device", {"deviceId": "6002"})]:
                out.append(_original_read_receipt(name, args, await hub.call(name, args), 1))
                out[-1].pop("client_component_parent_verification_read")
            for _ in range(2):
                for name, args in [("hub_get_device", {"deviceId": "6000"}),
                                   ("hub_list_devices", {"format": "summary", "labelFilter": "Fictional Bridge"})]:
                    out.append(_original_read_receipt(name, args, await hub.call(name, args), 1))
            return out
        receipts = asyncio.run(gather())
        args = {"commands": [{"command": "on", "deviceId": "6001"}, {"command": "on", "deviceId": "6002"}]}
        cands = batch_light_candidates(args, receipts)
        self.assertTrue(cands)
        self.assertTrue(batch_light_authorization(cands, receipts))


class InternetSwitchOnOffTests(unittest.IsolatedAsyncioTestCase):
    def _receipts(self, declare):
        d = block_detail()
        d["commands"] += [{"name": n, "arguments": None} for n in declare]
        return [previous_receipt("hub_get_device", {"deviceId": "7001"}, d)]

    def test_off_and_on_qualify_only_when_the_device_declares_them(self):
        from routine_approval_policy import internet_block_candidate
        self.assertIsNone(internet_block_candidate({"deviceId": "7001", "command": "off"}, self._receipts([])))
        both = self._receipts(["on", "off"])
        for command in ("on", "off"):
            self.assertIsNotNone(internet_block_candidate({"deviceId": "7001", "command": command}, both))

    def test_a_switch_without_its_own_ip_and_mac_never_qualifies(self):
        from routine_approval_policy import internet_block_candidate
        d = block_detail(with_ip=False)
        d["commands"] += [{"name": "off", "arguments": None}]
        receipts = [previous_receipt("hub_get_device", {"deviceId": "7001"}, d)]
        self.assertIsNone(internet_block_candidate({"deviceId": "7001", "command": "off"}, receipts))

    async def test_off_on_a_declared_block_switch_runs_without_a_card(self):
        from test_routine_action_fastpath import ScriptedAgent

        class OffHub(BlockHub):
            async def call(self, name, args):
                if name == "hub_get_device":
                    from test_routine_action_fastpath import mcp_result
                    self.calls.append((name, deepcopy(args)))
                    d = block_detail()
                    d["commands"] += [{"name": "off", "arguments": None}]
                    return mcp_result(d)
                return await super().call(name, args)

        hub = OffHub()
        model = ScriptedAgent([
            tool("hub_get_device", deviceId="7001"),
            tool("hub_call_device_command", deviceId="7001", command="off"),
        ])
        gate = Interaction(require_native_write_approval=True, auto_approve_lights=True,\
                           auto_approve_internet_block=True)
        result = await model.answer("block Fictional Gadget", [], hub, 60, before_call=gate.before_call)
        self.assertIsNone(gate.pending)
        self.assertEqual(gate.routine_auto_approval_class, "verified_internet_block")
        self.assertIn("block command accepted", result["answer"])


class UndeclaredConfirmAndExtraReadTests(unittest.IsolatedAsyncioTestCase):
    def test_confirm_is_dropped_only_when_the_live_schema_omits_it(self):
        from agent import drop_undeclared_confirm
        declared = [{"name": "hub_call_device_command", "inputSchema": {
            "type": "object", "properties": {"deviceId": {}, "command": {}}}}]
        calls = tool("hub_call_device_command", deviceId=1, command="off", confirm="True")["tool_calls"]
        self.assertEqual(drop_undeclared_confirm(calls, declared), 1)
        self.assertEqual(calls[0]["function"]["arguments"], {"deviceId": 1, "command": "off"})
        keeps = [{"name": "hub_manage_x", "inputSchema": {
            "type": "object", "properties": {"confirm": {}, "a": {}}}}]
        kept = tool("hub_manage_x", a=1, confirm=True)["tool_calls"]
        self.assertEqual(drop_undeclared_confirm(kept, keeps), 0)
        self.assertEqual(kept[0]["function"]["arguments"], {"a": 1, "confirm": True})
        unknown = tool("hub_call_device_command", deviceId=1, command="off", confirm=True)["tool_calls"]
        self.assertEqual(drop_undeclared_confirm(unknown, [{"name": "hub_call_device_command"}]), 0)

    async def test_block_with_invented_confirm_runs_without_a_card(self):
        from test_routine_action_fastpath import ScriptedAgent

        class Hub(BlockHub):
            def __init__(self):
                super().__init__()
                self.catalog[2]["inputSchema"] = {"type": "object", "properties": {
                    "deviceId": {}, "command": {}, "parameters": {}}}

            async def call(self, name, args):
                if name == "hub_call_device_command":
                    assert "confirm" not in args, args
                if name == "hub_get_device":
                    from test_routine_action_fastpath import mcp_result
                    self.calls.append((name, deepcopy(args)))
                    d = block_detail()
                    d["commands"] += [{"name": "off", "arguments": None}]
                    return mcp_result(d)
                return await super().call(name, args)

        hub = Hub()
        model = ScriptedAgent([
            tool("hub_get_device", deviceId="7001", mode="summary"),
            tool("hub_call_device_command", deviceId=7001, command="off", confirm="True"),
        ])
        gate = Interaction(require_native_write_approval=True, auto_approve_lights=True,
                           auto_approve_internet_block=True)
        result = await model.answer("block Fictional Gadget", [], hub, 60, before_call=gate.before_call)
        self.assertIsNone(gate.pending)
        self.assertEqual(gate.routine_auto_approval_class, "verified_internet_block")
        self.assertIn("block command accepted", result["answer"])

    def test_an_extra_configuration_read_does_not_disqualify_the_device(self):
        from routine_approval_policy import internet_block_candidate
        d = block_detail()
        d["commands"] += [{"name": "on", "arguments": None}]
        receipts = [previous_receipt("hub_get_device", {"deviceId": "7001"}, d),
                    previous_receipt("hub_get_device", {"deviceId": "7001", "mode": "configuration"},
                                     {"id": "7001", "editableFields": []})]
        self.assertIsNotNone(internet_block_candidate({"deviceId": "7001", "command": "on"}, receipts))
        twice = receipts[:1] + [previous_receipt("hub_get_device", {"deviceId": "7001", "mode": "summary"}, d)]
        self.assertIsNone(internet_block_candidate({"deviceId": "7001", "command": "on"}, twice))


class ClientReadsBlockEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_command_after_a_label_search_needs_no_model_detail_read(self):
        from test_routine_action_fastpath import ScriptedAgent, mcp_result

        class Hub(BlockHub):
            async def call(self, name, args):
                if name == "hub_list_devices":
                    self.calls.append((name, deepcopy(args)))
                    return mcp_result({"devices": [{"id": "7001", "label": "Block Fictional-Gadget"}],
                                       "count": 1, "total": 1})
                if name == "hub_get_device":
                    self.calls.append((name, deepcopy(args)))
                    d = block_detail()
                    d["commands"] += [{"name": "on", "arguments": None}, {"name": "off", "arguments": None}]
                    return mcp_result(d)
                return await super().call(name, args)

        hub = Hub()
        model = ScriptedAgent([
            tool("hub_list_devices", labelFilter="gadget"),
            tool("hub_call_device_command", deviceId=7001, command="off"),
        ])
        gate = Interaction(require_native_write_approval=True, auto_approve_lights=True,
                           auto_approve_internet_block=True)
        result = await model.answer("block gadget", [], hub, 60, before_call=gate.before_call)
        self.assertIsNone(gate.pending)
        self.assertEqual(gate.routine_auto_approval_class, "verified_internet_block")
        self.assertEqual(model.rounds_seen, 2)
        self.assertEqual([c[0] for c in hub.calls],
                         ["hub_list_devices", "hub_get_device", "hub_call_device_command"])
        self.assertEqual(hub.calls[1][1], {"deviceId": "7001", "mode": "summary"})
        self.assertIn("block command accepted", result["answer"])

    async def test_unqualified_device_still_gets_a_card_after_the_client_read(self):
        from test_routine_action_fastpath import ScriptedAgent, mcp_result

        class Hub(BlockHub):
            async def call(self, name, args):
                if name == "hub_get_device":
                    self.calls.append((name, deepcopy(args)))
                    return mcp_result(block_detail(with_ip=False))
                return await super().call(name, args)

        hub = Hub()
        model = ScriptedAgent([tool("hub_call_device_command", deviceId=7001, command="blockInternet"),
                               tool("hub_call_device_command", deviceId=7001, command="blockInternet")])
        gate = Interaction(require_native_write_approval=True, auto_approve_internet_block=True)
        task = asyncio.ensure_future(
            model.answer("block gadget", [], hub, 30, before_call=gate.before_call))
        for _ in range(200):
            if gate.pending or task.done():
                break
            await asyncio.sleep(0.02)
        self.assertIsNotNone(gate.pending)
        self.assertEqual(hub.calls[0][0], "hub_get_device")
        task.cancel()
        try:
            await task
        except BaseException:
            pass


class BootstrapParentReadOnceTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_bridge_light_reads_its_parent_once(self):
        from test_routine_action_fastpath import ScriptedAgent, mcp_result

        class Hub(BridgeLightHub):
            LABELS = {"6001": "Hallway Light 1", "6002": "Hallway Light 2"}

            async def call(self, name, args):
                if name == "hub_list_devices" and args.get("labelFilter") == "hallway light 1":
                    self.calls.append((name, deepcopy(args)))
                    return mcp_result({"devices": [{
                        "id": "6001", "label": "Hallway Light 1", "name": "LWA018", "room": "Hallway",
                        "driver": "Generic Component Dimmer", "protocol": "virtual",
                        "parentDeviceId": "6000", "disabled": False, "deviceNetworkId": "M1-15",
                        "currentStates": {"switch": "off", "level": "30"}}],
                        "count": 1, "total": 1, "labelFilter": "hallway light 1"})
                return await super().call(name, args)

        hub = Hub()
        model = ScriptedAgent([tool("hub_call_device_command", deviceId=6001, command="on")])
        gate = Interaction(require_native_write_approval=True, auto_approve_lights=True)
        await model.answer("turn on hallway light 1", [], hub, 60, before_call=gate.before_call,
                           enable_routine_bootstrap=True)
        self.assertIsNone(gate.pending)
        self.assertEqual(gate.routine_auto_approval_class, "verified_light_batch")
        self.assertEqual(len([c for c in hub.calls if c == ("hub_get_device", {"deviceId": "6000"})]), 1)


class PromptGuidanceTests(unittest.TestCase):
    def test_prompt_forbids_extra_arguments_on_device_commands(self):
        import agent
        text = agent.SYSTEM_PROMPT if hasattr(agent, "SYSTEM_PROMPT") else Path(agent.__file__).read_text()
        self.assertIn("never add confirm or any other argument to it", text)
        self.assertIn("Do not read the device detail", text)

    def test_prompt_covers_room_wide_lights_and_hyphenated_switch_labels(self):
        import agent
        text = agent.SYSTEM_PROMPT if hasattr(agent, "SYSTEM_PROMPT") else Path(agent.__file__).read_text()
        self.assertIn("roomFilter set to the room and capabilityFilter \"Light\"", text)
        self.assertIn("a \"Shower Light\" in the Bathroom", text)
        self.assertIn("retry once with the hyphenated form", text)

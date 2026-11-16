"""Alpha.126 generic outcome-first causal review tests.

All observations are FICTIONAL, with no live network, cloud model or actuator.
One uninspected primary output versus observed zone-idle history exercises
cross-device evidence scope without subsystem-specific routing.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent, _SKILL
from causal_outcome_frontier import (
    causal_outcome_frontier, should_prompt_outcome_first_review,
    OUTCOME_FIRST_CHECKPOINT,
)
from investigation_review import (
    should_prompt_outcome_history_gap, SOURCE_REVIEW_PROMPT,
    FINAL_CLAIM_AUDIT_PROMPT,
)


def wrapped(native):
    return json.dumps({"content": [{"type": "text", "text": json.dumps(native)}]})


INVENTORY = {"devices": [
    {"id": "FIX-ZONE", "label": "Fixture Zone A", "currentStates": {
        "thermostatOperatingState": "idle"}},
    {"id": "FIX-OUTPUT", "label": "Fixture Primary Output", "currentStates": {
        "thermostatOperatingState": "idle"}},
    {"id": "FIX-AUX", "label": "Fixture Auxiliary Input", "currentStates": {
        "temperature": "22"}},
], "count": 3}
ZONE_EVENTS = {"source": "device", "deviceId": "FIX-ZONE",
               "attributeFilter": "thermostatOperatingState", "events": [
    {"name": "thermostatOperatingState", "value": "idle",
     "date": "2030-11-16T08:30:00+0000", "isStateChange": True},
    {"name": "thermostatOperatingState", "value": "idle",
     "date": "2030-11-16T11:30:00+0000", "isStateChange": True},
]}
PRIMARY_EVENTS = {"source": "device", "deviceId": "FIX-OUTPUT",
                  "attributeFilter": "thermostatOperatingState", "events": [
    {"name": "thermostatOperatingState", "value": "heating",
     "date": "2030-11-16T11:32:35+0000", "isStateChange": True,
     "producedBy": {"deviceId": "FIX-OUTPUT", "name": "Fixture output"}},
    {"name": "thermostatOperatingState", "value": "idle",
     "date": "2030-11-16T11:45:35+0000", "isStateChange": True,
     "producedBy": {"deviceId": "FIX-OUTPUT", "name": "Fixture output"}},
]}


def original_receipt(name, arguments, payload, success=True):
    return {
        "name": name, "arguments": arguments, "success": success,
        "response": wrapped(payload),
    }


def tool_call(name, args):
    return {"content": "", "tool_calls": [{"function": {
        "name": name, "arguments": args,
    }}]}


class OutcomeFrontierTests(unittest.TestCase):
    def setUp(self):
        self.inventory = original_receipt(
            "hub_list_devices", {"capabilityFilter": "Thermostat"}, INVENTORY)
        self.zone = original_receipt("hub_list_device_events",
                                     {"deviceId": "FIX-ZONE",
                                      "attribute": "thermostatOperatingState",
                                      "hoursBack": 6}, ZONE_EVENTS)

    def test_uninspected_controlled_output_not_excluded_by_zone_idle(self):
        before = json.dumps([self.inventory, self.zone], sort_keys=True)
        found = causal_outcome_frontier([self.inventory, self.zone])
        self.assertEqual(found["focused_inventory_device_count"], 3)
        self.assertEqual(found["successful_device_history_target_count"], 1)
        self.assertEqual(found["device_history_scopes"][0]["device_id"], "FIX-ZONE")
        self.assertEqual(found["device_history_scopes"][0]["observed_state_fields"], [
            {"field": "thermostatOperatingState",
             "returned_value_counts": {"idle": 2}}])
        self.assertEqual(
            set(x["device_id"] for x in found["focused_inventory_members_without_history"]),
            {"FIX-OUTPUT", "FIX-AUX"})
        self.assertTrue(found["other_device_idle_does_not_rule_out_focal_outcome"])
        self.assertTrue(found["history_not_read_does_not_mean_event_absent"])
        self.assertEqual(before, json.dumps([self.inventory, self.zone], sort_keys=True))

    def test_outcome_receipt_alters_scope_but_never_supplies_auto_cause(self):
        output = original_receipt("hub_list_device_events", {
            "deviceId": "FIX-OUTPUT", "attribute": "thermostatOperatingState",
            "hoursBack": 6}, PRIMARY_EVENTS)
        found = causal_outcome_frontier([output, self.inventory, self.zone])
        self.assertEqual(found["successful_device_history_target_count"], 2)
        self.assertEqual(found["unread_focused_inventory_member_count"], 1)
        self.assertEqual(found["focused_inventory_members_without_history"][0][
            "device_id"], "FIX-AUX")
        self.assertTrue(found["frontier_does_not_verify_or_deny_user_event"])
        self.assertNotIn("caused_by", found)
        self.assertEqual(next(x for x in found["device_history_scopes"]
                              if x["device_id"] == "FIX-OUTPUT")[
            "observed_state_fields"][0]["returned_value_counts"],
            {"heating": 1, "idle": 1})

    def test_scope_is_non_exhaustive_and_unfiltered_location_is_not_device(self):
        many = original_receipt("hub_list_devices", {}, {
            "devices": [
                {"id": str(i), "label": "Fictional Device " + str(i)}
                for i in range(100)
            ]})
        loc = original_receipt("hub_list_device_events", {"hoursBack": 2}, {
            "source": "location", "events": [
                {"name": "mode", "value": "Afternoon",
                 "date": "2030-11-16T12:00:00+0000"}]})
        failed = {**self.zone, "success": False}
        found = causal_outcome_frontier([many, loc, failed])
        self.assertEqual(found["focused_inventory_device_count"], 0)
        self.assertEqual(found["successful_device_history_target_count"], 0)
        self.assertEqual(found["unread_focused_inventory_member_count"], 0)
        self.assertEqual(found["broad_or_oversized_inventories_not_enumerated"], 1)

    def test_general_review_conditions_and_no_read_guard(self):
        found = causal_outcome_frontier([self.zone, self.inventory])
        yes = dict(review_kind_name="causal", source_frontier=found,
                   candidate_answer='The device did not "turn on" this morning.')
        self.assertTrue(should_prompt_outcome_history_gap(
            "Why did the fictional system turn on?", **yes))
        self.assertFalse(should_prompt_outcome_history_gap(
            "Why did the fictional system turn on? Do not make any new tool calls.",
            **yes))
        self.assertFalse(should_prompt_outcome_history_gap(
            "Turn on the fictional system and explain why.", **yes))
        self.assertFalse(should_prompt_outcome_history_gap(
            "Why did the fictional system turn on?",
            **{**yes, "has_action_receipt": True}))
        self.assertFalse(should_prompt_outcome_first_review(
            "Why did the fictional system turn on?", **{
                **yes, "no_new_reads": True}))
        self.assertFalse(should_prompt_outcome_history_gap(
            "Why did the fictional system turn on?",
            **{**yes, "review_kind_name": "current_state"}))
        self.assertIn("controlled output", OUTCOME_FIRST_CHECKPOINT)
        self.assertIn("categorical", OUTCOME_FIRST_CHECKPOINT)
        self.assertIn("actual controlled output/device", SOURCE_REVIEW_PROMPT)
        self.assertIn("categorical", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("historical", _SKILL.lower())
        for forbidden in ("Bedroom 3", "3970", "4382", "Hallway Light 1"):
            self.assertNotIn(forbidden, OUTCOME_FIRST_CHECKPOINT)


class FictionalMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_list_devices", "description": "Read fixture inventory",
             "inputSchema": {"type": "object", "properties": {
                 "capabilityFilter": {"type": "string"}}}},
            {"name": "hub_list_device_events",
             "description": "Read exact fictional device events",
             "inputSchema": {"type": "object", "properties": {
                 "deviceId": {"type": "string"},
                 "attribute": {"type": "string"},
                 "hoursBack": {"type": "integer"}}}},
            {"name": "hub_manage_devices", "description": "Unsafe write gateway",
             "inputSchema": {"type": "object", "properties": {}}},
        ]

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_list_devices":
            return json.loads(wrapped(INVENTORY))
        if name == "hub_list_device_events":
            if args.get("deviceId") == "FIX-ZONE":
                return json.loads(wrapped(ZONE_EVENTS))
            if args.get("deviceId") == "FIX-OUTPUT":
                return json.loads(wrapped(PRIMARY_EVENTS))
        raise AssertionError("No unoffered source or write may occur")


class ScriptedAgent(Agent):
    def __init__(self, *replies):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 20)
        self.replies = list(replies)
        self.snapshots = []
        self.offered = []

    async def round(self, messages, tools, remaining):
        self.snapshots.append([dict(m) for m in messages])
        self.offered.append([t["function"]["name"] for t in tools])
        if not self.replies:
            raise AssertionError("Unexpected model round")
        return self.replies.pop(0)


class ModelLedOutcomeFollowThroughTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_can_choose_missing_focal_history_in_existing_review(self):
        inv_args = {"capabilityFilter": "Thermostat"}
        zone_args = {"deviceId": "FIX-ZONE",
                     "attribute": "thermostatOperatingState", "hoursBack": 6}
        out_args = {"deviceId": "FIX-OUTPUT",
                    "attribute": "thermostatOperatingState", "hoursBack": 6}
        agent = ScriptedAgent(
            tool_call("hub_list_devices", inv_args),
            tool_call("hub_list_device_events", zone_args),
            {"content": "The fictional system did not turn on. Zone remained idle."},
            tool_call("hub_list_device_events", out_args),
            {"content": "The primary output reported heating at 11:32:35 "
                        "and later idle; why the controller decided to activate "
                        "is not established by the returned receipts."},
        )
        hub = FictionalMCP()
        try:
            result = await agent.answer(
                "Why did the fictional system start earlier? Do not change anything.",
                [], hub, 90, enable_final_claim_audit=False,
                enable_causal_follow_through=False,
            )
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(result["source_review_kind"], "causal")
        self.assertEqual(result["rounds"], 5)
        self.assertEqual(hub.calls, [
            ("hub_list_devices", inv_args),
            ("hub_list_device_events", zone_args),
            ("hub_list_device_events", out_args),
        ])
        self.assertIn("Outcome-first causal evidence checkpoint",
                      agent.snapshots[3][-1]["content"])
        self.assertIn("FIX-OUTPUT", agent.snapshots[3][-1]["content"])
        self.assertNotIn("hub_manage_devices", agent.offered[3])
        self.assertIn("reported heating", result["answer"])
        self.assertEqual(result["causal_outcome_source_frontier"][
            "successful_device_history_target_count"], 2)

    async def test_model_may_decline_more_reads_no_host_route(self):
        inv_args = {"capabilityFilter": "Thermostat"}
        zone_args = {"deviceId": "FIX-ZONE",
                     "attribute": "thermostatOperatingState", "hoursBack": 6}
        agent = ScriptedAgent(
            tool_call("hub_list_devices", inv_args),
            tool_call("hub_list_device_events", zone_args),
            {"content": "The historic output remains unverified."},
            {"content": "Only a zone's idle reports were read. The actual "
                        "output's historical state remains unverified."},
        )
        hub = FictionalMCP()
        try:
            result = await agent.answer(
                "Why did the fictional system turn on? Do not change anything.",
                [], hub, 90, enable_final_claim_audit=False,
                enable_causal_follow_through=False,
            )
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"], 4)
        self.assertEqual(len(hub.calls), 2)
        self.assertEqual(result["causal_outcome_source_frontier"][
            "successful_device_history_target_count"], 1)
        self.assertIn("unverified", result["answer"])


if __name__ == "__main__":
    unittest.main()

"""Alpha.141: source-scope causal ceiling, not phrase-trigger scoring.

Cross-domain fictional original MCP receipts only; no hub, provider, native
write, household IDs, invented decisions, or live-model benchmark result.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from causal_claim_publication import (
    causal_original_source_ceiling, causal_publication_floor,
)


def receipt(tool, args, native, *, success=True):
    return {
        "name": tool, "arguments": args, "success": success,
        "result_kind": "tool_result",
        "response": json.dumps({"content": [{
            "type": "text", "text": json.dumps(native)
        }]}),
    }


def event(field, value, time, **extra):
    return {"name": field, "value": value, "date": time, **extra}


def state_history(device, field, states):
    return receipt("hub_list_device_events",
                   {"deviceId": device, "attribute": field, "limit": 20},
                   {"source": "device", "deviceId": device,
                    "device": "Fixture Output " + device,
                    "events": states})


T0 = "2030-11-17T07:58:28.820+00:00"
T1 = "2030-11-17T07:58:47.423+00:00"
T2 = "2030-11-17T08:00:49.222+00:00"
APP_ID = "613"


def reported_output_history(device="FX-HEAT"):
    return state_history(device, "thermostatOperatingState", [
        event("thermostatOperatingState", "idle", T2,
              producedBy={"deviceId": "FX-BRIDGE"},
              triggered=[{"appId": 13}]),
        event("thermostatOperatingState", "heating", T1,
              producedBy={"deviceId": "FX-BRIDGE"},
              triggered=[{"appId": 13}]),
    ])


def setpoint_history():
    return state_history("FX-HEAT", "heatingSetpoint", [
        event("heatingSetpoint", "22", T0,
              producedBy={"appId": int(APP_ID)}),
        event("heatingSetpoint", "12", "2030-11-17T07:20:00+00:00",
              producedBy={"appId": int(APP_ID)}),
    ])


def command_history(field="switch", device="FX-LAMP"):
    return state_history(device, field, [
        event(field, "off", T1, type="event",
              producedBy={"deviceId": "FX-BRIDGE"}),
        event("command-off", None, T0, type="command",
              producedBy={"appId": int(APP_ID)}),
    ])


def app_log():
    return receipt(
        "hub_get_logs", {"appId": APP_ID, "mode": "past",
                         "since": "2030-11-17T07:45:00+00:00",
                         "until": "2030-11-17T08:05:00+00:00"},
        {"mode": "past", "entries": [
            {"type": "app", "time": "2030-11-17 07:58:28.809",
             "message": "app|613|Fixture controller|Input A demand reported"}
        ]},
    )


class CausalCeilingTests(unittest.TestCase):
    def test_confident_grouping_is_not_event_time_input_proof(self):
        observed = [
            state_history("FX-TRV-A", "thermostatOperatingState", [
                event("thermostatOperatingState", "idle", T2)]),
            state_history("FX-TRV-B", "thermostatOperatingState", [
                event("thermostatOperatingState", "idle", T1)]),
            setpoint_history(),
            receipt("hub_get_device", {"deviceId": "FX-HEAT"},
                    {"id": "FX-HEAT", "room": "Fixture thermostat group",
                     "currentStates": {"temperature": 20, "thermostatMode": "heat"}}),
        ]
        before = deepcopy(observed)
        ceiling = causal_original_source_ceiling(observed)
        self.assertFalse(ceiling["two_distinct_reported_states_same_output"])
        self.assertFalse(ceiling[
            "minimum_source_categories_for_unrestricted_causal_prose"])
        self.assertFalse(ceiling["cause_or_upstream_input_verified_by_this_index"])
        self.assertEqual(causal_publication_floor(
            "Why did the heater turn on and which zone requested it?",
            "The zone was the device group. The current temperature "
            "tells us it was the historical initiator.", observed
        )["reason"], "original_event_time_causal_sources_insufficient")
        self.assertEqual(observed, before)

    def test_state_only_with_a_reported_transition_is_still_not_cause(self):
        x = causal_original_source_ceiling([reported_output_history()])
        self.assertTrue(x["two_distinct_reported_states_same_output"])
        self.assertFalse(x["recorded_app_command_on_reported_output"])
        self.assertFalse(x["minimum_source_categories_for_unrestricted_causal_prose"])

    def test_recorded_command_and_report_same_device_preserve_proximal_source(self):
        x = causal_original_source_ceiling([command_history()])
        self.assertTrue(x["recorded_app_command_on_reported_output"])
        self.assertTrue(x["minimum_source_categories_for_unrestricted_causal_prose"])
        self.assertFalse(x["cause_or_upstream_input_verified_by_this_index"])
        self.assertEqual(causal_publication_floor(
            "Why did the fixture lamp go off?",
            "An original command-off row identifies app 613 as the recorded "
            "issuer, but its internal trigger remains unknown.",
            [command_history()],
        )["status"], "passed")

    def test_related_execution_source_plus_output_reports_is_source_opportunity(self):
        sources = [reported_output_history(), setpoint_history(), app_log()]
        x = causal_original_source_ceiling(sources)
        self.assertTrue(x["related_app_execution_source_category"])
        self.assertTrue(x["minimum_source_categories_for_unrestricted_causal_prose"])
        self.assertFalse(x["cause_or_upstream_input_verified_by_this_index"])

    def test_listener_wrong_source_failed_log_and_numeric_only_do_not_pass(self):
        base = [reported_output_history(), setpoint_history()]
        cases = [
            [],
            [receipt("hub_get_logs", {"appId": "13", "mode": "past"},
                     {"mode": "past", "entries": [{"type": "app", "message":
                        "app|13|Observer|Listening"}]})],
            [receipt("hub_get_logs", {"appId": "999", "mode": "past"},
                     {"mode": "past", "entries": [{"type": "app", "message":
                        "app|999|Unrelated|Ran"}]})],
            [{**app_log(), "success": False}],
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                self.assertFalse(causal_original_source_ceiling(
                    base + extra
                )["minimum_source_categories_for_unrestricted_causal_prose"])


class FakeHub:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_list_device_events", "inputSchema": {
                "type": "object", "properties": {
                    "deviceId": {"type": "string"},
                    "attribute": {"type": "string"},
                    "limit": {"type": "integer"}}}},
            {"name": "hub_get_logs", "inputSchema": {
                "type": "object", "properties": {
                    "appId": {"type": "string"}, "mode": {"type": "string"},
                    "since": {"type": "string"}, "until": {"type": "string"}}}},
        ]

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_list_device_events":
            if args.get("attribute") == "heatingSetpoint":
                src = setpoint_history()
            else:
                src = reported_output_history()
            return json.loads(src["response"])
        if name == "hub_get_logs":
            return json.loads(app_log()["response"])
        raise AssertionError("unexpected or native write call")


def call(tool, args):
    return {"content": "", "tool_calls": [
        {"function": {"name": tool, "arguments": args}}]}


class FakeModel(Agent):
    def __init__(self, *replies):
        super().__init__("http://127.0.0.1:11434", "fixture", "", 20)
        self.replies = list(replies)
        self.seen = []

    async def round(self, messages, tools, remaining):
        self.seen.append([dict(item) for item in messages])
        if not self.replies:
            raise AssertionError("unexpected additional model round")
        return self.replies.pop(0)


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_confident_wrong_input_triggers_review_then_source_ceiling(self):
        hub = FakeHub()
        model = FakeModel(
            call("hub_list_device_events",
                 {"deviceId": "FX-HEAT", "attribute": "heatingSetpoint"}),
            {"content": "The fixture output changed its setpoint."},
            {"content": "The initiating room was the fixture grouping."},
            {"content": "The room was the group, based on current status."},
        )
        try:
            answer = await model.answer(
                "Why did the fixture heating start and which zone demanded it? "
                "Do not change anything.",
                [], hub, 120, enable_final_claim_audit=False,
            )
        finally:
            await model.close()
        self.assertTrue(answer["causal_follow_through_invoked"])
        self.assertEqual(answer["rounds"], 4)
        self.assertEqual(answer["causal_claim_verification"]["reason"],
                         "original_event_time_causal_sources_insufficient")
        self.assertEqual(answer["answer_fallback_status"],
                         "causal_claim_publication_floor")
        self.assertNotIn("initiating room was", answer["answer"])
        self.assertNotIn("room was the group", answer["answer"])
        self.assertFalse(answer["action_lifecycle"]["native_write_submitted"])
        self.assertEqual(len(hub.calls), 1)
        self.assertIn("Original causal source ceiling",
                      model.seen[3][-1]["content"])

    async def test_model_may_select_its_own_event_time_read(self):
        hub = FakeHub()
        model = FakeModel(
            call("hub_list_device_events",
                 {"deviceId": "FX-HEAT",
                  "attribute": "thermostatOperatingState"}),
            {"content": "The fixture reported heating."},
            {"content": "A confident unsupported cause."},
            call("hub_list_device_events",
                 {"deviceId": "FX-HEAT", "attribute": "heatingSetpoint"}),
            call("hub_get_logs",
                 {"appId": APP_ID, "mode": "past",
                  "since": "2030-11-17T07:45:00+00:00",
                  "until": "2030-11-17T08:05:00+00:00"}),
            {"content": "The output reported heating, and an application log "
                        "was returned. The source does not independently "
                        "verify the physical effect or precise upstream input."},
        )
        try:
            answer = await model.answer(
                "Why did the fixture output report heating, and which input requested it? Do not change anything.",
                [], hub, 120, enable_final_claim_audit=False,
            )
        finally:
            await model.close()
        self.assertEqual(answer["causal_claim_verification"]["status"], "passed")
        self.assertTrue(answer["causal_original_source_ceiling"][
            "minimum_source_categories_for_unrestricted_causal_prose"])
        self.assertEqual([n for n, _ in hub.calls],
                         ["hub_list_device_events", "hub_list_device_events",
                          "hub_get_logs"])
        self.assertFalse(answer["action_lifecycle"]["native_write_submitted"])


if __name__ == "__main__":
    unittest.main()

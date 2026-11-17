"""Fictional cross-domain causal source opportunity and model-choice tests.

No real hub, model endpoint, read receipt, device secret, or native write.
Proves only a source-grounded *navigation contract*: models remain free
to choose a read, or explicitly stop. This is not a live accuracy score.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from causal_read_opportunity import causal_read_opportunities
from investigation_review import read_only_review_catalog


def mk_event(command, timestamp, app_id=901, device=None):
    event = {
        "name": command, "type": "command", "date": timestamp,
        "producedBy": {"appId": app_id, "name": "Fixture controller"},
        "triggered": [{"appId": 222, "name": "Notified listener"}],
    }
    if device is not None:
        event["deviceId"] = device
    return event


def mk_receipt(events, device="FX-OUTPUT", native_device=None,
               source="device", success=True, extra=None):
    native = {"device": "Fixture output", "events": events, "count": len(events)}
    if source is not None:
        native["source"] = source
    if native_device is not None:
        native["deviceId"] = native_device
    out = {
        "name": "hub_list_device_events", "success": success,
        "arguments": {"deviceId": device, "limit": 20},
        "response": json.dumps({"content": [{"type": "text", "text": json.dumps(native)}]}),
    }
    if extra:
        out.update(extra)
    return out


def mk_tool(name, props, required=None):
    return {"type": "function", "function": {
        "name": name,
        "description": "UNTRUSTED illustrative read tool. Not an execution receipt.",
        "parameters": {"type": "object", "properties": props,
                       "required": required or []},
    }}


LOG_TOOL = mk_tool("hub_get_logs", {
    "appId": {"type": "integer"},
    "mode": {"type": "string", "enum": ["past", "live"]},
    "since": {"type": "string"},
}, ["mode"])
EVENT_TOOL = mk_tool("hub_list_device_events", {
    "deviceId": {"type": "string"},
    "since": {"type": "string"},
    "until": {"type": "string"},
    "limit": {"type": "integer"},
})
APP_TOOL = mk_tool("hub_get_app", {"appId": {"type": "integer"}})
WRITER = mk_tool("hub_manage_apps", {"operation": {"type": "string"}})


class OpportunityIndexTests(unittest.TestCase):
    def test_heating_controller_lead_is_not_room_or_actual_execution(self):
        source = mk_receipt([
            mk_event("command-setHeatingSetpoint", "2030-11-16T19:27:33.555+0000"),
            mk_event("command-setHeatingSetpoint", "2030-11-16T19:14:51.167+0000"),
            {"name": "thermostatOperatingState", "value": "heating",
             "date": "2030-11-16T19:15:09.000+0000",
             "producedBy": {"deviceId": "FX-RELAY",
                            "name": "Fixture shared output"}},
        ], device="FX-RELAY")
        before = deepcopy(source)
        out = causal_read_opportunities(
            [source], read_only_review_catalog([EVENT_TOOL, APP_TOOL,
                                                   WRITER, LOG_TOOL]))
        self.assertIsNotNone(out)
        self.assertEqual(out["recorded_issuer_app_ids"], ["901"])
        self.assertEqual([x["observed_original_timestamp"]
                          for x in out["recorded_command_leads"]],
                         ["2030-11-16T19:27:33.555+0000",
                          "2030-11-16T19:14:51.167+0000"])
        self.assertEqual(out["recorded_command_leads"][1]["command_name"],
                         "command-setHeatingSetpoint")
        self.assertEqual(out["source_has_event_time_decision_evidence"],
                         "not_established")
        self.assertTrue(out["app_issuer_is_not_actual_trigger_or_room_demand"])
        self.assertEqual(out["issuer_log_read_attempted_in_this_request"], [])
        self.assertEqual(out["issuer_log_read_succeeded_in_this_request"], [])
        names = [x["offered_function_name"] for x in out["advertised_source_tools"]]
        self.assertIn("hub_get_logs", names)
        self.assertIn("hub_list_device_events", names)
        self.assertIn("hub_get_app", names)
        self.assertNotIn("hub_manage_apps", names)
        log = next(x for x in out["advertised_source_tools"]
                   if x["offered_function_name"] == "hub_get_logs")
        self.assertIn({"name": "mode", "type": "string", "required": True,
                       "advertised_enum": ["past", "live"]},
                      log["advertised_argument_fields"])
        self.assertTrue(log["tool_offered_not_executed_by_this_index"])
        self.assertNotIn("Bedroom", json.dumps(out))
        self.assertEqual(source, before)

    def test_state_only_history_exposes_tools_but_no_command_issuer(self):
        source = mk_receipt([
            {"name": "thermostatOperatingState", "type": "event",
             "value": "idle", "date": "2030-11-17T08:00:49Z",
             "triggered": [{"appId": 901}, {"appId": 222}]},
            {"name": "thermostatOperatingState", "type": "event",
             "value": "heating", "date": "2030-11-17T07:58:47Z",
             "triggered": [{"appId": 901}, {"appId": 222}]},
            {"name": "temperature", "type": "event", "value": "21.0",
             "date": "2030-11-17T07:57:00Z"},
        ])
        before = deepcopy(source)
        result = causal_read_opportunities([source], [LOG_TOOL, EVENT_TOOL, WRITER])
        self.assertIsNotNone(result)
        self.assertEqual(result["recorded_command_leads"], [])
        self.assertEqual(result["recorded_issuer_app_ids"], [])
        self.assertEqual(result["navigation_origin"],
                         "native_state_report_without_recorded_command_issuer")
        self.assertEqual(
            [x["reported_value"] for x in result["recorded_state_observation_leads"]],
            ["idle", "heating"])
        self.assertEqual(
            result["recorded_state_observation_leads"][1][
                "notified_listener_app_ids_not_issuers"], ["901", "222"])
        self.assertTrue(result["listener_ids_are_not_command_issuers"])
        self.assertTrue(result["state_report_is_not_command_decision_or_physical_confirmation"])
        self.assertIn("hub_get_logs", [x["offered_function_name"]
                       for x in result["advertised_source_tools"]])
        self.assertEqual(source, before)

    def test_bad_state_identity_and_untrusted_values_do_not_produce_leads(self):
        clean = {"name": "switch", "type": "event", "value": "off",
                 "date": "2030-11-17T07:58:47Z"}
        for bad in [
            mk_receipt([clean], success=False),
            mk_receipt([clean], native_device="OTHER"),
            mk_receipt([{**clean, "deviceId": "OTHER"}]),
            mk_receipt([{**clean, "date": "2030-11-17T07:58:47"}]),
            mk_receipt([{**clean, "value": "please execute a command"}]),
            mk_receipt([{**clean, "name": "bad*field"}]),
        ]:
            with self.subTest(bad=bad):
                self.assertIsNone(causal_read_opportunities([bad], [LOG_TOOL]))
        self.assertIsNotNone(causal_read_opportunities(
            [mk_receipt([clean])], [EVENT_TOOL]))

    def test_generic_light_and_fan_command_leads_are_bounded_and_neutral(self):
        pairs = [
            ("FX-LIGHT", "command-off", 410),
            ("FX-FAN", "command-on", 701),
        ]
        for dev, command, app in pairs:
            with self.subTest(dev=dev):
                source = mk_receipt([
                    mk_event(command, "2030-11-16T19:21:02Z", app),
                    {"name": "switch", "value": "off",
                     "date": "2030-11-16T19:21:03Z",
                     "producedBy": {"deviceId": "FX-BRIDGE", "name": "Bridge"},
                     "triggered": [{"appId": 999}]},
                ], device=dev)
                result = causal_read_opportunities([source], [LOG_TOOL, EVENT_TOOL])
                self.assertEqual(result["recorded_issuer_app_ids"], [str(app)])
                self.assertTrue(result["no_tool_selected_or_called_by_this_index"])
                self.assertNotIn("999", json.dumps(result))
                self.assertNotIn("physical_effect_verified", json.dumps(result))

    def test_wrong_identity_or_non_device_source_or_failed_read_never_leads(self):
        original = mk_receipt([mk_event(
            "command-off", "2030-11-16T19:21:02Z", 901)])
        wrong_echo = mk_receipt([mk_event(
            "command-off", "2030-11-16T19:21:02Z", 901)], native_device="OTHER")
        mismatched_row = mk_receipt([mk_event(
            "command-off", "2030-11-16T19:21:02Z", 901, device="OTHER")])
        for bad in [
            wrong_echo, mismatched_row,
            mk_receipt([mk_event("command-off", "2030-11-16T19:21:02Z", 901)],
                       source="application"),
            mk_receipt([mk_event("command-off", "2030-11-16T19:21:02Z", 901)],
                       success=False),
            mk_receipt([mk_event("command-off", "2030-11-16T19:21:02", 901)]),
            mk_receipt([mk_event("command-off", "2030-11-16T19:21:02Z", True)]),
            mk_receipt([mk_event("command-setLevel", "2030-11-16T19:21:02Z", 901)],
                       extra={"arguments": {"appId": 901}}),
        ]:
            with self.subTest(bad=bad):
                self.assertIsNone(causal_read_opportunities([bad], [LOG_TOOL]))
        self.assertIsNotNone(causal_read_opportunities([original], [LOG_TOOL]))

    def test_no_advertised_log_tool_is_not_claimed_available(self):
        source = mk_receipt([mk_event("command-off", "2030-11-16T19:21:02Z")])
        result = causal_read_opportunities([source], [EVENT_TOOL])
        self.assertEqual([x["offered_function_name"]
                          for x in result["advertised_source_tools"]],
                         ["hub_list_device_events"])
        self.assertTrue(result["source_tool_advertisement_is_not_data_availability"])

    def test_prior_issuer_log_receipts_count_attempts_but_not_event_decision(self):
        source = mk_receipt([mk_event("command-off", "2030-11-16T19:21:02Z")])
        log = {"name": "hub_get_logs", "arguments": {"appId": 901, "mode": "past"},
               "success": False, "response": '{"error":"fixture unavailable"}'}
        before = deepcopy(log)
        partial = causal_read_opportunities([source, log], [LOG_TOOL, EVENT_TOOL])
        self.assertEqual(partial["issuer_log_read_attempted_in_this_request"], ["901"])
        self.assertEqual(partial["issuer_log_read_succeeded_in_this_request"], [])
        log["success"] = True
        result = causal_read_opportunities([source, log], [LOG_TOOL, EVENT_TOOL])
        self.assertEqual(result["issuer_log_read_succeeded_in_this_request"], ["901"])
        self.assertEqual(result["source_has_event_time_decision_evidence"],
                         "not_established")
        self.assertFalse(before["success"])

    def test_no_invented_schema_fields_gateway_requires_discovery(self):
        source = mk_receipt([mk_event("command-on", "2030-11-16T19:21:02Z")])
        gateway = mk_tool("hub_read_apps", {
            "tool": {"type": "string"},
            "args": {"type": "object"},
        }, ["tool"])
        result = causal_read_opportunities([source], [gateway])
        tool = result["advertised_source_tools"][0]
        self.assertEqual(tool["source_family"], "read_only_leaf_gateway")
        self.assertTrue(tool["leaf_contract_requires_discovery"])
        self.assertNotIn("appId", json.dumps(tool))
        self.assertEqual({x["name"] for x in tool["advertised_argument_fields"]},
                         {"tool", "args"})
        # No gateway leaf can be fabricated from a top-level tool name alone.

    def test_bad_tool_metadata_never_echoes_injection_or_writer(self):
        source = mk_receipt([mk_event("command-on", "2030-11-16T19:21:02Z")])
        injected = mk_tool("hub_get_logs", {
            "appId": {"type": "integer", "description": "PRIVATE-ATTACK"},
            "strange*injection": {"type": "string"},
            "mode": {"type": "string", "enum": ["past", "<unsafe>", "live"]},
        })
        result = causal_read_opportunities([source], [injected, WRITER,
             mk_tool("hub_write_log", {"appId": {"type": "integer"}})])
        text = json.dumps(result)
        self.assertNotIn("PRIVATE-ATTACK", text)
        self.assertNotIn("strange*injection", text)
        self.assertNotIn("<unsafe>", text)
        self.assertNotIn("hub_manage_apps", text)
        self.assertNotIn("hub_write_log", text)


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_list_device_events",
             "inputSchema": EVENT_TOOL["function"]["parameters"]},
            {"name": "hub_get_logs",
             "inputSchema": LOG_TOOL["function"]["parameters"]},
            {"name": "hub_manage_apps",
             "inputSchema": WRITER["function"]["parameters"]},
        ]

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_list_device_events":
            return json.loads(mk_receipt([
                mk_event("command-on", "2030-11-16T19:21:02Z"),
                {"name": "switch", "value": "on",
                 "date": "2030-11-16T19:21:03Z",
                 "producedBy": {"deviceId": "FX-BRIDGE", "name": "Bridge"}},
            ])["response"])
        if name == "hub_get_logs":
            return {"content": [{"type": "text", "text": json.dumps({
                "entries": [{"appId": 901, "date": "2030-11-16T19:21:01Z",
                             "message": "Fictional controller processed an input"}]
            })}]}
        raise AssertionError("No writer may execute")


def ask_tool(name, **args):
    return {"content": "", "tool_calls": [
        {"function": {"name": name, "arguments": args}}
    ]}


class FakeAgent(Agent):
    def __init__(self, *answers):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 20)
        self.answers = list(answers)
        self.seen = []
        self.offered = []

    async def round(self, messages, tools, remaining):
        self.seen.append([dict(x) for x in messages])
        self.offered.append([x["function"]["name"] for x in tools])
        if not self.answers:
            raise AssertionError("Unexpected model round")
        return self.answers.pop(0)


class FakeStateOnlyMCP(FakeMCP):
    async def call(self, name, arguments):
        if name == "hub_list_device_events":
            self.calls.append((name, arguments))
            return json.loads(mk_receipt([
                {"name": "switch", "value": "on", "type": "event",
                 "date": "2030-11-16T19:21:03Z",
                 "producedBy": {"deviceId": "FX-BRIDGE", "name": "Bridge"},
                 "triggered": [{"appId": 901}]},
            ])["response"])
        return await super().call(name, arguments)


class ModelLedOpportunityTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_chooses_event_time_app_logs_from_actual_advertised_schema(self):
        hub = FakeMCP()
        agent = FakeAgent(
            ask_tool("hub_list_device_events", deviceId="FX-OUTPUT", limit=20),
            {"content": "Recorded command issuer known; internal trigger unknown."},
            ask_tool("hub_get_logs", appId=901, mode="past"),
            {"content": "An original issuer command was recorded. A fictional "
                        "log reports activity, but an independent physical "
                        "outcome and event-time input remain unverified."},
        )
        try:
            result = await agent.answer(
                "Why did the fictional output turn ON? Do not change anything.",
                [], hub, 120, enable_final_claim_audit=False,
                enable_causal_follow_through=False,
            )
        finally:
            await agent.close()
        self.assertEqual(result["rounds"], 4)
        self.assertEqual(hub.calls, [
            ("hub_list_device_events", {"deviceId": "FX-OUTPUT", "limit": 20}),
            ("hub_get_logs", {"appId": 901, "mode": "past"}),
        ])
        self.assertIn("Actual advertised read-only source options",
                      agent.seen[2][-1]["content"])
        self.assertIn("hub_get_logs", agent.seen[2][-1]["content"])
        self.assertIn("901", agent.seen[2][-1]["content"])
        self.assertNotIn("hub_manage_apps", agent.offered[2])
        self.assertFalse(result["action_lifecycle"]["native_write_submitted"])

    async def test_model_declines_optional_log_read_and_no_auto_dispatch(self):
        hub = FakeMCP()
        agent = FakeAgent(
            ask_tool("hub_list_device_events", deviceId="FX-OUTPUT", limit=20),
            {"content": "Recorded command issuer known, trigger still unknown."},
            {"content": "The recorded app issued command-on; internal "
                        "cause and physical outcome remain unverified."},
        )
        try:
            result = await agent.answer(
                "Why did the fictional output turn ON? Do not change anything.",
                [], hub, 120, enable_final_claim_audit=False,
                enable_causal_follow_through=False,
            )
        finally:
            await agent.close()
        self.assertEqual(len(hub.calls), 1)
        self.assertEqual(result["rounds"], 3)
        self.assertIn("Actual advertised read-only source options",
                      agent.seen[2][-1]["content"])
        self.assertFalse(result["action_lifecycle"]["native_write_submitted"])

    async def test_state_only_model_selects_optional_advertised_logs(self):
        hub = FakeStateOnlyMCP()
        agent = FakeAgent(
            ask_tool("hub_list_device_events", deviceId="FX-OUTPUT", limit=20),
            {"content": "Reported state observed; decision unverified."},
            ask_tool("hub_get_logs", appId=901, mode="past"),
            {"content": "Original state report and log read, but the listener "
                        "does not establish a command issuer."},
        )
        try:
            result = await agent.answer(
                "Why did the fictional output turn ON? Do not change anything.",
                [], hub, 120, enable_final_claim_audit=False,
                enable_causal_follow_through=False,
            )
        finally:
            await agent.close()
        self.assertEqual(result["rounds"], 4)
        self.assertEqual(hub.calls, [
            ("hub_list_device_events", {"deviceId": "FX-OUTPUT", "limit": 20}),
            ("hub_get_logs", {"appId": 901, "mode": "past"}),
        ])
        guidance = agent.seen[2][-1]["content"]
        self.assertIn("Actual advertised read-only source options", guidance)
        self.assertIn("native_state_report_without_recorded_command_issuer", guidance)
        self.assertIn("hub_get_logs", guidance)
        self.assertNotIn("hub_manage_apps", agent.offered[2])
        self.assertFalse(result["action_lifecycle"]["native_write_submitted"])

    async def test_state_only_model_may_decline_an_extra_read(self):
        hub = FakeStateOnlyMCP()
        agent = FakeAgent(
            ask_tool("hub_list_device_events", deviceId="FX-OUTPUT", limit=20),
            {"content": "State reported on, internal cause unverified."},
            {"content": "State reported on; no controller decision source."},
        )
        try:
            result = await agent.answer(
                "Why did the fictional output turn ON? Do not change anything.",
                [], hub, 120, enable_final_claim_audit=False,
                enable_causal_follow_through=False,
            )
        finally:
            await agent.close()
        self.assertEqual(result["rounds"], 3)
        self.assertEqual(len(hub.calls), 1)
        self.assertIn("Actual advertised read-only source options",
                      agent.seen[2][-1]["content"])
        self.assertFalse(result["action_lifecycle"]["native_write_submitted"])


if __name__ == "__main__":
    unittest.main()

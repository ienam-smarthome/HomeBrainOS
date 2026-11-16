"""Fictional, cross-domain command provenance in conservative V2 partial answers.

No live home, cloud model, approval, write, network connection or private
household metadata. These tests assess what original receipts can justify,
not whether an LLM independently discovers the correct source.
"""
from __future__ import annotations

from copy import deepcopy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from native_command_provenance import original_command_rows
from read_only_receipt_fallback import source_only_partial_answer


def receipt(native, *, device_id="FX-LAMP", success=True, limit=20):
    return {
        "name": "hub_list_device_events",
        "arguments": {"deviceId": device_id, "limit": limit},
        "success": success, "result_kind": "tool_result",
        "response": json.dumps({
            "content": [{"type": "text", "text": json.dumps(native)}]
        }),
    }


def event(name, date, value=None, *, producer=None, listeners=None, type_=None):
    result = {"name": name, "date": date}
    if value is not None:
        result["value"] = value
    if producer is not None:
        result["producedBy"] = producer
    if listeners is not None:
        result["triggered"] = listeners
    if type_ is not None:
        result["type"] = type_
    return result


APP_A = {"name": "Fixture button controller", "appId": 812}
APP_B = {"name": "Fixture brightness automation", "appId": 821}
BRIDGE = {"name": "Fixture Matter Bridge", "deviceId": "FX-BRIDGE"}
LISTENER = [{"name": "Fictional listening automation", "appId": 999}]


def lighting_history():
    return {
        "device": "Fixture Lamp", "count": 8,
        "events": [
            event("level", "2030-11-16T20:34:48.274+0000", "83",
                  producer=BRIDGE, listeners=LISTENER),
            event("command-setLevel", "2030-11-16T20:34:48.069+0000",
                  producer=APP_B),
            event("command-setLevel", "2030-11-16T20:34:46.194+0000",
                  producer=APP_B),
            event("switch", "2030-11-16T20:34:39.074+0000", "on",
                  producer=BRIDGE, listeners=LISTENER),
            event("command-on", "2030-11-16T20:34:38.621+0000",
                  producer=APP_B),
            event("switch", "2030-11-16T19:22:57.424+0000", "off",
                  producer=BRIDGE, listeners=LISTENER),
            event("command-off", "2030-11-16T19:22:57.223+0000",
                  producer=APP_A),
            event("level", "2030-11-16T19:18:26.224+0000", "100",
                  producer=BRIDGE),
        ],
    }


class NativeCommandProvenanceTests(unittest.TestCase):
    def test_realistic_native_shape_retains_distinct_off_after_newer_level_calls(self):
        source = receipt(lighting_history(), limit=8)
        before = deepcopy(source)
        records, cap = original_command_rows([source])
        self.assertTrue(cap)
        self.assertEqual({r["command_name"] for r in records},
                         {"command-off", "command-on", "command-setLevel"})
        off = next(r for r in records if r["command_name"] == "command-off")
        self.assertEqual(off["issuer_app_id"], "812")
        self.assertEqual(off["issuer_label"], "Fixture button controller")
        self.assertEqual(source, before)

        result = source_only_partial_answer("Why did this lamp turn OFF?",
                                            [source], timezone_name="Europe/London")
        self.assertIn("command-off", result)
        self.assertIn("Fixture button controller", result)
        self.assertIn("app ID 812", result)
        self.assertIn("7:22:57 pm GMT", result)
        self.assertIn("Fixture Matter Bridge", result)
        self.assertIn("reported by", result)
        self.assertNotIn("listening automation", result)
        self.assertNotIn("app ID 999", result)
        self.assertIn("row limit", result)
        self.assertIn("not exhaustive", result)
        self.assertIn("not proof", result)
        self.assertNotIn("physical state change", result)
        self.assertNotIn("caused by the button", result)

    def test_command_only_history_remains_evidence_without_reported_state(self):
        data = {"source": "device", "deviceId": "FX-LAMP",
                "events": [event("command-off", "2030-11-16T19:22:57Z",
                                 producer=APP_A)]}
        result = source_only_partial_answer(
            "What was recorded?", [receipt(data)], timezone_name="Europe/London")
        self.assertIn("command-off", result)
        self.assertIn("app ID 812", result)
        self.assertNotIn("Returned device state reports", result)
        self.assertIn("independent physical effect", result)

    def test_cross_domain_heat_output_command_not_mistaken_for_heating(self):
        data = {"device": "Fixture Shared Relay", "events": [
            event("command-setHeatingSetpoint", "2030-01-05T10:30:02+0000",
                  producer={"name": "Fixture Heat Scheduler", "appId": 416},
                  type_="command"),
            event("heatingSetpoint", "2030-01-05T10:30:03+0000", "22.0",
                  producer={"name": "Fixture Driver", "deviceId": "FX-HEAT"}),
            event("thermostatOperatingState", "2030-01-05T10:30:20+0000",
                  "heating", producer={"name": "Fixture Driver",
                                       "deviceId": "FX-HEAT"}),
        ]}
        output = source_only_partial_answer("Why did shared heat start?",
                    [receipt(data, device_id="FX-RELAY")])
        self.assertIn("command-setHeatingSetpoint", output)
        self.assertIn("Fixture Heat Scheduler", output)
        self.assertIn("10:30:20 am GMT", output)
        self.assertIn("reported by Fixture Driver", output)
        self.assertIn("internal controller decision", output)
        self.assertIn("physical", output)

    def test_missing_issuer_not_promoted_from_listener_or_bridge(self):
        data = {"device": "Fixture Gate", "events": [
            event("command-off", "2030-01-05T10:30:02Z",
                  producer={"name": "Fixture Reporter", "deviceId": "FX-BRIDGE"},
                  listeners=LISTENER),
            event("switch", "2030-01-05T10:30:04Z", "off",
                  producer=BRIDGE, listeners=LISTENER),
        ]}
        output = source_only_partial_answer("Why?", [receipt(data)])
        self.assertIn("command-off", output)
        self.assertIn("issuer not established", output)
        self.assertNotIn("app ID 999", output)
        self.assertNotIn("recorded issuer **Fixture Reporter**", output)

    def test_conflicting_same_time_issuers_cannot_establish_unique_identity(self):
        base = {"device": "Fixture Outlet", "events": [
            event("command-off", "2030-01-05T10:00:00Z",
                  producer={"name": "Fixture App One", "appId": 901})]}
        other = deepcopy(base)
        other["events"][0]["producedBy"] = {"name": "Fixture App Two", "appId": 902}
        rows, _ = original_command_rows([
            receipt(base), receipt(other),
        ])
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["issuer_app_id"])
        self.assertIsNone(rows[0]["issuer_label"])

    def test_untrusted_labels_malformed_times_mismatch_and_failed_reads(self):
        native = {"device": "Fixture <script>**unsafe**", "events": [
            event("command-off", "2030-01-05T10:00:00Z",
                  producer={"name": "**trick** <script>", "appId": "not-an-id"}),
            event("command-on", "2030-01-05T10:01:00",
                  producer=APP_A),
            event("command-off<inject>", "2030-01-05T10:02:00Z",
                  producer=APP_A),
            event("switch", "2030-01-05T10:04:00Z", "off",
                  producer=BRIDGE),
        ]}
        valid = receipt(native)
        wrong = receipt(dict(native, deviceId="WRONG"))
        nondevice = receipt(dict(native, source="location"))
        failed = receipt(native, success=False)
        baseline, _ = original_command_rows([valid])
        self.assertEqual(len(baseline), 1)
        self.assertIsNone(baseline[0]["issuer_app_id"])
        for row in (wrong, nondevice, failed):
            result = source_only_partial_answer("Why?", [row])
            self.assertIsNone(result)
        output = source_only_partial_answer("Why?", [valid])
        self.assertNotIn("<script>", output)
        self.assertNotIn("<inject>", output)
        self.assertNotIn("trick", output)
        self.assertIn("issuer not established", output)

    def test_no_auto_focal_device_or_unbounded_source_promotions(self):
        a = receipt({"device": "Fixture Outlet", "events": [
            event("command-off", "2030-01-05T10:00:00Z",
                  producer=APP_A)]}, device_id="FX-A")
        b = receipt({"device": "Fixture Ventilation", "events": [
            event("command-on", "2030-01-05T10:01:00Z",
                  producer=APP_B)]}, device_id="FX-B")
        output = source_only_partial_answer("What caused it?", [a, b])
        self.assertIn("Fixture Outlet", output)
        self.assertIn("Fixture Ventilation", output)
        self.assertNotIn("therefore the cause", output)


class FictionalMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [{"name": "hub_list_device_events",
                 "inputSchema": {"type": "object", "properties": {
                     "deviceId": {"type": "string"}}}}]

    async def call(self, name, args):
        self.calls.append((name, args))
        assert name == "hub_list_device_events"
        assert args == {"deviceId": "FX-LAMP", "limit": 8}
        return json.loads(receipt(lighting_history(), limit=8)["response"])


class ScriptedAgent(Agent):
    def __init__(self, *rounds):
        super().__init__("http://127.0.0.1:11434", "fixture", "", 20)
        self.scripted_rounds = list(rounds)

    async def round(self, messages, tools, remaining):
        if not self.scripted_rounds:
            raise AssertionError("Unexpected extra model call")
        return self.scripted_rounds.pop(0)


class EndToEndTests(unittest.IsolatedAsyncioTestCase):
    async def test_unsupported_model_cause_preserves_native_issuer_and_reporter(self):
        mcp = FictionalMCP()
        agent = ScriptedAgent(
            {"content": "", "tool_calls": [{"function": {
                "name": "hub_list_device_events",
                "arguments": {"deviceId": "FX-LAMP", "limit": 8}}}]},
            {"content": "The lamp turned off because the controller executed a timer."},
        )
        try:
            result = await agent.answer(
                "Why did the fictional lamp turn OFF most recently? Do not change anything.",
                [], mcp, 90, enable_source_review=False,
                enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        self.assertEqual(result["answer_fallback_status"], "causal_claim_publication_floor")
        self.assertEqual(result["causal_claim_verification"]["reason"],
                         "controller_decision_unverified")
        self.assertEqual(result["rounds"], 2)
        self.assertEqual(len(mcp.calls), 1)
        self.assertIn("command-off", result["answer"])
        self.assertIn("Fixture button controller", result["answer"])
        self.assertIn("reported by Fixture Matter Bridge", result["answer"])
        self.assertNotIn("executed a timer", result["answer"])
        self.assertFalse(result["action_lifecycle"]["native_write_submitted"])


if __name__ == "__main__":
    unittest.main()

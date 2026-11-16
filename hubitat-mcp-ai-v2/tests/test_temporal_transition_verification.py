"""Fictional original MCP evidence for source-derived latest transition claims.

No real Hubitat, cloud model or writes. These are general event/attribute
fixtures covering focal vs peer identity, lookback, truncation and chronology.
"""
from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from temporal_transition_verification import (
    temporal_transition_evidence, verify_recent_transition, _friendly_time,
)

Q = ("In the last 12 hours, when did Fictional Bedroom TRV last change "
     "from heating to idle? What was main Thermostat doing and what caused it? "
     "Do not change anything.")


def receipt(name, args, data, success=True):
    return {
        "name": name, "arguments": args, "success": success,
        "result_kind": "tool_result",
        "response": json.dumps({
            "content": [{"type": "text", "text": json.dumps(data)}]
        }),
    }


def native_events(device_id, label, events, *, hours=12, limit=100,
                  since="2026-11-15T10:22:08+0000"):
    return receipt(
        "hub_list_device_events",
        {"deviceId": device_id, "hoursBack": hours, "limit": limit},
        {"deviceId": str(device_id), "device": label,
         "sinceTimestamp": since, "hoursBack": hours,
         "events": events, "count": len(events)},
    )


def event(name, value, date, actor=None):
    row = {"name": name, "value": value, "date": date,
           "isStateChange": True}
    if actor:
        row["producedBy"] = {"name": actor, "appId": 3970}
    return row


def original_fixture():
    rows = [
        receipt("hub_list_devices", {"format": "summary",
                                    "labelFilter": "Fictional Bedroom TRV"},
                {"devices": [{"id": "101", "label": "Fictional Bedroom TRV"}],
                 "count": 1, "total": 1}),
        native_events(101, "Fictional Bedroom TRV", [
            event("thermostatOperatingState", "idle",
                  "2026-11-15T17:00:56.395+0000"),
            event("thermostatOperatingState", "idle",
                  "2026-11-15T18:30:55.492+0000"),
            event("thermostatOperatingState", "idle",
                  "2026-11-15T22:00:54.742+0000"),
        ]),
        # A successful transport with only a truncated client view is not
        # an inspectable native event timeline and cannot provide a focal pair.
        {"name": "hub_list_device_events",
         "arguments": {"deviceId": 101, "hoursBack": 12, "limit": 200},
         "success": True, "result_kind": "tool_result",
         "response": json.dumps({
             "truncated": True, "returned_characters": 97000,
             "visible_prefix": "A partial prefix of a large event response"
         })},
        native_events(202, "Fictional Main Thermostat", [
            event("thermostatOperatingState", "heating",
                  "2026-11-15T15:58:35.644+0000"),
            event("command-setHeatingSetpoint", "12.0",
                  "2026-11-15T16:05:07.838+0000",
                  actor="Fictional Thermostat Scheduler"),
            event("thermostatOperatingState", "idle",
                  "2026-11-15T16:05:25.999+0000"),
            event("thermostatOperatingState", "heating",
                  "2026-11-15T21:53:35.570+0000"),
            event("command-setHeatingSetpoint", "12.0",
                  "2026-11-15T22:00:08.416+0000",
                  actor="Fictional Thermostat Scheduler"),
            event("thermostatOperatingState", "idle",
                  "2026-11-15T22:00:26.949+0000"),
        ]),
    ]
    return rows


class FocalTransitionTests(unittest.TestCase):
    def test_peer_latest_must_not_be_focal_transition_or_caused_claim(self):
        source = original_fixture()
        index = temporal_transition_evidence(Q, source)
        self.assertEqual(index["target_id"], "101")
        self.assertEqual(index["focal_report_count"], 3)
        self.assertEqual(index["focal_truncated_reads"], 1)
        self.assertIsNone(index["focal_pair"])
        self.assertTrue(index["requested_window_verified_from_source"])
        self.assertEqual(index["peer_reports"][0]["latest"]["timestamp"],
                         "2026-11-15T22:00:26.949+0000")
        self.assertEqual(index["peer_reports"][0]["previous_different"]["timestamp"],
                         "2026-11-15T21:53:35.570+0000")
        bogus = (
            "Bedroom TRV last changed at 16:05:08 due to Scheduler; the "
            "Thermostat's last heating event was 15:58:35. Verified cause."
        )
        answer = verify_recent_transition(Q, bogus, source)
        self.assertEqual(answer["status"], "focal_transition_unverified")
        self.assertIn("cannot verify its last HEATING → IDLE", answer["answer"])
        self.assertIn("5:00 pm UTC", answer["answer"])
        self.assertIn("10:00 pm UTC", answer["answer"])
        self.assertIn("9:53 pm UTC", answer["answer"])
        self.assertIn("10:00 pm UTC", answer["answer"])
        self.assertIn("10:00 pm UTC", answer["answer"])
        self.assertIn("Fictional Thermostat Scheduler", answer["answer"])
        self.assertNotIn("due to Scheduler", answer["answer"])
        self.assertNotIn("last heating event was 15:58", answer["answer"])
        self.assertFalse(answer["physical_transition_or_cause_verified"])

    def test_latest_observed_pair_is_focal_and_not_absolute_or_physical(self):
        source = original_fixture()
        source[1] = native_events(101, "Fictional Bedroom TRV", [
            event("thermostatOperatingState", "heating",
                  "2026-11-15T16:00:00+0000"),
            event("thermostatOperatingState", "idle",
                  "2026-11-15T16:05:00+0000"),
            event("thermostatOperatingState", "heating",
                  "2026-11-15T21:20:00+0000"),
            event("thermostatOperatingState", "idle",
                  "2026-11-15T22:00:00+0000"),
        ])
        got = verify_recent_transition(Q, "Last 16:05 definitely caused", source)
        self.assertEqual(got["status"], "bounded_pair_observed")
        self.assertIn("10:00 pm UTC", got["answer"])
        self.assertIn("9:20 pm UTC", got["answer"])
        self.assertIn("latest *observed*", got["answer"])
        self.assertIn("not independently verified", got["answer"])
        self.assertNotIn("Last 16:05 definitely caused", got["answer"])

    def test_older_24h_source_does_not_establish_12h_pair(self):
        source = original_fixture()
        source[1] = native_events(
            101, "Fictional Bedroom TRV", [
                event("thermostatOperatingState", "heating",
                      "2026-11-14T23:00:00+0000"),
                event("thermostatOperatingState", "idle",
                      "2026-11-14T23:30:00+0000"),
            ], hours=24, since="2026-11-14T22:22:08+0000",
        )
        # No matching 12-hour source in this fixture: a 24-hour return
        # cannot silently certify the user's requested relative window.
        source = source[:3]
        got = verify_recent_transition(Q, "Latest at 23:30", source)
        self.assertEqual(got["status"], "focal_transition_unverified")
        self.assertFalse(got["requested_window_verified_from_source"])
        self.assertIn("relative time window", got["answer"])
        self.assertNotIn("Latest at 23:30", got["answer"])

    def test_other_device_state_and_commands_do_not_supply_focal_pair(self):
        source = original_fixture()
        source[1] = native_events(101, "Fictional Bedroom TRV", [])
        result = temporal_transition_evidence(Q, source)
        self.assertEqual(result["focal_report_count"], 0)
        self.assertIsNone(result["focal_pair"])
        self.assertEqual(result["peer_reports"][0]["latest"]["observed_value"], "idle")

    def test_nonmatching_questions_and_controls_are_unchanged(self):
        source = original_fixture()
        for q in (
            "Turn off Fictional Bedroom TRV",
            "Why did my heating stop?",
            "List all returned events in the last 12 hours",
            "What is the current temperature?",
        ):
            with self.subTest(question=q):
                res = verify_recent_transition(q, "Original answer", source)
                self.assertEqual(res["status"], "not_applicable")
                self.assertEqual(res["answer"], "Original answer")

    def test_missing_identity_and_failed_event_read_never_prove_absence(self):
        source = original_fixture()
        missing = verify_recent_transition(Q, "Definitely at 16:05", source[1:])
        self.assertEqual(missing["status"], "focal_transition_unverified")
        self.assertIn("cannot verify", missing["answer"])
        only_failed = [source[0], {**source[1], "success": False}]
        missing = verify_recent_transition(Q, "Definitely at 16:05", only_failed)
        self.assertEqual(missing["focal_returned_state_rows"], 0)
        self.assertNotIn("Definitely at 16:05", missing["answer"])

    def test_source_timestamp_must_keep_offset(self):
        source = original_fixture()
        source[1] = native_events(101, "Fictional Bedroom TRV", [
            event("thermostatOperatingState", "heating", "2026-11-15T20:00:00"),
            event("thermostatOperatingState", "idle", "2026-11-15T21:00:00"),
        ])
        got = verify_recent_transition(Q, "Definitely 21", source)
        self.assertEqual(got["status"], "focal_transition_unverified")

    def test_row_limit_reached_is_not_proof_of_complete_history(self):
        source = original_fixture()
        source[1] = native_events(101, "Fictional Bedroom TRV", [
            event("thermostatOperatingState", "heating", "2026-11-15T20:00:00+0000"),
            event("thermostatOperatingState", "idle", "2026-11-15T21:00:00+0000"),
        ], limit=2)
        got = verify_recent_transition(Q, "Latest 21", source)
        self.assertEqual(got["focal_limit_reached_reads"], 1)
        self.assertIn("truncated or capped", got["answer"])


    def test_preserves_separate_source_verified_thermostat_context(self):
        source = original_fixture()
        source[1] = native_events(101, "Fictional Bedroom TRV", [
            event("thermostatOperatingState", "idle",
                  "2026-11-15T18:00:55+0000"),
            event("command-setHeatingSetpoint", "16.0",
                  "2026-11-15T23:00:07+0000",
                  actor="Fictional Thermostat Scheduler"),
            event("heatingSetpoint", "16.0", "2026-11-15T23:00:53+0000"),
            event("temperature", "22.0", "2026-11-15T23:00:53+0000"),
            event("valveLevel", "0", "2026-11-15T23:00:55+0000"),
            event("thermostatOperatingState", "idle",
                  "2026-11-15T23:00:55+0000"),
        ], since="2026-11-15T11:15:00+0000")
        source[3] = native_events(202, "Fictional Main Thermostat", [
            event("thermostatOperatingState", "heating",
                  "2026-11-15T21:53:35+0000"),
            event("command-setHeatingSetpoint", "12.0",
                  "2026-11-15T22:00:08+0000",
                  actor="Fictional Thermostat Scheduler"),
            event("thermostatOperatingState", "idle",
                  "2026-11-15T22:00:26+0000"),
            event("command-setThermostatMode", "off",
                  "2026-11-15T22:30:01+0000",
                  actor="Fictional Thermostat OFF app"),
            event("thermostatMode", "off", "2026-11-15T22:30:02+0000"),
        ], since="2026-11-15T11:15:00+0000")
        index = temporal_transition_evidence(Q, source)
        self.assertIsNone(index["focal_pair"])
        self.assertEqual(index["focal_context"][-1]["event_name"], "valveLevel")
        self.assertEqual(index["focal_commands"][-1]["observed_value"], "16.0")
        self.assertEqual(index["peer_reports"][0]["latest_mode"]["observed_value"], "off")
        answer = verify_recent_transition(Q, "The TRV switched at 22:00 because of the thermostat.", source)
        self.assertIn("cannot verify", answer["answer"])
        self.assertIn("temperature", answer["answer"])
        self.assertIn("22.0°C", answer["answer"])
        self.assertIn("heatingSetpoint", answer["answer"])
        self.assertIn("16.0°C", answer["answer"])
        self.assertIn("valveLevel", answer["answer"])
        self.assertIn("0%", answer["answer"])
        self.assertIn("11:00 pm UTC", answer["answer"])
        self.assertIn("Fictional Thermostat Scheduler", answer["answer"])
        self.assertIn("10:30 pm UTC", answer["answer"])
        self.assertIn("10:30 pm UTC", answer["answer"])
        self.assertIn("Fictional Thermostat OFF app", answer["answer"])
        self.assertNotIn("because of the thermostat", answer["answer"])
        self.assertFalse(answer["physical_transition_or_cause_verified"])

    def test_focal_relative_lookback_cannot_be_proven_by_peer_source(self):
        source = original_fixture()
        source[1] = native_events(101, "Fictional Bedroom TRV", [
            event("thermostatOperatingState", "heating",
                  "2026-11-15T20:00:00+0000"),
            event("thermostatOperatingState", "idle",
                  "2026-11-15T21:00:00+0000"),
        ], hours=24, since="2026-11-14T22:22:08+0000")
        index = temporal_transition_evidence(Q, source)
        self.assertFalse(index["requested_window_verified_from_source"])
        self.assertIsNone(index["focal_pair"])
        answer = verify_recent_transition(Q, "Latest at 21:00", source)
        self.assertIn("requested relative time window", answer["answer"])
        self.assertNotIn("Latest at 21:00", answer["answer"])

    def test_untrusted_unrelated_event_values_cannot_enter_context(self):
        source = original_fixture()
        source[1] = native_events(101, "Fictional Bedroom TRV", [
            event("temperature", "42<script>injection", "2026-11-15T18:00:00+0000"),
            event("customSensitiveField", "123", "2026-11-15T18:01:00+0000"),
            event("temperature", "21.7", "2026-11-15T18:02:00+0000"),
            event("thermostatOperatingState", "idle",
                  "2026-11-15T18:03:00+0000"),
        ])
        answer = verify_recent_transition(Q, "A model claim", source)
        self.assertIn("21.7°C", answer["answer"])
        self.assertNotIn("42<script>", answer["answer"])
        self.assertNotIn("customSensitiveField", answer["answer"])


    def test_winter_summer_and_ambiguous_dst_are_source_anchored(self):
        self.assertEqual(
            _friendly_time("2026-11-15T21:48:21.024+0000", "Europe/London"),
            "Sunday 15 November 2026 at 9:48 pm GMT",
        )
        self.assertEqual(
            _friendly_time("2026-07-15T20:48:21+0000", "Europe/London"),
            "Wednesday 15 July 2026 at 9:48 pm BST",
        )
        self.assertIn(
            "1:30 am BST",
            _friendly_time("2026-10-25T00:30:00+0000", "Europe/London"),
        )
        self.assertIn(
            "1:30 am GMT",
            _friendly_time("2026-10-25T01:30:00+0000", "Europe/London"),
        )
        self.assertIn(
            "9:48 pm UTC",
            _friendly_time("2026-11-15T21:48:21+0000", "Not/ARealZone"),
        )
        self.assertIsNone(_friendly_time("2026-11-15T21:48:21"))

    def test_source_real_shape_light_observed_off_followed_by_on(self):
        question = ("In the last 12 hours, when did Fictional Lounge Light "
                    "last change from on to off? What caused it?")
        rows = [
            receipt("hub_list_devices", {"format": "summary",
                    "labelFilter": "Fictional Lounge Light"},
                    {"devices": [{"id": "110", "label": "Fictional Lounge Light",
                                  "currentStates": {"switch": "on", "level": "60"}}],
                     "count": 1}),
        ]
        events = [
            event("switch", "on", "2026-11-15T21:07:38.098+0000"),
            event("switch", "off", "2026-11-15T21:48:21.024+0000"),
            event("switch", "on", "2026-11-15T21:49:47.638+0000"),
        ]
        events[1]["producedBy"] = {"name": "Fictional Zigbee Bridge",
                                     "deviceId": "100"}
        rows.append(native_events(110, "Fictional Lounge Light", events,
                                  since="2026-11-15T11:53:36+0000"))
        index = temporal_transition_evidence(question, rows)
        self.assertEqual(index["focal_pair"]["after"]["timestamp"],
                         "2026-11-15T21:48:21.024+0000")
        self.assertEqual(index["focal_later_report"]["observed_value"], "on")
        answer = verify_recent_transition(
            question, "Definitely caused by Fictional Bridge at 22:00", rows,
            timezone_name="Europe/London",
        )
        self.assertEqual(answer["status"], "bounded_pair_observed")
        self.assertIn("Sunday 15 November 2026 at 9:48 pm GMT", answer["answer"])
        self.assertIn("9:07 pm GMT", answer["answer"])
        self.assertIn("9:49 pm GMT", answer["answer"])
        self.assertIn("reported by **Fictional Zigbee Bridge**", answer["answer"])
        self.assertIn("Inventory read during this request", answer["answer"])
        self.assertIn("60% level", answer["answer"])
        self.assertNotIn("2026-11-15T", answer["answer"])
        self.assertNotIn("Definitely caused", answer["answer"])
        self.assertIn("initiated", answer["answer"])
        self.assertEqual(answer["focal_pair_original_timestamps"]["after"],
                         "2026-11-15T21:48:21.024+0000")
        self.assertFalse(answer["physical_transition_or_cause_verified"])



class FictionalTemporalHub:
    def __init__(self):
        self.sources = original_fixture()
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_list_devices", "inputSchema": {"type": "object"}},
            {"name": "hub_list_device_events", "inputSchema": {"type": "object"}},
        ]

    async def call(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "hub_list_devices":
            return json.loads(self.sources[0]["response"])
        if name == "hub_list_device_events":
            if args.get("deviceId") == 101:
                return json.loads(self.sources[1]["response"])
            if args.get("deviceId") == 202:
                return json.loads(self.sources[3]["response"])
        raise AssertionError("No unadvertised tool or native write allowed")


class ScriptedTemporalAgent:
    def __init__(self, script):
        from agent import Agent
        class Internal(Agent):
            def __init__(self, script):
                super().__init__("http://127.0.0.1:11434", "fiction", "", 12)
                self.script = list(script)
                self.rounds_seen = 0
                self.prompts = []

            async def round(self, messages, tools, remaining):
                self.rounds_seen += 1
                self.prompts.append(messages[-1].get("content", ""))
                if not self.script:
                    raise AssertionError("Unexpected extra paid-model round")
                return self.script.pop(0)
        self.model = Internal(script)


def selected_tool(name, **args):
    return {"tool_calls": [{"function": {
        "name": name, "arguments": args,
    }}]}


class IntegratedTemporalPublicationTests(unittest.IsolatedAsyncioTestCase):
    async def test_wrong_last_and_cause_cannot_survive_existing_review(self):
        hub = FictionalTemporalHub()
        draft = (
            "The Fictional Bedroom TRV last changed from heating to idle "
            "at 16:05:08, definitively caused by the main Thermostat's "
            "command. The main Thermostat last heated at 15:58."
        )
        model = ScriptedTemporalAgent([
            selected_tool("hub_list_devices", labelFilter="Fictional Bedroom TRV",
                          format="summary"),
            selected_tool("hub_list_device_events", deviceId=101,
                          attribute="thermostatOperatingState",
                          hoursBack=12, limit=100),
            selected_tool("hub_list_device_events", deviceId=202,
                          hoursBack=12, limit=100),
            {"content": draft},
            {"content": draft},
        ]).model
        try:
            result = await model.answer(
                Q, [], hub, 100, enable_causal_follow_through=False,
                enable_final_claim_audit=True,
            )
        finally:
            await model.close()
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(model.rounds_seen, 5)
        self.assertFalse(result["final_claim_audit_invoked"])
        self.assertIn("Source-derived focal transition audit", model.prompts[-1])
        self.assertEqual(
            result["temporal_transition_verification"]["status"],
            "focal_transition_unverified",
        )
        self.assertIn("cannot verify", result["answer"])
        self.assertIn("10:00 pm GMT", result["answer"])
        self.assertIn("9:53 pm GMT", result["answer"])
        self.assertNotIn("definitively caused", result["answer"])
        self.assertEqual([x[0] for x in hub.calls], [
            "hub_list_devices", "hub_list_device_events",
            "hub_list_device_events",
        ])
        self.assertEqual(result["read_source_usage"]["native_device_event_reads"], 2)


if __name__ == "__main__":
    unittest.main()

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
    temporal_transition_evidence, verify_recent_transition,
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
        self.assertIn("17:00:56.395", answer["answer"])
        self.assertIn("22:00:54.742", answer["answer"])
        self.assertIn("21:53:35.570", answer["answer"])
        self.assertIn("22:00:26.949", answer["answer"])
        self.assertIn("22:00:08.416", answer["answer"])
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
        self.assertIn("22:00:00", got["answer"])
        self.assertIn("21:20:00", got["answer"])
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
        self.assertIn("22:00:26.949", result["answer"])
        self.assertIn("21:53:35.570", result["answer"])
        self.assertNotIn("definitively caused", result["answer"])
        self.assertEqual([x[0] for x in hub.calls], [
            "hub_list_devices", "hub_list_device_events",
            "hub_list_device_events",
        ])
        self.assertEqual(result["read_source_usage"]["native_device_event_reads"], 2)


if __name__ == "__main__":
    unittest.main()

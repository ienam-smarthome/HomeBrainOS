"""Alpha.10 generic causal-evidence and returned-history scope regressions.

Synthetic domains only: not assertions about a user's hub or model quality.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent, _SKILL
from evidence_scope import model_result_with_scope, scope_of


def event_response(device, events, **extras):
    body = {"device": device, "source": "device", "events": events,
            "count": len(events), **extras}
    return {"content": [{"type": "text", "text": json.dumps(body)}],
            "_meta": {"serverInfo": {"version": "fixture"}}}


class ScopeTests(unittest.TestCase):
    def test_filtered_history_does_not_imply_retention_loss(self):
        events = [{"name": "state", "value": "idle",
                   "date": "2026-11-06T11:00:55.000+0000"},
                  {"name": "state", "value": "idle",
                   "date": "2026-11-06T15:00:55.000+0000"}]
        raw = event_response("Fixture A", events, hoursBack=48, attributeFilter="state")
        args = {"tool": "hub_list_device_events",
                "args": {"deviceId": "fixture-A", "attribute": "state",
                         "hoursBack": 48, "limit": 50}}
        decorated = model_result_with_scope(raw, args)
        self.assertEqual(decorated["content"], raw["content"])
        self.assertEqual(decorated["_meta"], raw["_meta"])
        info = decorated["client_event_source_scope"]
        self.assertEqual(info["events_returned"], 2)
        self.assertEqual(info["oldest_returned_event"], events[0]["date"])
        self.assertEqual(info["newest_returned_event"], events[1]["date"])
        self.assertEqual(info["requested_lookback_hours"], 48)
        self.assertEqual(info["requested_limit"], 50)
        self.assertFalse(info["limit_reached"])
        self.assertFalse(info["can_infer_older_events_absent"])
        self.assertFalse(info["can_infer_cause_of_missing_records"])
        self.assertFalse(info["can_infer_requested_window_fully_covered"])
        self.assertIn("not establish", info["note"])
        self.assertEqual(raw.keys(), {"content", "_meta"})  # input not modified

    def test_history_limit_is_possible_cap_not_proof(self):
        result = event_response("Fixture B", [
            {"name": "temperature", "date": "2026-11-06T08:00:00.000Z"},
            {"name": "temperature", "date": "2026-11-06T09:00:00.000Z"},
        ], truncated=True, matchedCount=5)
        meta = scope_of(result, {"tool": "hub_list_device_events",
                                  "args": {"limit": 2}})
        self.assertTrue(meta["limit_reached"])
        self.assertTrue(meta["upstream_truncated"])
        self.assertEqual(meta["upstream_matchedCount"], 5)
        self.assertFalse(meta["can_infer_cause_of_missing_records"])

    def test_empty_history_is_not_absence_proof(self):
        info = scope_of(event_response("Fixture C", []),
                        {"hoursBack": 168, "limit": 100})
        self.assertEqual(info["events_returned"], 0)
        self.assertIsNone(info["oldest_returned_event"])
        self.assertFalse(info["can_infer_older_events_absent"])
        self.assertFalse(info["can_infer_requested_window_fully_covered"])

    def test_returned_observation_spacing_is_not_continuity_proof(self):
        # Wholly fictional event values and clock times.
        rows = [
            {"name": "sample", "value": "10", "date": "2026-02-01T10:00:00.000Z", "isStateChange": True},
            {"name": "sample", "value": "12", "date": "2026-02-01T10:05:00.000Z", "isStateChange": True},
            {"name": "sample", "value": "11", "date": "2026-02-01T11:20:00.000Z", "isStateChange": True},
            {"name": "sample", "value": "9", "date": "2026-02-01T12:00:00.000Z", "isStateChange": True},
        ]
        raw = event_response("Fixture Sensor", rows)
        before = json.dumps(raw, sort_keys=True)
        scope = scope_of(raw, {"attribute": "sample", "limit": 100})
        self.assertEqual(scope["events_returned"], 4)
        self.assertEqual(scope["adjacent_returned_timestamp_pairs"], 3)
        self.assertEqual(scope["largest_gap_between_returned_events_seconds"], 4500.0)
        self.assertFalse(scope["can_infer_uninterrupted_state_between_events"])
        self.assertIn("discrete reports", scope["note"])
        self.assertIn("isStateChange", scope["note"])
        self.assertEqual(json.dumps(raw, sort_keys=True), before)

    def test_gaps_handle_mixed_timezones_duplicates_and_missing_dates(self):
        rows = [
            {"name": "temp", "date": "2026-02-03T10:00:00+0200"},
            {"name": "temp", "date": "2026-02-03T09:30:00+0000"},
            {"name": "temp", "date": "2026-02-03T09:30:00+0000"},
            {"name": "temp", "date": "2026-02-03T09:40:00"},
            {"name": "temp", "value": "unknown"},
        ]
        meta = scope_of(event_response("Synthetic B", rows))
        self.assertEqual(meta["adjacent_returned_timestamp_pairs"], 2)
        self.assertEqual(meta["largest_gap_between_returned_events_seconds"], 5400.0)
        self.assertEqual(meta["date_rows_without_parseable_offset"], 1)
        self.assertFalse(meta["can_infer_uninterrupted_state_between_events"])
        single = scope_of(event_response("Synthetic B", [rows[0]]))
        self.assertIsNone(single["largest_gap_between_returned_events_seconds"])
        self.assertEqual(single["adjacent_returned_timestamp_pairs"], 0)
        empty = scope_of(event_response("Synthetic B", []))
        self.assertIsNone(empty["largest_gap_between_returned_events_seconds"])
        self.assertFalse(empty["can_infer_uninterrupted_state_between_events"])


    def test_command_actor_metadata_does_not_invent_internal_causes(self):
        rows = [
            {"name": "temperature", "date": "2026-04-05T08:12:00Z",
             "producedBy": {"name": "Synthetic sensor"}},
            {"name": "command-setLevel", "type": "command",
             "date": "2026-04-05T08:14:00Z",
             "producedBy": {"name": "Fictional Controller", "appId": 123}},
            {"name": "switch", "value": "off",
             "date": "2026-04-05T08:14:01Z",
             "producedBy": {"name": "Test Bridge"},
             "triggered": [{"name": "Fictional Controller", "appId": 123}]},
        ]
        raw = event_response("Synthetic actuator", rows)
        original = json.dumps(raw, sort_keys=True)
        indexed = model_result_with_scope(raw, {"limit": 100})
        self.assertEqual(indexed["content"], raw["content"])
        self.assertEqual(indexed["_meta"], raw["_meta"])
        command = indexed["client_command_issuer_scope"]
        self.assertEqual(command["command_rows_returned"], 1)
        self.assertEqual(command["command_examples"][0]["reported_command_issuer"],
                         {"name": "Fictional Controller", "appId": 123})
        self.assertFalse(command["issuer_field_alone_proves_internal_trigger"])
        self.assertIn("read-only sources", command["note"])
        self.assertIn("Clock-time coincidence", command["note"])
        self.assertNotIn("Test Bridge", json.dumps(command))
        self.assertEqual(original, json.dumps(raw, sort_keys=True))

    def test_command_issuer_examples_bounded_and_no_assumed_actor(self):
        rows = [
            {"name": "command-off", "date": "2026-02-01T10:00:00Z",
             "type": "command", "producedBy": {"name": "Fictional Controller"}}
            for _ in range(20)
        ]
        rows.append({"name": "command-on", "type": "command",
                     "date": "2026-02-01T10:01:00Z"})
        commands = model_result_with_scope(event_response("Synthetic", rows))
        index = commands["client_command_issuer_scope"]
        self.assertEqual(index["command_rows_returned"], 21)
        self.assertEqual(len(index["command_examples"]), 12)
        self.assertEqual(index["command_examples_omitted"], 9)
        empty_actor = model_result_with_scope(event_response("Synthetic", [
            {"name": "command-off", "date": "2026-02-01T10:01:00Z"}
        ]))["client_command_issuer_scope"]["command_examples"][0]
        self.assertNotIn("reported_command_issuer", empty_actor)

    def test_command_scope_is_not_applied_to_unrelated_reads_or_errors(self):
        plain = event_response("Synthetic", [
            {"name": "temperature", "date": "2026-02-01T10:00:00Z"},
            {"name": "switch", "date": "2026-02-01T10:01:00Z",
             "triggered": [{"name": "Observer", "appId": 999}]},
        ])
        self.assertNotIn("client_command_issuer_scope", model_result_with_scope(plain))
        failure = {"isError": True, "content": [{"type": "text", "text": (
            '{"events":[{"name":"command-off","type":"command"}]}')} ]}
        self.assertIs(model_result_with_scope(failure), failure)

    def test_other_tools_and_error_payload_are_unchanged(self):
        device = {"content": [{"type": "text", "text": '{"devices":[]}'}]}
        self.assertIsNone(scope_of(device))
        self.assertIs(model_result_with_scope(device), device)
        failure = {"isError": True,
                   "content": [{"type": "text", "text": '{"events":[]}'}]}
        self.assertIsNone(scope_of(failure))
        self.assertIs(model_result_with_scope(failure), failure)

    def test_source_time_order_uses_instants_not_string_sort(self):
        a = "2026-11-06T10:00:00.000+0200"  # 08:00 UTC
        b = "2026-11-06T09:30:00.000+0000"  # 09:30 UTC
        info = scope_of(event_response("Fixture D", [
            {"name": "state", "date": b}, {"name": "state", "date": a}
        ]))
        self.assertEqual(info["oldest_returned_event"], a)
        self.assertEqual(info["newest_returned_event"], b)

    def test_general_model_evidence_instructions_do_not_embed_incidents(self):
        for expected in ("discriminates between alternatives",
                         "cause remains unverified",
                         "whole interval was recorded",
                         "Do not project current snapshots"):
            self.assertIn(expected, _SKILL)
        # Generic source-quality wording instead of hard-coded device/incident
        # templates that try to turn a fixed pattern into a causal conclusion.
        self.assertIn("Before stopping at a recorded command issuer", _SKILL)
        self.assertNotIn("Bedroom 1", _SKILL)
        self.assertNotIn("Hubitat event retention limits are", _SKILL)

    def test_agent_receives_scope_as_separate_metadata_without_tool_replay(self):
        original = event_response("Synthetic controller", [
            {"name": "command-off", "type": "command",
             "producedBy": {"name": "Fixture Coordinator", "appId": 72},
             "date": "2026-11-06T11:00:54.000+0000"},
            {"name": "power", "value": "off",
             "date": "2026-11-06T11:00:55.000+0000"},
        ])
        class FakeMCP:
            def __init__(self):
                self.calls = []
            async def list_tools(self, refresh=False):
                return [{"name": "hub_read_history",
                         "inputSchema": {"type": "object",
                                         "properties": {"hoursBack": {"type": "integer"}}}}]
            async def call(self, name, args):
                self.calls.append((name, args))
                return original
        class FakeAgent(Agent):
            def __init__(self):
                super().__init__("http://127.0.0.1:11434", "fixture", "", 15)
                self.rounds = 0
            async def round(self, messages, tools, remaining):
                self.rounds += 1
                if self.rounds == 1:
                    return {"content": "", "tool_calls": [
                        {"function": {"name": "hub_read_history",
                                      "arguments": {"hoursBack": 48}}}]}
                self.messages_seen = list(messages)
                return {"content": "Only returned data verified; cause unverified.",
                        "tool_calls": []}
        async def run():
            hub = FakeMCP()
            agent = FakeAgent()
            try:
                response = await agent.answer("Investigate why", [], hub, 60)
                self.assertTrue(response["success"])
                self.assertEqual(response["rounds"], 2)
                self.assertEqual(hub.calls, [("hub_read_history", {"hoursBack": 48})])
                tool = json.loads(agent.messages_seen[-1]["content"])
                self.assertEqual(tool["content"], original["content"])
                self.assertEqual(tool["client_event_source_scope"]["events_returned"], 2)
                self.assertEqual(tool["client_command_issuer_scope"]["command_rows_returned"], 1)
                self.assertEqual(tool["client_command_issuer_scope"]["command_examples"][0]["reported_command_issuer"]["appId"], 72)
                self.assertFalse(tool["client_event_source_scope"]["can_infer_cause_of_missing_records"])
                receipt = json.loads(response["tool_calls"][0]["response"])
                self.assertEqual(tool, receipt)
            finally:
                await agent.close()
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

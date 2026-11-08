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
        self.assertNotIn("Bedroom 1", _SKILL)
        self.assertNotIn("Hubitat event retention limits are", _SKILL)

    def test_agent_receives_scope_as_separate_metadata_without_tool_replay(self):
        original = event_response("Synthetic controller", [
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
                self.assertEqual(tool["client_event_source_scope"]["events_returned"], 1)
                self.assertFalse(tool["client_event_source_scope"]["can_infer_cause_of_missing_records"])
                receipt = json.loads(response["tool_calls"][0]["response"])
                self.assertEqual(tool, receipt)
            finally:
                await agent.close()
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

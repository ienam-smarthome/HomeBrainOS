"""Experimental source-ledger behavior tests with entirely fictional sources.

No model endpoint, cloud account, Hubitat / HA server, or device actions.
These test structural evidence integrity only, NEVER answer quality uplift.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent
from source_ledger import source_ledger, with_source_ledger
from source_ledger_experiment import SourceLedgerExperimentalAgent


def wrap(data):
    return {"content": [{"type": "text", "text": json.dumps(data)}],
            "_meta": {"serverInfo": {"version": "fiction"}}}


class LedgerStructuralTests(unittest.TestCase):
    def test_generic_current_attribute_counts_are_derived_from_rows(self):
        raw = wrap({"devices": [
            {"currentStates": {"battery": "2", "temperature": "20",
                               "password": "SECRET-NEVER-SUMMARIZE"}},
            {"currentStates": {"battery": "88"}},
            {"currentStates": {"temperature": "19"}},
            {"currentStates": {}},
            {"label": "Private Fixture No State"},
        ], "count": 5, "unfilteredTotal": 17})
        before = json.dumps(raw, sort_keys=True)
        result = with_source_ledger(raw, {"format": "summary"})
        self.assertEqual(raw["_meta"], result["_meta"])
        self.assertEqual(raw["content"], result["content"])
        info = result["client_collection_source_ledger"]
        self.assertEqual(info["kind"], "devices")
        self.assertEqual(info["returned_rows"], 5)
        self.assertEqual(info["reported_matching_rows"], 5)
        self.assertEqual(info["reported_total_rows"], 17)
        self.assertEqual(info["requested_filters"]["format"], "summary")
        battery = info["field_coverage_in_returned_rows"]["battery"]
        self.assertEqual(battery, {"rows_with_field_returned": 2,
                                   "rows_without_field_returned": 3})
        self.assertNotIn("password", info["field_coverage_in_returned_rows"])
        self.assertFalse(info["entire_source_or_requested_window_verified"])
        self.assertEqual(json.dumps(raw, sort_keys=True), before)

    def test_partial_log_page_is_explicit_without_claiming_missing_errors(self):
        raw = wrap({"mode": "past", "total": 510, "matched": 12,
                    "entries": [{"level": "WARN"}, {"level": "WARN"}]})
        result = with_source_ledger(raw, {"tool": "hub_get_logs",
                                          "args": {"level": "warn", "since": "24h",
                                                   "limit": 2}})
        meta = result["client_collection_source_ledger"]
        self.assertEqual(meta["kind"], "entries")
        self.assertEqual(meta["returned_rows"], 2)
        self.assertEqual(meta["reported_matching_rows"], 12)
        self.assertEqual(meta["reported_total_rows"], 510)
        self.assertEqual(meta["requested_filters"]["level"], "warn")
        self.assertEqual(meta["requested_filters"]["since"], "24h")
        self.assertTrue(meta["returned_rows_less_than_reported_matches"])
        self.assertFalse(meta["entire_source_or_requested_window_verified"])

    def test_unfiltered_collection_does_not_invent_completeness(self):
        raw = wrap({"apps": [], "count": 0, "totalOnHub": 23})
        m = source_ledger(raw)
        self.assertEqual(m["returned_rows"], 0)
        self.assertEqual(m["reported_total_rows"], 23)
        self.assertFalse(m["entire_source_or_requested_window_verified"])
        self.assertIsNone(m["returned_rows_less_than_reported_matches"])

    def test_events_errors_and_ambiguous_multi_source_are_unchanged(self):
        event = wrap({"events": [{"name": "sample", "value": "1"}]})
        self.assertIs(with_source_ledger(event), event)
        failure = {**wrap({"devices": []}), "isError": True}
        self.assertIs(with_source_ledger(failure), failure)
        ambiguous = {"content": [
            {"type": "text", "text": '{"devices":[]}'},
            {"type": "text", "text": '{"devices":[]}'},
        ]}
        self.assertIsNone(source_ledger(ambiguous))
        self.assertIs(with_source_ledger(ambiguous), ambiguous)

    def test_malformed_data_and_boolean_counts_do_not_fake_certainty(self):
        bad = wrap({"devices": [{"currentStates": []}], "count": True,
                    "unfilteredTotal": -1})
        meta = source_ledger(bad)
        self.assertEqual(meta["returned_rows"], 1)
        self.assertIsNone(meta["reported_matching_rows"])
        self.assertIsNone(meta["reported_total_rows"])
        self.assertEqual(meta["field_coverage_in_returned_rows"], {})


class FakeMCP:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
    async def list_tools(self, refresh=False):
        return [{"name": "hub_generic_read",
                 "inputSchema": {"type": "object", "properties": {}}}]
    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        return self.payload


class ScriptedRound:
    async def round(self, messages, tools, remaining):
        self.seen = list(messages)
        count = getattr(self, "script_calls", 0)
        self.script_calls = count + 1
        if count == 0:
            return {"content": "", "tool_calls": [
                {"function": {"name": "hub_generic_read", "arguments": {}}}]}
        return {"content": "Fictional observations; no causal conclusion.",
                "tool_calls": []}


class BaselineAgent(ScriptedRound, Agent):
    pass


class CandidateAgent(ScriptedRound, SourceLedgerExperimentalAgent):
    pass


class AgentPresentationTests(unittest.TestCase):
    def test_candidate_adds_only_receipt_scope_without_changing_native_calls(self):
        async def exercise(cls):
            source = wrap({"devices": [
                {"currentStates": {"battery": "42"}},
                {"currentStates": {}},
            ], "count": 2, "unfilteredTotal": 19})
            mcp = FakeMCP(source)
            agent = cls("http://127.0.0.1:11434", "synthetic", "", 15)
            try:
                answer = await agent.answer("Describe synthetic data", [], mcp, 30)
                self.assertTrue(answer["success"])
                self.assertEqual(answer["rounds"], 2)
                self.assertEqual(mcp.calls, [("hub_generic_read", {})])
                self.assertEqual(answer["tool_calls"][0]["name"], "hub_generic_read")
                return json.loads(agent.seen[-1]["content"]), answer
            finally:
                await agent.close()
        baseline, candidate = asyncio.run(exercise(BaselineAgent)), asyncio.run(exercise(CandidateAgent))
        self.assertEqual(baseline[0]["content"], candidate[0]["content"])
        self.assertEqual(baseline[0]["_meta"], candidate[0]["_meta"])
        self.assertNotIn("client_collection_source_ledger", baseline[0])
        self.assertEqual(candidate[0]["client_collection_source_ledger"]["returned_rows"], 2)
        self.assertEqual(candidate[0]["client_collection_source_ledger"]
                         ["field_coverage_in_returned_rows"]["battery"]
                         ["rows_without_field_returned"], 1)
        self.assertEqual(baseline[1]["tool_calls"][0]["success"], True)
        self.assertEqual(candidate[1]["tool_calls"][0]["success"], True)

    def test_candidate_preserves_existing_historical_event_annotation(self):
        source = wrap({"events": [{"name": "temperature", "value": "17",
                                   "date": "2026-10-01T08:00:00Z"}]})
        agent = SourceLedgerExperimentalAgent("http://127.0.0.1:11434", "synthetic", "", 15)
        try:
            result = agent.present_native_result(source, {"hoursBack": 48})
            self.assertEqual(result["client_event_source_scope"]["events_returned"], 1)
            self.assertNotIn("client_collection_source_ledger", result)
            self.assertEqual(result["content"], source["content"])
        finally:
            asyncio.run(agent.close())


if __name__ == "__main__":
    unittest.main()

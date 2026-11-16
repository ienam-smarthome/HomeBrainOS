"""Alpha.122 fictional source-review coverage and no-extra-round regressions.

No real Hubitat, cloud model, device write or account information is used.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from investigation_source_ledger import (
    source_review_ledger, may_skip_unchanged_final_audit,
)


def history_receipt(*, events, limit=20, hours=12, cap=None):
    if cap is None:
        cap = len(events) >= limit
    native = {
        "device": "Fictional Lamp",
        "deviceId": "LAB-1",
        "attributeFilter": "switch",
        "events": events,
        "count": len(events),
        "sinceTimestamp": "2026-11-15T12:00:00+0000",
    }
    return {
        "name": "hub_list_device_events",
        "arguments": {
            "deviceId": "LAB-1", "attribute": "switch",
            "hoursBack": hours, "limit": limit,
        },
        "success": True, "result_kind": "tool_result",
        "response": json.dumps({
            "client_claim_evidence_headline": {
                "row_limit_reached": cap,
                "returned_row_count": len(events),
            },
            "content": [{"type": "text", "text": json.dumps(native)}],
        }),
    }


class LedgerTests(unittest.TestCase):
    def test_repeated_idle_reports_are_not_a_transition_or_full_window(self):
        rows = [
            {"name": "thermostatOperatingState", "value": "idle",
             "isStateChange": True,
             "date": f"2026-11-15T{h:02d}:00:00+0000",
             "producedBy": {"deviceId": "LAB-1"}}
            for h in range(19, 23)
        ]
        original = history_receipt(events=rows)
        original_copy = json.dumps(original, sort_keys=True)
        ledger = json.loads(source_review_ledger([original], monitor_offered=True))
        scope = ledger["receipt_rows"][0]["original_event_scope"]
        self.assertEqual(scope["returned_event_rows"], 4)
        self.assertFalse(scope["full_requested_window_proven_covered"])
        self.assertTrue(scope["no_unseen_commands_or_earlier_events_proven_absent"])
        self.assertIn("12:00:00", scope["native_reported_query_start"])
        self.assertEqual(scope["returned_attributes"][0]["short_observed_values"], [
            {"value": "idle", "returned_rows": 4}
        ])
        self.assertEqual(scope["oldest_indexed_event"], "2026-11-15T19:00:00+00:00")
        self.assertTrue(ledger["monitor_configured_and_offered_not_proven_connected"])
        self.assertEqual(json.dumps(original, sort_keys=True), original_copy)

    def test_original_command_rows_and_reporters_not_turned_into_cause(self):
        result = history_receipt(events=[
            {"name": "command-off", "type": "command",
             "value": None, "date": "2026-11-15T21:48:20+0000",
             "producedBy": {"appId": 15}},
            {"name": "switch", "value": "off",
             "date": "2026-11-15T21:48:21+0000",
             "producedBy": {"deviceId": "BRIDGE-1"}},
        ])
        ledger = json.loads(source_review_ledger([result]))
        scope = ledger["receipt_rows"][0]["original_event_scope"]
        self.assertEqual(scope["returned_event_rows"], 2)
        self.assertEqual({x["attribute"] for x in scope["returned_attributes"]},
                         {"command-off", "switch"})
        self.assertIn("reporter", ledger["review_contract"])
        self.assertNotIn("recorded_issuer", json.dumps(scope))

    def test_failed_schema_read_does_not_mean_empty_history(self):
        error = {
            "name": "hub_list_device_events",
            "arguments": {"deviceId": "LAB-1", "stateFilter": "heating"},
            "success": False, "operation_executed": True,
            "error": "Unknown argument: stateFilter SECRET",
        }
        ledger = source_review_ledger([error])
        obj = json.loads(ledger)["receipt_rows"][0]
        self.assertTrue(obj["failed_read_is_not_empty_history"])
        self.assertNotIn("stateFilter", ledger)
        self.assertNotIn("SECRET", ledger)
        self.assertFalse(may_skip_unchanged_final_audit(
            [error], review_kind="historical_measurement",
            receipt_count_at_review=1
        ))

    def test_value_privacy_cap_and_uncertainty(self):
        rows = [
            {"name": "command-password", "value": "PRIVATE-secret-long-value",
             "date": "2026-11-15T20:00:00+0000"},
            {"name": "switch", "value": "on",
             "date": "2026-11-15T20:01:00+0000"},
        ]
        ledger = source_review_ledger([history_receipt(events=rows)])
        self.assertNotIn("PRIVATE-secret-long-value", ledger)
        self.assertNotIn("secret-long", ledger)
        scope = json.loads(ledger)["receipt_rows"][0]["original_event_scope"]
        self.assertTrue(scope["returned_rows_are_discrete_not_continuous"])
        self.assertEqual(scope["returned_attributes"][1]["short_observed_values"],
                         [{"value": "on", "returned_rows": 1}])

    def test_unmodified_uncapped_history_only_skips_duplicate_audit(self):
        base = history_receipt(events=[
            {"name": "switch", "value": "on",
             "date": "2026-11-15T20:00:00+0000"}
        ])
        self.assertTrue(may_skip_unchanged_final_audit(
            [base], review_kind="historical_measurement",
            receipt_count_at_review=1
        ))
        for rows, kind, initial in (
            ([base], "causal", 1),
            ([base], "historical_measurement", 0),
            ([history_receipt(events=base and [{"name": "switch",
               "value": "on", "date": "2026-11-15T20:00:00+0000"}],
               limit=1)], "historical_measurement", 1),
            ([history_receipt(events=[])], "historical_measurement", 1),
        ):
            with self.subTest(kind=kind, initial=initial):
                self.assertFalse(may_skip_unchanged_final_audit(
                    rows, review_kind=kind, receipt_count_at_review=initial
                ))


class FictionalMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [{
            "name": "hub_list_device_events",
            "description": "Read bounded device event history",
            "inputSchema": {"type": "object", "properties": {
                "deviceId": {"type": "string"},
                "hoursBack": {"type": "number"},
                "limit": {"type": "integer"},
            }},
        }]

    async def call(self, name, args):
        self.calls.append((name, args))
        return {"content": [{"type": "text", "text": json.dumps({
            "device": "Fixture Lamp",
            "deviceId": "LAB-1",
            "attributeFilter": "switch",
            "sinceTimestamp": "2026-11-15T12:00:00+0000",
            "events": [{
                "name": "switch", "value": "off",
                "date": "2026-11-15T22:15:00+0000",
                "producedBy": {"deviceId": "FIXTURE-BRIDGE"},
            }],
            "count": 1,
        })}]}


class ScriptedAgent(Agent):
    def __init__(self):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 20)
        self.messages_seen = []
        self.responses = [
            {"content": "", "tool_calls": [{
                "function": {"name": "hub_list_device_events",
                             "arguments": {"deviceId": "LAB-1",
                                           "hoursBack": 12, "limit": 20}}
            }]},
            {"content": "The fixture reported OFF. Records are bounded.",
             "tool_calls": []},
            {"content": "A fixture OFF report was returned at 10:15 pm; "
                        "the reporting bridge is not the initiator. "
                        "No continuous history was verified.",
             "tool_calls": []},
        ]

    async def round(self, messages, tools, remaining):
        self.messages_seen.append([dict(x) for x in messages])
        if not self.responses:
            raise AssertionError("Unnecessary extra model-only audit round")
        return self.responses.pop(0)


class OrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_gets_ledger_and_skips_redundant_audit(self):
        agent = ScriptedAgent()
        mcp = FictionalMCP()
        try:
            result = await agent.answer(
                "Show the reported switch events in the past 12 hours for "
                "the fictional fixture; oldest first. Do not change anything.",
                [], mcp, 90,
            )
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"], 3)
        self.assertEqual(len(mcp.calls), 1)
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(result["final_claim_audit_status"],
                         "skipped_unchanged_uncapped_sources")
        self.assertFalse(result["final_claim_audit_invoked"])
        prompt = agent.messages_seen[-1][-1]["content"]
        self.assertIn("Original receipt-scope navigation index", prompt)
        self.assertIn("short_observed_values", prompt)
        self.assertIn("full_requested_window_proven_covered", prompt)


if __name__ == "__main__":
    unittest.main()

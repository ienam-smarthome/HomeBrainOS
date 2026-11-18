"""Replays of unsupported prose after successful, bounded native reads."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from historical_publication import historical_publication_check
from test_read_only_receipt_fallback import ARGS_OUT, FakeMCP, ScriptedAgent, tool_call


def receipt(tool, args, native):
    return {"name": tool, "arguments": args, "success": True,
            "response": json.dumps({"content": [
                {"type": "text", "text": json.dumps(native)},
            ]})}


class HistoricalPublicationTests(unittest.TestCase):
    def test_alpha148_source_contract_regressions(self):
        events = receipt("hub_list_device_events", {"appId": 701, "limit": 50}, {"events": []})
        measurement = receipt(
            "hub_list_device_events", {"deviceId": 702, "attribute": "energy", "hoursBack": 168},
            {"events": []},
        )
        log = receipt("hub_get_logs", {"mode": "past", "level": "error", "limit": 0},
                      {"entries": [{}] * 5, "matched": 5, "total": 12295})
        cases = [
            ("06", "The app logs an event each time it issues a decision.", events,
             "unverified_execution_or_reporting_mechanism"),
            ("07", "This shows the full week of recorded events.", measurement,
             "unverified_history_or_retention_coverage"),
            ("07", "A setting is false, meaning the driver does not generate energy events.",
             measurement, "unverified_execution_or_reporting_mechanism"),
            ("08", "Each command attempt updates the hub timestamp.", measurement,
             "unverified_execution_or_reporting_mechanism"),
            ("08", "This discrepancy is explained by command retries.", measurement,
             "unverified_execution_or_reporting_mechanism"),
            ("10", "The evidence confirms it retained the full set of errors for the interval.",
             log, "unverified_history_or_retention_coverage"),
        ]
        for case, draft, source, expected in cases:
            with self.subTest(case=case, draft=draft):
                reason, summary = historical_publication_check(draft, [source])
                self.assertEqual(reason, expected)
                self.assertIn("Receipt 1", summary)
        _, summary = historical_publication_check(cases[-1][1], [log])
        self.assertIn("5 returned, 5 reported matches, source total 12295 with scope unverified", summary)

    def test_qualified_findings_remain_publishable(self):
        events = receipt("hub_list_device_events", {"appId": 701}, {"events": []})
        for draft in (
            "No matching events were returned by this query.",
            "The read cannot establish complete coverage of the window.",
            "All returned rows in that window were OFF reports.",
            "The timestamps differ. Command retries might explain the discrepancy.",
        ):
            with self.subTest(draft=draft):
                self.assertEqual(historical_publication_check(draft, [events]), (None, ""))


class HistoricalPublicationAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_publication_guard_runs_without_optional_audit(self):
        hub = FakeMCP()
        model = ScriptedAgent(
            tool_call("hub_list_device_events", ARGS_OUT),
            {"content": "Each command attempt updates the device timestamp."},
        )
        try:
            result = await model.answer(
                "Compare the fixture device's recent state reports. Do not change anything.",
                [], hub, 90, enable_source_review=False,
            )
        finally:
            await model.close()
        self.assertEqual(result["historical_claim_verification"]["reason"],
                         "unverified_execution_or_reporting_mechanism")
        self.assertNotIn("Each command attempt updates", result["answer"])
        self.assertIn("Bounded history evidence", result["answer"])
        self.assertEqual(len(hub.calls), 1)
        self.assertFalse(result["action_lifecycle"]["native_write_submitted"])

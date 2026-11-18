"""Replays of unsupported prose after successful, bounded native reads."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from historical_publication import historical_publication_check
from read_only_receipt_fallback import source_only_partial_answer
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

    def test_alpha149_scope_claims_that_previously_reached_publication(self):
        history = receipt(
            "hub_list_device_events", {"deviceId": 702, "attribute": "switch", "limit": 5},
            {"events": [{"name": "switch", "value": "off"}] * 5},
        )
        application = receipt("hub_list_device_events", {"appId": 701}, {"events": []})
        energy = receipt(
            "hub_list_device_events", {"deviceId": 702, "attribute": "energy"},
            {"events": []},
        )
        warnings = receipt(
            "hub_get_logs", {"mode": "past", "level": "warn", "since": "3h"},
            {"total": 14500, "matched": 196, "entries": [{}] * 100},
        )
        for case, draft, original in (
            ("05", "The absence of intervening events proves the state remained idle throughout that interval.", history),
            ("05", "The attribute logs a change whenever the value changes.", history),
            ("06", "The app did not emit any device-attribute events.", application),
            ("07", "In the examined 24-hour window, the hub saw no events that reported a change.", energy),
            ("10", "The total is all levels, all time.", warnings),
            ("10", "The available data indicates continuous logging without obvious holes.", warnings),
        ):
            with self.subTest(case=case, draft=draft):
                reason, summary = historical_publication_check(draft, [original])
                self.assertIsNotNone(reason)
                self.assertIn("Bounded history evidence", summary)

    def test_alpha149_activity_and_health_survive_source_only_fallback(self):
        identity = [
            {"id": "702", "lastActivity": "2026-11-18T15:17:04+00:00"},
            {"id": "703", "lastActivity": "2026-11-18T16:00:00+00:00"},
        ]
        inventory = receipt("hub_list_devices", {"format": "summary"}, {"devices": identity})
        history = receipt("hub_list_device_events", {"deviceId": 702, "limit": 10}, {
            "source": "device", "deviceId": 702, "device": "Fixture plug", "events": [
                {"name": "healthStatus", "value": "offline", "date": "2026-11-17T21:20:06+00:00"},
                {"name": "healthStatus", "value": "unknown", "date": "2026-11-17T21:19:38+00:00"},
                {"name": "command-off", "type": "command", "date": "2026-11-18T13:30:03+00:00",
                 "producedBy": {"appId": 701}},
            ],
        })
        answer = source_only_partial_answer("Why do the activity and health timestamps differ?",
                                           [inventory, history])
        self.assertIn("`healthStatus` offline at Tuesday 17 November 2026 at 9:20:06 pm GMT", answer)
        self.assertIn("`lastActivity` Wednesday 18 November 2026 at 3:17:04 pm GMT", answer)
        self.assertIn("Neither identifies the operation that updated", answer)
        self.assertNotIn("4:00:00 pm GMT", answer)

    def test_qualified_findings_remain_publishable(self):
        events = receipt("hub_list_device_events", {"appId": 701}, {"events": []})
        for draft in (
            "No matching events were returned by this query.",
            "The read cannot establish complete coverage of the window.",
            "All returned rows in that window were OFF reports.",
            "These receipts cannot establish continuous logging.",
            "The returned rows do not prove that the device remained idle throughout.",
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

"""Fictional source-only System Health freshness regression tests.

No clocks queried from hub, no model calls or live devices. An old lastActivity
is a quiet-device observation, NOT proof the device is offline or defective.
"""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from home_overview import summarize_device_inventory, read_overview


NOW = datetime(2030, 7, 1, 12, 0, tzinfo=timezone.utc)


def reply(devices, total=None):
    payload = {"devices": devices}
    if total is not None:
        payload["total"] = total
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


class QuietDeviceCoverageTests(unittest.TestCase):
    def test_known_older_activity_not_conflated_with_offline(self):
        devices = [
            {"label": "Fixture sleepy sensor", "lastActivity": "2030-06-29T12:00:00Z",
             "currentStates": {"healthStatus": "online"}},
            {"label": "Fixture recent source", "lastActivity": "2030-07-01T11:55:00+0000"},
            {"label": "Fixture at boundary", "lastActivity": "2030-06-30T12:00:00+00:00"},
            {"label": "Fixture without timestamp"},
            {"label": "Fixture invalid source", "lastActivity": "2030-06-01T11:00:00"},
            {"label": "Fixture future date", "lastActivity": "2030-08-01T11:00:00Z"},
        ]
        result = summarize_device_inventory(reply(devices,total=6), observed_at=NOW)
        metric = result["metrics"]["last_activity_over_24h"]
        self.assertEqual(result["observed_at_utc"], NOW.isoformat())
        self.assertEqual(metric["count"], 1)
        self.assertEqual(metric["devices_with_state"], 3)
        self.assertEqual(metric["threshold_exclusive_hours"], 24)
        self.assertEqual(metric["members"], [
            {"name": "Fixture sleepy sensor", "inactive_hours": 48.0}])
        self.assertEqual(result["metrics"]["reported_offline"]["count"], 0)
        self.assertIn("not a proven offline device", " ".join(result["notes"]))

    def test_unknown_dates_and_invalid_clock_remain_unverified(self):
        for value in (None, "", "yesterday", "2030-06-28T00:00:00",
                      "2030-07-02T00:00:00+00:00", True):
            with self.subTest(value=value):
                result = summarize_device_inventory(
                    reply([{"label": "Fixture", "lastActivity": value}]),
                    observed_at=NOW)
                m = result["metrics"]["last_activity_over_24h"]
                self.assertEqual(m["count"], 0)
                self.assertEqual(m["devices_with_state"], 0)
        with self.assertRaises(ValueError):
            summarize_device_inventory(reply([]), observed_at=datetime(2030, 7, 1))

    def test_bounded_members_not_false_complete(self):
        devices = [
            {"label": f"Fixture {i:03d}", "lastActivity": "2030-06-01T00:00:00Z"}
            for i in range(270)]
        result = summarize_device_inventory(reply(devices,total=300),
                                           observed_at=NOW)
        metric = result["metrics"]["last_activity_over_24h"]
        self.assertEqual(metric["count"], 270)
        self.assertEqual(len(metric["members"]), 250)
        self.assertEqual(metric["members_omitted"], 20)
        self.assertFalse(result["inventory_full_coverage_verified"])

    def test_no_extra_mcp_calls_for_freshness(self):
        class FakeMCP:
            def __init__(self):
                self.calls = []
            async def list_tools(self):
                return [{"name": "hub_list_devices",
                         "inputSchema": {"type": "object", "properties": {}}}]
            async def call(self, name, args):
                self.calls.append((name,args))
                return reply([{"label": "Fixture offline report",
                               "lastActivity": "2026-01-01T00:00:00Z"}],total=1)
        # This test verifies exactly one original inventory call. New
        # categories are computed from returned data, not another Hub query.
        import asyncio
        hub = FakeMCP()
        result = asyncio.run(read_overview(hub))
        self.assertEqual(hub.calls, [("hub_list_devices", {})])
        self.assertEqual(result["metrics"]["last_activity_over_24h"]["count"], 1)


if __name__ == "__main__":
    unittest.main()

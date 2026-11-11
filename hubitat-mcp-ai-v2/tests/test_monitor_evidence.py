"""Gate B regressions for source-derived monitor evidence semantics.

All test values are fictional. No hub, model endpoint, credentials or device
actions are contacted. Metadata must not change source reads or model choice.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from monitor_evidence import monitor_evidence_scope


def history(device_id="LAB-001", metric="humidity", *, reported=0, held=0,
            unknown=288, null=0, absent=0):
    is_power = metric == "power"
    return {
        "source": "fictional saved-bin archive",
        "read_only": True,
        "device_id": device_id,
        "metric": metric,
        "unit": "W" if is_power else "%RH",
        "historical_start_utc": "2026-03-01T00:00:00+00:00",
        "historical_end_utc": "2026-03-02T00:00:00+00:00",
        "upstream_returned_window_start_utc": "2026-03-01T00:00:00+00:00",
        "upstream_returned_window_end_utc": "2026-03-02T00:00:00+00:00",
        "returned_resolution": "5m",
        "summary": {
            "expected_bin_positions": 288,
            "populated_bin_positions": 288-null-absent,
            "reported_bin": reported,
            "held_from_report": held,
            "sensor_freshness_unverified": unknown,
            "fresh_sensor_reports_verified": False if is_power else None,
            "sensor_freshness_known_from_source": None if is_power else False,
            "all_expected_bin_positions_populated": null+absent == 0,
            "explicit_null_bin_rows": null,
            "null_bin_positions_within_expected": null,
            "absent_bin_positions": absent,
            "saved_bin_extrema": {"lowest": {"value": 0.0}},
            "report_containing_saved_bin_extrema": (
                {"highest": {"value": 81.0}} if is_power and reported else None
            ),
            "coverage_complete": False,
        },
        "samples": [{"bin_start_utc": "2026-03-01T00:00:00+00:00",
                     "saved_value": 72,
                     "sample_class": "sensor_freshness_unverified"}],
    }


class SourceSemanticsTests(unittest.TestCase):
    def test_full_sensor_grid_does_not_prove_fresh_crossing(self):
        payload = history()
        mapped = monitor_evidence_scope({"local_device_monitor": payload})
        self.assertEqual(mapped["mode"], "history")
        scope = mapped["history"]
        self.assertEqual(scope["bins_with_sensor_freshness_unverified"], 288)
        self.assertTrue(scope["all_saved_bin_values_present"])
        self.assertFalse(scope["fresh_sensor_reports_independently_verified"])
        self.assertFalse(scope["source_verified_exact_physical_threshold_crossing_time"])
        self.assertFalse(scope["source_verified_continuous_physical_observation"])
        self.assertEqual(scope["saved_bin_extrema"], payload["summary"]["saved_bin_extrema"])
        self.assertIsNone(scope["reported_power_bin_extrema"])
        self.assertEqual(scope["requested_window_end_exclusive_utc"],
                         "2026-03-02T00:00:00+00:00")

    def test_reported_held_and_missing_power_bins_are_distinct(self):
        payload = history("LAB-002", "power", reported=228, held=51,
                          unknown=0, null=9)
        mapped = monitor_evidence_scope({"local_device_monitor": payload})
        scope = mapped["history"]
        self.assertEqual(scope["bins_containing_monitor_received_power_reports"], 228)
        self.assertEqual(scope["bins_held_from_previous_power_report"], 51)
        self.assertEqual(scope["explicit_null_bin_positions"], 9)
        self.assertEqual(scope["absent_bin_positions"], 0)
        self.assertEqual(scope["reported_power_bin_extrema"]["highest"]["value"], 81)
        self.assertFalse(scope["source_verified_instantaneous_physical_peak"])
        self.assertFalse(scope["source_verified_device_connection_or_offline_cause"])

    def test_all_null_bins_not_zero_power(self):
        payload = history("LAB-003", "power", reported=0, held=0, unknown=0,
                          null=288)
        mapped = monitor_evidence_scope({"local_device_monitor": payload})
        scope = mapped["history"]
        self.assertEqual(scope["bins_with_saved_values"], 0)
        self.assertEqual(scope["explicit_null_bin_positions"], 288)
        self.assertEqual(scope["absent_bin_positions"], 0)
        self.assertIsNone(scope["reported_power_bin_extrema"])
        self.assertFalse(scope["source_verified_device_connection_or_offline_cause"])

    def test_compare_maps_each_device_without_confusing_scope(self):
        first = history("LAB-004", "power", reported=228, held=51, unknown=0,
                        null=9)
        second = history("LAB-005", "power", reported=0, held=0, unknown=0,
                         null=288)
        rows = [{k: v for k, v in obj.items() if k != "samples"}
                for obj in (first, second)]
        mapped = monitor_evidence_scope({"local_device_monitor": {
            "read_only": True, "mode": "compare", "metric": "power",
            "shared_window_verified": True,
            "shared_window_start_utc": first["historical_start_utc"],
            "shared_window_end_exclusive_utc": first["historical_end_utc"],
            "devices": rows,
        }})
        self.assertTrue(mapped["same_requested_window_verified"])
        self.assertEqual(len(mapped["device_summaries"]), 2)
        self.assertEqual(mapped["device_summaries"][0]["explicit_null_bin_positions"], 9)
        self.assertEqual(mapped["device_summaries"][1]["explicit_null_bin_positions"], 288)
        self.assertFalse(mapped["causal_inference_supported"])

    def test_latest_value_status_is_not_historical_measurement(self):
        mapped = monitor_evidence_scope({"local_device_monitor": {
            "read_only": True, "monitor_observed_at_utc": "2026-03-02T00:10:00Z",
            "selected_devices": [{"id": "LAB-006", "power_w": 0.0,
                                  "power_fresh": False}],
        }})
        self.assertEqual(mapped["mode"], "status")
        self.assertEqual(mapped["selected_device_count"], 1)
        self.assertFalse(mapped["proves_historical_readings"])
        self.assertFalse(mapped["proves_historical_connectivity"])

    def test_no_fabricated_map_for_error_or_non_monitor_object(self):
        self.assertIsNone(monitor_evidence_scope({}))
        self.assertIsNone(monitor_evidence_scope({"local_device_monitor": {
            "read_only": False, "samples": [], "summary": {},
        }}))
        self.assertIsNone(monitor_evidence_scope({"local_device_monitor": {
            "read_only": True, "mode": "history", "samples": [],
        }}))


class FakeMCP:
    async def list_tools(self, refresh=False):
        return []

    async def call(self, name, args):
        raise AssertionError("Unexpected native call")


class FakeMonitor:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    async def query(self, args):
        self.calls.append(dict(args))
        return self.reply


class ScriptedAgent(Agent):
    def __init__(self):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 10)
        self.messages_seen = []
        self.turn = 0

    async def round(self, messages, tools, remaining):
        self.messages_seen.append([dict(m) for m in messages])
        self.turn += 1
        if self.turn == 1:
            return {"content": "", "tool_calls": [{
                "function": {"name": "homebrain_read_device_monitor",
                             "arguments": {"mode": "history", "device_id": "7107",
                                           "metric": "power", "range": "24h"}}
            }]}
        return {"content": "Source returned no numeric saved bins.", "tool_calls": []}


class MonitorAgentIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_compact_map_precedes_unmodified_history_response(self):
        payload = history("7107", "power", reported=0, held=0,
                          unknown=0, null=288)
        monitor = FakeMonitor(payload)
        agent = ScriptedAgent()
        try:
            result = await agent.answer("Show archived power yesterday", [],
                                        FakeMCP(), 90,
                                        enable_source_review=False,
                                        device_monitor=monitor)
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(len(monitor.calls), 1)
        first = json.loads(result["tool_calls"][0]["response"])
        self.assertEqual(next(iter(first)), "client_monitor_evidence_scope")
        self.assertEqual(first["local_device_monitor"], payload)
        self.assertEqual(first["client_monitor_evidence_scope"]["history"][
            "explicit_null_bin_positions"], 288)
        self.assertEqual(agent.messages_seen[1][-1]["content"],
                         result["tool_calls"][0]["response"])


if __name__ == "__main__":
    unittest.main()

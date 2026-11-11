"""Alpha.48 window and provenance regressions (fictional, offline fixtures).

No Hubitat/HA account, private receipts, OAuth token or actual monitor contacted.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from device_monitor import HubDeviceMonitor, _event_samples

BIN_MS = 300000


def ms(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


class IntervalSourceTests(unittest.TestCase):
    def test_exact_half_open_comparison_window_does_not_use_earlier_24h_peak(self):
        start = ms("2026-10-18T00:05:00Z")
        end = ms("2026-10-18T12:05:00Z")
        rows = {"series": [
            # Both BEFORE requested interval -- must not contaminate extrema.
            {"t": start - 3*BIN_MS, "w": 220, "powerReports": 3},
            {"t": start, "w": 0, "powerReports": 2},
            {"t": start + BIN_MS, "w": 0, "powerReports": 0,
             "powerSourceAt": start + 60_000},
            {"t": start + 2*BIN_MS, "w": None},
            # This timestamp deliberately has no row: missing BIN POSITION.
            {"t": ms("2026-10-18T02:50:00Z"), "w": 153, "powerReports": 4},
            {"t": ms("2026-10-18T09:20:00Z"), "w": 119, "powerReports": 2},
            {"t": end, "w": 800, "powerReports": 9},  # End EXCLUSIVE.
        ]}
        samples, summary = _event_samples(
            rows, "power", "999", start, end, resolution="5m")
        self.assertEqual(summary["expected_bin_positions"], 144)
        self.assertEqual(summary["populated_bin_positions"], 4)
        self.assertEqual(summary["reported_bin"], 3)
        self.assertEqual(summary["held_from_report"], 1)
        self.assertEqual(summary["explicit_null_bin_rows"], 1)
        self.assertEqual(summary["absent_bin_positions"], 139)
        self.assertEqual(summary["missing_bin_positions_total"], 140)
        self.assertEqual(summary["ignored_outside_window_rows"], 2)
        self.assertEqual(summary["power_report_rows_in_bins"], 8)
        self.assertEqual(summary["highest_report_containing_saved_bin"]["value"], 153)
        self.assertEqual(
            summary["highest_report_containing_saved_bin"]["bin_start_utc"],
            "2026-10-18T02:50:00.000+00:00",
        )
        self.assertFalse(summary["all_expected_bin_positions_populated"])
        self.assertFalse(summary["coverage_complete"])
        self.assertFalse(summary["continuous_physical_peak_verified"])
        self.assertEqual(len(samples), 4)

    def test_full_grid_does_not_prove_continuous_observation(self):
        start = ms("2026-10-18T00:00:00Z")
        end = start + 4*BIN_MS
        rows = {"series": [
            {"t": start, "w": 10, "powerReports": 1},
            {"t": start + BIN_MS, "w": 10, "powerReports": 0,
             "powerSourceAt": start+15_000},
            {"t": start + 2*BIN_MS, "w": 12, "powerReports": 1},
            {"t": start + 3*BIN_MS, "w": 12, "powerReports": 0,
             "powerSourceAt": start + 2*BIN_MS + 30_000},
        ]}
        samples, s = _event_samples(rows, "power", "101", start, end)
        self.assertEqual(s["expected_bin_positions"], 4)
        self.assertEqual(s["missing_bin_positions_total"], 0)
        self.assertTrue(s["all_expected_bin_positions_populated"])
        self.assertEqual(s["held_from_report"], 2)
        self.assertEqual(s["reported_bin"], 2)
        self.assertFalse(s["coverage_complete"])
        self.assertTrue(s["bin_grid_complete_does_not_prove_observation_continuity"])
        self.assertEqual(samples[1]["sample_class"], "held_from_report")

    def test_sensor_bins_are_not_definitely_stale_or_fresh(self):
        start = ms("2026-10-18T20:00:00Z")
        end = start + 4*BIN_MS
        records = {"sensors": [{"id": "42", "series": [
            {"t": start, "tempC": 22.2},
            {"t": start + BIN_MS, "tempC": 22.1},
            {"t": start + 2*BIN_MS, "tempC": 21.3},
            {"t": start + 3*BIN_MS, "tempC": 21.3},
        ]}]}
        samples, summary = _event_samples(
            records, "temperature", "42", start, end)
        self.assertTrue(summary["all_expected_bin_positions_populated"])
        self.assertEqual(summary["sensor_freshness_unverified"], 4)
        self.assertFalse(summary["sensor_freshness_known_from_source"])
        self.assertIsNone(summary["fresh_sensor_reports_verified"])
        self.assertTrue(all(s["sample_class"] == "sensor_freshness_unverified"
                            for s in samples))
        self.assertTrue(all(s["fresh_sensor_report_verified"] is False
                            for s in samples))
        self.assertEqual(summary["saved_bin_extrema"]["highest"]["value"], 22.2)
        self.assertEqual(summary["saved_bin_extrema"]["lowest"]["value"], 21.3)
        self.assertEqual(
            summary["saved_bin_extrema"]["lowest"]["bin_start_utc"],
            "2026-10-18T20:10:00.000+00:00")
        self.assertIsNone(summary["report_containing_saved_bin_extrema"])
        self.assertFalse(summary["coverage_complete"])

    def test_humidity_missing_and_held_are_distinct_from_null_or_absent(self):
        start = ms("2026-10-18T12:00:00Z")
        end = start + 5*BIN_MS
        records = {"sensors": [{"id": "7", "series": [
            {"t": start, "humidityPct": 50},
            {"t": start + BIN_MS, "humidityPct": None},
            {"t": start + 3*BIN_MS, "humidityPct": 88},
            {"t": start + 4*BIN_MS, "humidityPct": 55},
        ]}]}
        samples, s = _event_samples(records, "humidity", "7", start, end)
        self.assertEqual(s["expected_bin_positions"], 5)
        self.assertEqual(s["returned_non_null_bins"], 3)
        self.assertEqual(s["explicit_null_bin_rows"], 1)
        self.assertEqual(s["absent_bin_positions"], 1)
        self.assertEqual(s["missing_bin_positions_total"], 2)
        self.assertEqual(s["saved_bin_extrema"]["highest"]["value"], 88)
        self.assertEqual(s["saved_bin_extrema"]["lowest"]["value"], 50)
        self.assertIsNone(s["fresh_sensor_reports_verified"])
        self.assertEqual(s["sensor_freshness_unverified"], 3)

    def test_unfiltered_response_can_be_out_of_order_but_bins_sort(self):
        start = ms("2026-10-18T00:00:00Z")
        rows = {"series": [
            {"t": start + BIN_MS, "w": 60, "powerReports": 1},
            {"t": start, "w": 45, "powerReports": 1},
        ]}
        samples, s = _event_samples(rows,"power","1",start,start+2*BIN_MS)
        self.assertEqual([row["saved_value"] for row in samples],[45,60])
        self.assertEqual(s["saved_bin_extrema"]["highest"]["value"],60)

    def test_duplicate_bins_rejected_instead_of_claiming_extrema(self):
        start = ms("2026-10-18T00:00:00Z")
        rows = {"series": [
            {"t": start, "w": 20, "powerReports": 1},
            {"t": start, "w": 120, "powerReports": 1},
        ]}
        with self.assertRaisesRegex(ValueError, "duplicate timestamp"):
            _event_samples(rows,"power","1",start,start+BIN_MS)


class ControlledHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def setUp(self):
        self.requests = []
        self.monitor = HubDeviceMonitor(
            "http://192.168.1.239/apps/api/1234",
            "FICTIONAL_TEST_ACCESS_TOKEN_LENGTH_1234567890",
        )
        await self.monitor._client.aclose()
        def response(request):
            self.requests.append(request)
            return httpx.Response(200, json={
                "success": True, "device": "77", "resolution": "5m",
                # Upstream returned boundaries do not define the *requested*
                # interval when the bridge passes custom from/to.
                "start": ms("2026-10-18T12:00:00Z"),
                "end": ms("2026-10-19T12:00:00Z"),
                "series": [], "note": "test-only archive",
            })
        self.monitor._client = httpx.AsyncClient(
            transport=httpx.MockTransport(response), follow_redirects=False)

    async def asyncTearDown(self):
        await self.monitor.close()

    async def test_missing_custom_end_rejected_without_network_call(self):
        for args in (
            {"mode": "history", "device_id": "77",
             "metric": "temperature", "range": "custom",
             "start": "2026-10-18T00:00:00Z"},
            {"mode": "history", "device_id": "77",
             "metric": "temperature", "range": "custom",
             "end": "2026-10-18T00:00:00Z"},
        ):
            with self.assertRaisesRegex(ValueError, "requires BOTH start and end"):
                await self.monitor.query(args)
        self.assertEqual(self.requests, [])

    async def test_12h_uses_exact_custom_query_without_claiming_24h(self):
        before = datetime.now(timezone.utc)
        result = await self.monitor.query({
            "mode": "history", "device_id": "77",
            "metric": "power", "range": "12h",
        })
        after = datetime.now(timezone.utc)
        self.assertEqual(result["range"], "12h")
        q = self.requests[0].url.params
        self.assertEqual(q["range"], "custom")
        self.assertEqual(q["device"], "77")
        start = datetime.fromtimestamp(int(q["from"])/1000,timezone.utc)
        end = datetime.fromtimestamp(int(q["to"])/1000,timezone.utc)
        self.assertGreaterEqual(end, before-timedelta(seconds=1))
        self.assertLessEqual(end, after+timedelta(seconds=1))
        self.assertAlmostEqual((end-start).total_seconds(), 43200, delta=1)
        self.assertEqual(result["summary"]["window_start_utc"],
                         result["historical_start_utc"])
        self.assertEqual(result["summary"]["window_end_exclusive_utc"],
                         result["historical_end_utc"])
        self.assertEqual(result["summary"]["missing_bin_positions_total"], 144)
        self.assertFalse(result["summary"]["coverage_complete"])

    async def test_same_custom_window_summaries_not_24h_upstream(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        result = await self.monitor.query({
            "mode": "history", "device_id": "77", "metric": "power",
            "range": "custom", "start": (now-timedelta(hours=8)).isoformat(),
            "end": (now-timedelta(hours=1)).isoformat(),
        })
        self.assertAlmostEqual(
            (datetime.fromisoformat(result["historical_end_utc"]) -
             datetime.fromisoformat(result["historical_start_utc"])).total_seconds(),
            7*3600, delta=1)
        self.assertLessEqual(result["summary"]["expected_bin_positions"],85)
        self.assertEqual(result["summary"]["populated_bin_positions"],0)
        self.assertEqual(result["summary"]["missing_bin_positions_total"],
                         result["summary"]["expected_bin_positions"])
        self.assertFalse(result["summary"]["coverage_complete"])


if __name__ == "__main__":
    unittest.main()

"""Alpha.49 fictional multi-device history comparison and gap-run regressions.

No live Hubitat/HA/OAuth endpoint contacted. These prove only local contracts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from device_monitor import HubDeviceMonitor, _event_samples, TOOL_DEFINITION
from investigation_review import is_read_only_review_tool

STEP = 300_000
TOKEN = "FICTIONAL_TEST_ACCESS_TOKEN_LENGTH_12345678"


def ms(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()*1000)


class GapRunTests(unittest.TestCase):
    def test_null_absent_and_held_are_distinct_and_runs_are_bounded(self):
        start = ms("2026-10-18T00:00:00Z")
        end = start + STEP*10
        rows = {"series":[
            {"t":start,"w":30,"powerReports":1},
            {"t":start+STEP,"w":30,"powerReports":0,"powerSourceAt":start+50_000},
            # 2, 3 absent
            {"t":start+4*STEP,"w":None},
            {"t":start+5*STEP,"w":45,"powerReports":1},
            {"t":start+6*STEP,"w":45,"powerReports":0,"powerSourceAt":start+5*STEP},
            {"t":start+7*STEP,"w":None},
            # 8 absent
            {"t":start+9*STEP,"w":40,"powerReports":1},
        ]}
        samples,s = _event_samples(rows,"power","1",start,end)
        self.assertEqual(s["expected_bin_positions"],10)
        self.assertEqual(s["populated_bin_positions"],5)
        self.assertEqual(s["absent_bin_positions"],3)
        self.assertEqual(s["explicit_null_bin_rows"],2)
        self.assertEqual(s["missing_bin_positions_total"],5)
        self.assertEqual(s["held_from_report"],2)
        missing=s["missing_runs"]
        self.assertEqual(missing["count"],2)
        self.assertEqual(missing["total_bin_positions"],5)
        self.assertEqual(missing["longest"]["bin_count"],3)
        self.assertEqual(missing["longest"]["start_utc"],"2026-10-18T00:10:00.000+00:00")
        self.assertEqual(missing["longest"]["end_exclusive_utc"],"2026-10-18T00:25:00.000+00:00")
        self.assertEqual(s["held_value_runs"]["count"],2)
        self.assertEqual(s["held_value_runs"]["total_bin_positions"],2)
        self.assertEqual(s["highest_report_containing_saved_bin"]["value"],45)
        self.assertFalse(s["coverage_complete"])
        self.assertFalse(s["continuous_physical_peak_verified"])
        self.assertFalse(s["all_expected_bin_positions_populated"])

    def test_long_gap_run_not_split_by_truncated_preview(self):
        start=ms("2026-10-18T00:00:00Z")
        end=start+288*STEP
        samples,s=_event_samples({"series":[]}, "power","1",start,end)
        self.assertEqual(len(samples),0)
        self.assertEqual(s["missing_runs"]["count"],1)
        self.assertEqual(s["missing_runs"]["longest"]["bin_count"],288)
        self.assertEqual(s["missing_runs"]["longest"]["duration_minutes"],1440)
        self.assertEqual(s["absent_bin_positions"],288)
        self.assertEqual(s["explicit_null_bin_rows"],0)
        self.assertEqual(s["held_value_runs"]["count"],0)

    def test_humidity_can_have_missing_runs_without_report_freshness_claim(self):
        start=ms("2026-10-18T00:00:00Z")
        raw={"sensors":[{"id":"9","series":[
            {"t":start,"humidityPct":67},
            {"t":start+3*STEP,"humidityPct":70},
        ]}]}
        _,s=_event_samples(raw,"humidity","9",start,start+5*STEP)
        self.assertEqual(s["sensor_freshness_unverified"],2)
        self.assertEqual(s["missing_runs"]["count"],2)
        self.assertIsNone(s["held_value_runs"])
        self.assertIsNone(s["report_containing_saved_bin_extrema"])
        self.assertFalse(s["sensor_freshness_known_from_source"])

    def test_compare_advertised_and_read_only(self):
        fn=TOOL_DEFINITION["function"]
        self.assertIn("compare",fn["parameters"]["properties"]["mode"]["enum"])
        self.assertIn("device_ids",fn["parameters"]["properties"])
        self.assertTrue(is_read_only_review_tool(fn["name"]))


class FictionalMonitorHTTP(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests=[]
        self.monitor=HubDeviceMonitor(
            "http://192.168.1.239/apps/api/1234",TOKEN)
        await self.monitor._client.aclose()
        def response(request):
            self.requests.append(request)
            assert request.method=="GET"
            assert request.url.path.endswith("/api/history")
            assert request.url.params["access_token"]==TOKEN
            start=int(request.url.params["from"])
            end=int(request.url.params["to"])
            device_id=request.url.params["device"]
            # Physical five-minute monitor bins remain clock-aligned even
            # when a custom requested time has seconds/minutes off-grid.
            first=((start+STEP-1)//STEP)*STEP
            if device_id=="101":
                rows=[
                    {"t":first,"w":25,"powerReports":1,
                     "powerSourceAt":first+5000},
                    {"t":first+STEP,"w":25,"powerReports":0,
                     "powerSourceAt":first+5000},
                    {"t":first+2*STEP,"w":None},
                    {"t":first+4*STEP,"w":72,"powerReports":2,
                     "powerSourceAt":first+4*STEP+15000},
                ]
            else:
                rows=[{"t":first,"w":0,"powerReports":1,
                       "powerSourceAt":first+1000},
                      {"t":first+3*STEP,"w":14,"powerReports":1,
                       "powerSourceAt":first+3*STEP+15000}]
            return httpx.Response(200,json={
                "success":True, "device":device_id,"resolution":"5m",
                "start":start,"end":end-950,"series":rows,
                "note":"fictional saved bins only",
            })
        self.monitor._client=httpx.AsyncClient(
            transport=httpx.MockTransport(response),
            follow_redirects=False,
        )

    async def asyncTearDown(self):
        await self.monitor.close()

    async def test_compare_two_devices_one_shared_relative_window(self):
        before=datetime.now(timezone.utc)
        data=await self.monitor.query({
            "mode":"compare","device_ids":["101","202"],
            "metric":"power","range":"12h",
        })
        after=datetime.now(timezone.utc)
        self.assertEqual(data["mode"],"compare")
        self.assertEqual(data["monitored_device_count"],2)
        self.assertTrue(data["shared_window_verified"])
        self.assertTrue(data["relative_end_aligned_to_last_complete_5m_boundary"])
        self.assertEqual(len(self.requests),2)
        a,b=[r.url.params for r in self.requests]
        for key in ("range","from","to"):
            self.assertEqual(a[key],b[key])
        self.assertEqual(a["range"],"custom")
        aligned=datetime.fromtimestamp(int(a["to"])/1000,timezone.utc)
        self.assertEqual(int(a["to"])%STEP,0)
        self.assertLessEqual(aligned,after)
        self.assertGreater(aligned,before-timedelta(minutes=5,seconds=2))
        self.assertEqual(int(a["to"])-int(a["from"]),12*3600*1000)
        self.assertEqual(data["shared_window_end_exclusive_utc"],aligned.isoformat())
        first,second=data["devices"]
        self.assertEqual(first["requested_interval_start_utc"],
                         second["requested_interval_start_utc"])
        self.assertEqual(first["requested_interval_end_exclusive_utc"],
                         second["requested_interval_end_exclusive_utc"])
        self.assertEqual(first["summary"]["highest_report_containing_saved_bin"]["value"],72)
        self.assertEqual(second["summary"]["highest_report_containing_saved_bin"]["value"],14)
        self.assertEqual(first["summary"]["missing_runs"]["count"],2)
        self.assertEqual(first["summary"]["held_value_runs"]["count"],1)
        self.assertEqual(first["summary"]["absent_bin_positions"],140)
        self.assertEqual(first["summary"]["explicit_null_bin_rows"],1)
        self.assertEqual(first["saved_sample_count"],3)
        self.assertFalse(first["full_sample_list_included"])
        self.assertNotIn("samples",first)
        self.assertNotIn(TOKEN,json.dumps(data))
        self.assertNotIn("192.168.1.239",json.dumps(data))
        self.assertFalse(first["summary"]["coverage_complete"])
        self.assertEqual(data["source_note"].find("SAME saved-history source")>=0,True)

    async def test_compare_explicit_window_preserves_offset_not_rounded(self):
        start=(datetime.now(timezone.utc)-timedelta(hours=6,minutes=1)).replace(microsecond=0)
        end=start+timedelta(hours=6)
        data=await self.monitor.query({
            "mode":"compare","device_ids":["101","202"],"range":"custom",
            "start":start.isoformat(),"end":end.isoformat()
        })
        self.assertFalse(data["relative_end_aligned_to_last_complete_5m_boundary"])
        self.assertEqual(int(self.requests[0].url.params["from"]),int(start.timestamp()*1000))
        self.assertEqual(int(self.requests[0].url.params["to"]),int(end.timestamp()*1000))
        self.assertEqual(self.requests[0].url.params["from"],
                         self.requests[1].url.params["from"])
        self.assertEqual(self.requests[0].url.params["to"],
                         self.requests[1].url.params["to"])

    async def test_invalid_devices_and_custom_period_never_send_network(self):
        invalid=[
            {"device_ids":["101"]},
            {"device_ids":["101","101"]},
            {"device_ids":["101","?"]},
            {"device_ids":["101","202","303","404","505","606"]},
            {"device_ids":["101","202"],"range":"custom"},
            {"device_ids":["101","202"],"range":"custom","start":"2026-10-18T00:00:00Z"},
            {"device_ids":["101","202"],"range":"3d"},
            {"device_ids":["101","202"],"metric":"invalid"},
        ]
        for values in invalid:
            with self.subTest(values=values),self.assertRaises(ValueError):
                await self.monitor.query({"mode":"compare",**values})
        self.assertEqual(self.requests,[])

    async def test_rejected_one_source_does_not_claim_complete_comparison(self):
        # A successful first device followed by a 403 aborts the comparison;
        # no misleading complete result or token-bearing error is returned.
        def respond(request):
            self.requests.append(request)
            if request.url.params["device"]=="101":
                return httpx.Response(200,json={
                    "success":True, "device":"101", "resolution":"5m",
                    "start":int(request.url.params["from"]),
                    "end":int(request.url.params["to"]), "series":[],
                })
            return httpx.Response(403,text="Sensitive upstream error")
        await self.monitor._client.aclose()
        self.monitor._client=httpx.AsyncClient(
            transport=httpx.MockTransport(respond),follow_redirects=False)
        with self.assertRaisesRegex(ValueError,"access denied"):
            await self.monitor.query({
                "mode":"compare","device_ids":["101","202"],"range":"12h"
            })
        self.assertEqual(len(self.requests),2)


if __name__=="__main__":
    unittest.main()

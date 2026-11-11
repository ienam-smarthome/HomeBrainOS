"""Alpha.45 monitor bridge: completely fictional HTTP and agent fixtures.

No Hubitat, HA, model, OAuth service or production monitor contacted.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent
from device_monitor import (
    HubDeviceMonitor, TOOL_NAME, _event_samples, validate_api_base,
)
from investigation_review import is_read_only_review_tool


TOKEN = "FAKE_TEST_MONITOR_SECRET_ABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = "http://192.168.1.239/apps/api/1234"


class SourceContractTests(unittest.TestCase):
    def test_lan_only_no_url_secrets_or_arbitrary_paths(self):
        self.assertEqual(validate_api_base(BASE + "/"), BASE)
        for value in (
            "https://192.168.1.239/apps/api/1234",
            "http://127.0.0.1/apps/api/1234",
            "http://169.254.1.1/apps/api/1234",
            "http://example.org/apps/api/1234",
            "http://192.168.1.239:9090/apps/api/1234",
            "http://192.168.1.239/apps/api/1234/dashboard",
            BASE + "?access_token=" + TOKEN,
            "http://user:password@192.168.1.239/apps/api/1234",
            "http://[::1]/apps/api/1234",
            "http://192.168.1.239/apps/api/1234/../../private",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_api_base(value)
        self.assertTrue(is_read_only_review_tool(TOOL_NAME))

    def test_provenance_is_not_a_continuous_physical_peak(self):
        rows = {
            "series": [
                {"t": 1760100000000, "w": 290, "powerReports": 3,
                 "powerSourceAt": 1760100010000},
                {"t": 1760100300000, "w": 290, "powerReports": 0,
                 "powerSourceAt": 1760100010000},
                {"t": 1760100600000, "w": 0, "powerReports": 1,
                 "powerSourceAt": 1760100630000},
                {"t": 1760100900000, "w": None, "powerTracked": True},
                {"t": 1760101200000, "w": 4},
            ]
        }
        points, summary = _event_samples(rows, "power", "42", None, None)
        self.assertEqual([p["sample_class"] for p in points], [
            "reported_bin", "held_from_report", "reported_bin", "unclassified_bin",
        ])
        self.assertEqual(summary["returned_null_or_unclassified_missing_bins"], 1)
        self.assertEqual(summary["reported_bin"], 2)
        self.assertEqual(summary["highest_report_containing_saved_bin"]["value"], 290)
        self.assertEqual(summary["lowest_report_containing_saved_bin"]["value"], 0)
        self.assertFalse(summary["continuous_physical_peak_verified"])

    def test_sensor_cache_is_not_new_physical_report(self):
        rows = {"sensors": [{"id": "42", "series": [
            {"t": 1760100000000, "tempC": 21.9},
            {"t": 1760100300000, "tempC": 21.9},
        ]}]}
        points, summary = _event_samples(rows, "temperature", "42", None, None)
        self.assertEqual(len(points), 2)
        self.assertEqual(summary["derived_or_held_sensor_bin"], 2)
        self.assertNotIn("highest_report_containing_saved_bin", summary)


class FakeMonitor:
    def __init__(self):
        self.requests = []
        self.response_status = {"success": True, "version": "0.3.27",
            "now": 1760101200000, "timeZone": "Europe/London",
            "instanceName": "Fictional Monitor", "monitorMode": "both",
            "sampling": {"status": "ok", "lastDeviceSuccess": 1760101200000},
            "devices": [
                {"id": "42", "name": "Synthetic Pump", "hasPower": True,
                 "powerW": 4, "powerFresh": True, "lastPowerEventAt": 1760101000000},
            ],
        }
        self.response_history = {
            "success": True, "device": "42", "range": "24h",
            "start": 1760014800000, "end": 1760101200000,
            "resolution": "5m", "note": "saved bins; gaps are unknown",
            "series": [
                {"t": 1760100000000, "w": 280, "powerTracked": True,
                 "powerReports": 1, "powerSourceAt": 1760100010000,
                 "powerReportAt": 1760100010000},
                {"t": 1760100300000, "w": 280, "powerTracked": True,
                 "powerReports": 0, "powerSourceAt": 1760100010000},
                {"t": 1760100600000, "w": None, "powerTracked": True},
                {"t": 1760100900000, "w": 0, "powerTracked": True,
                 "powerReports": 1, "powerSourceAt": 1760100900000},
            ],
        }

    def transport(self, request):
        self.requests.append(request)
        assert request.method == "GET"
        assert request.url.host == "192.168.1.239"
        assert request.url.params["access_token"] == TOKEN
        if request.url.path.endswith("/api/status"):
            return httpx.Response(200, json=self.response_status)
        if request.url.path.endswith("/api/history"):
            return httpx.Response(200, json=self.response_history)
        return httpx.Response(404)


async def client_with_fake(f):
    client = HubDeviceMonitor(BASE, TOKEN)
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(f.transport))
    return client


class MonitorHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_and_history_keep_token_out_of_model_data(self):
        f = FakeMonitor()
        client = await client_with_fake(f)
        try:
            status = await client.query({"mode": "status"})
            data = await client.query({"mode": "history", "device_id": "42",
                                       "metric": "power", "range": "24h"})
        finally:
            await client.close()
        self.assertEqual(len(f.requests), 2)
        self.assertEqual(f.requests[1].url.params["device"], "42")
        self.assertEqual(f.requests[1].url.params["range"], "24h")
        self.assertNotIn(TOKEN, json.dumps([status, data]))
        self.assertNotIn(BASE, json.dumps([status, data]))
        self.assertEqual(status["selected_devices"][0]["power_w"], 4)
        self.assertEqual(data["summary"]["reported_bin"], 2)
        self.assertEqual(data["summary"]["held_from_report"], 1)
        self.assertEqual(data["summary"]["returned_null_or_unclassified_missing_bins"], 1)
        self.assertEqual(data["summary"]["highest_report_containing_saved_bin"]["value"], 280)
        self.assertEqual(data["summary"]["lowest_report_containing_saved_bin"]["value"], 0)
        self.assertEqual(data["samples"][1]["sample_class"], "held_from_report")

    async def test_custom_window_becomes_epoch_ms_without_timezone_guess(self):
        f = FakeMonitor()
        client = await client_with_fake(f)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        start = now - timedelta(hours=8)
        end = now - timedelta(minutes=20)
        try:
            result = await client.query({
                "mode": "history", "device_id": "42",
                "range": "custom", "start": start.isoformat(),
                "end": end.isoformat(), "metric": "power",
            })
            self.assertEqual(result["range"], "custom")
            request = f.requests[0]
            self.assertEqual(int(request.url.params["from"]), int(start.timestamp()*1000))
            self.assertEqual(int(request.url.params["to"]), int(end.timestamp()*1000))
            before = len(f.requests)
            for bad in (
                {"mode":"history", "device_id":"42","range":"custom",
                 "start":"2026-11-10 20:00","end":end.isoformat()},
                {"mode":"history", "device_id":"42","range":"custom",
                 "start":end.isoformat(),"end":start.isoformat()},
                {"mode":"history", "device_id":"42","range":"custom",
                 "start":start.isoformat(),"end":(now+timedelta(days=2)).isoformat()},
                {"mode":"history", "device_id":"42","range":"24h",
                 "start":start.isoformat()},
                {"mode":"history", "device_id":"../123", "range":"24h"},
            ):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    await client.query(bad)
            self.assertEqual(len(f.requests), before)
        finally:
            await client.close()

    async def test_mismatch_daily_energy_auth_and_redirect_are_rejected(self):
        for kind in ("daily", "wrong_device", "auth", "redirect"):
            f = FakeMonitor()
            if kind == "daily":
                f.response_history["resolution"] = "daily"
            if kind == "wrong_device":
                f.response_history["device"] = "52"
            def respond(request):
                if kind == "auth": return httpx.Response(403, text="oauth denied")
                if kind == "redirect": return httpx.Response(302, headers={"Location":"http://example.org/"})
                return f.transport(request)
            client = HubDeviceMonitor(BASE,TOKEN)
            await client._client.aclose()
            client._client = httpx.AsyncClient(transport=httpx.MockTransport(respond),
                                               follow_redirects=False)
            try:
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    await client.query({"mode":"history", "device_id":"42"})
            finally:
                await client.close()


class FakeNativeMCP:
    def __init__(self): self.calls = []
    async def list_tools(self, refresh=False):
        return [{"name":"hub_read_devices","inputSchema":{
            "type":"object","properties":{}}}]
    async def call(self, name, args):
        self.calls.append((name,args))
        return {"content":[{"type":"text","text":"{}"}]}


class FakeModelAgent(Agent):
    def __init__(self,replies):
        super().__init__("http://127.0.0.1:11434","fixture","",15)
        self.replies=list(replies)
        self.tool_catalogs=[]
        self.seen_messages=[]
    async def round(self,messages,tools,remaining):
        self.tool_catalogs.append([t["function"]["name"] for t in tools])
        self.seen_messages.append([dict(x) for x in messages])
        return self.replies.pop(0)


def call(mode, **kwargs):
    return {"function":{"name":TOOL_NAME,"arguments":{"mode":mode, **kwargs}}}


class AgentIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_autonomously_reads_existing_saved_history(self):
        f = FakeMonitor()
        client = await client_with_fake(f)
        model = FakeModelAgent([
            {"content":"","tool_calls":[call("status")]},
            {"content":"The native query has no matching power rows.","tool_calls":[]},
            {"content":"","tool_calls":[call("history",device_id="42",metric="power",range="24h")]},
            {"content":"Saved report-containing 5-minute bins include 280 W and 0 W; longer gaps remain unknown.",
             "tool_calls":[]},
        ])
        hub=FakeNativeMCP()
        try:
            reply=await model.answer("Show synthetic pump's power last night",[],hub,90,device_monitor=client)
        finally:
            await model.close()
            await client.close()
        self.assertTrue(reply["success"])
        self.assertTrue(reply["source_review_invoked"])
        self.assertEqual(reply["source_review_kind"],"historical_measurement")
        self.assertEqual(reply["rounds"],4)
        self.assertEqual(hub.calls,[])
        self.assertEqual(len(reply["tool_calls"]),2)
        self.assertEqual([r["result_kind"] for r in reply["tool_calls"]],
                         ["local_monitor_read","local_monitor_read"])
        self.assertIn(TOOL_NAME,model.tool_catalogs[0])
        self.assertIn(TOOL_NAME,model.tool_catalogs[2])
        self.assertNotIn(TOKEN,json.dumps(reply))
        self.assertIn("280 W",reply["answer"])

    async def test_not_configured_means_not_advertised(self):
        model=FakeModelAgent([{"content":"No monitor source is configured.","tool_calls":[]}])
        try:
            reply=await model.answer("Show current sensors",[],FakeNativeMCP(),90)
        finally:
            await model.close()
        self.assertNotIn(TOOL_NAME,model.tool_catalogs[0])
        self.assertFalse(reply["source_review_invoked"])


if __name__ == "__main__":
    unittest.main()

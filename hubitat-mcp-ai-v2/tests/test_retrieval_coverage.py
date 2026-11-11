"""Alpha.47 source visibility and retrieval completeness, fictional receipts only."""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from retrieval_coverage import FileReadCoverage, event_attribute_scope, file_chunk_scope
from investigation_review import is_historical_measurement_question, review_kind


def mcp_reply(value):
    return {"content": [{"type": "text", "text": json.dumps(value)}]}


class NativeEvidenceScopeTests(unittest.TestCase):
    def test_per_attribute_time_not_reassigned_to_power(self):
        original = mcp_reply({"events": [
            {"name": "amperage", "value": "0.475",
             "date": "2026-10-18T01:03:00Z"},
            {"name": "energy", "value": "11.0",
             "date": "2026-10-18T06:42:00Z"},
            {"name": "power", "value": "4",
             "date": "2026-10-18T11:03:00+00:00"},
            {"name": "power", "value": "3",
             "date": "2026-10-18T11:22:00+00:00"},
        ], "attributeFilter": None})
        report = event_attribute_scope(original)
        names = {a["event_name"]: a for a in report["event_names"]}
        self.assertEqual(names["power"]["returned_count"], 2)
        self.assertEqual(names["power"]["first_returned_event_utc"],
                         "2026-10-18T11:03:00+00:00")
        self.assertEqual(names["power"]["last_returned_event_utc"],
                         "2026-10-18T11:22:00+00:00")
        self.assertEqual(names["amperage"]["last_returned_event_utc"],
                         "2026-10-18T01:03:00+00:00")
        self.assertFalse(report["can_infer_continuous_history_coverage"])
        self.assertFalse(report["can_infer_absent_events_not_in_result"])
        self.assertEqual(original["content"][0]["text"],
                         mcp_reply(json.loads(original["content"][0]["text"]))["content"][0]["text"])

    def test_empty_filtered_events_are_not_inferred_absence(self):
        data = event_attribute_scope(mcp_reply({
            "events": [], "attributeFilter": "power"}))
        self.assertEqual(data["events_returned"], 0)
        self.assertEqual(data["event_names"], [])
        self.assertEqual(data["requested_attribute_filter"], "power")
        self.assertFalse(data["can_infer_absent_events_not_in_result"])

    def test_file_chunk_missing_ranges_and_repeated_overlap(self):
        coverage = FileReadCoverage()
        pieces = [
            (0, 100), (250, 350), (500, 600), (250, 350),
            (100, 250), (350, 500), (600, 1000),
        ]
        for i, (start, end) in enumerate(pieces):
            scope = file_chunk_scope(mcp_reply({
                "success": True, "fileName": "synthetic_20261018.json",
                "totalLength": 1000, "offset": start,
                "chunkLength": end-start, "content": "x"*(end-start),
                "hasMore": i != len(pieces)-1,
            }))
            self.assertIsNotNone(scope)
            report = coverage.add(scope)
            self.assertFalse(report["can_claim_matching_records_absent_in_unread_ranges"])
        self.assertEqual(report["read_requests"], 7)
        self.assertEqual(report["retrieved_percent"], 100)
        self.assertTrue(report["file_completely_retrieved"])
        self.assertEqual(coverage.snapshot()[0]["retrieved_characters_unique"], 1000)

    def test_partial_file_end_does_not_prove_file_empty(self):
        tracker = FileReadCoverage()
        for start, end in ((0, 300), (1000, 1300), (2000, 2300),
                           (3000, 3300), (4000, 4600)):
            scope = file_chunk_scope(mcp_reply({
                "fileName": "simulated_data.json", "totalLength": 5179,
                "offset": start, "chunkLength": end-start,
                "content": "x"*(end-start), "hasMore": True}))
            state = tracker.add(scope)
        self.assertLess(state["retrieved_percent"], 40)
        self.assertGreater(state["unread_range_count"], 0)
        self.assertFalse(state["file_completely_retrieved"])
        self.assertTrue(state["first_unread_ranges"])
        self.assertFalse(tracker.snapshot()[0]["file_completely_retrieved"])

    def test_file_claimed_length_cannot_expand_actual_contents(self):
        scope = file_chunk_scope(mcp_reply({
            "fileName": "synthetic.json", "totalLength": 1000, "offset": 100,
            "chunkLength": 500, "content": "x"*120, "hasMore": True
        }))
        self.assertEqual(scope["returned_end_exclusive"], 220)
        self.assertFalse(scope["file_fully_read_by_this_chunk"])

    def test_history_source_inventory_question_invokes_review(self):
        text = "Show the available sensors and identify which have saved history"
        self.assertTrue(is_historical_measurement_question(text))
        self.assertEqual(review_kind(text), "historical_measurement")
        for text in ("Show current device status", "Turn off a device and save history",
                     "What is Hubitat's firmware version?"):
            self.assertFalse(is_historical_measurement_question(text), text)


class ScriptedAgent(Agent):
    def __init__(self, replies):
        super().__init__("http://127.0.0.1:11434", "fictional-model", "", 10)
        self.replies=list(replies)
        self.messages_seen=[]
        self.tool_names_seen=[]
    async def round(self, messages, tools, remaining):
        self.messages_seen.append([dict(x) for x in messages])
        self.tool_names_seen.append([x["function"]["name"] for x in tools])
        return self.replies.pop(0)


class FakeMCP:
    async def list_tools(self, refresh=False):
        return [{"name":"hub_read_file","inputSchema":{"type":"object",
               "properties":{"fileName":{"type":"string"}}}}]
    async def call(self, name, args):
        assert name == "hub_read_file"
        return mcp_reply({
            "fileName":"synthetic.json", "totalLength": 10000,
            "offset":0,"chunkLength":1000,
            "content":"x"*1000, "hasMore":True,
        })


def call(name, args):
    return {"function": {"name":name, "arguments":args}}


class CatalogAndReceiptTests(unittest.IsolatedAsyncioTestCase):
    async def test_separate_archive_availability_is_visible_before_model_call(self):
        from device_monitor import TOOL_NAME
        monitor = SimpleNamespace(query=None)
        model=ScriptedAgent([
            {"content": "No archived evidence retrieved.", "tool_calls":[]},
            {"content": "History is still unverified.", "tool_calls":[]},
        ])
        try:
            reply=await model.answer("show historical meter readings last night",
                                     [],FakeMCP(),90,device_monitor=monitor)
        finally:
            await model.close()
        self.assertTrue(reply["available_read_sources"]["hub_device_monitor"]["configured"])
        self.assertTrue(reply["available_read_sources"]["hub_device_monitor"]["offered_to_model"])
        self.assertFalse(reply["available_read_sources"]["hub_device_monitor"]["connection_verified_by_catalog"])
        self.assertIn(TOOL_NAME,model.tool_names_seen[0])
        self.assertIn("IS configured",model.messages_seen[0][0]["content"])
        self.assertEqual(reply["source_review_kind"],"historical_measurement")

    async def test_nonconfigured_archive_is_not_claimed_or_advertised(self):
        model=ScriptedAgent([{"content":"No archives verified.","tool_calls":[]}])
        try:
            reply=await model.answer("Show current sensor status",[],FakeMCP(),90)
        finally:
            await model.close()
        self.assertFalse(reply["available_read_sources"]["hub_device_monitor"]["configured"])
        self.assertNotIn("homebrain_read_device_monitor",model.tool_names_seen[0])
        self.assertIn("NOT configured",model.messages_seen[0][0]["content"])

    async def test_file_chunk_coverage_recorded_without_rewriting_original(self):
        model=ScriptedAgent([
            {"content":"","tool_calls":[call("hub_read_file",{"fileName":"synthetic.json"})]},
            {"content":"Only 10% of the file was examined.","tool_calls":[]},
            {"content":"The file remains 90% unexamined.","tool_calls":[]},
        ])
        try:
            reply=await model.answer("Show which devices have archived history",[],FakeMCP(),90)
        finally:
            await model.close()
        self.assertTrue(reply["source_review_invoked"])
        self.assertEqual(reply["file_read_coverage"][0]["retrieved_percent"],10)
        receipt=json.loads(reply["tool_calls"][0]["response"])
        self.assertIn("client_file_cumulative_coverage",receipt)
        self.assertEqual(receipt["client_file_cumulative_coverage"]["unread_range_count"],1)
        self.assertIn("mcp_result",receipt)
        self.assertEqual(
            json.loads(receipt["mcp_result"]["content"][0]["text"])["content"],
            "x"*1000,
        )


class MonitorCheckRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_probe_only_fixed_read_only_status(self):
        import app as runtime
        previous = runtime.app.state._state.copy()
        class FakeMonitor:
            def __init__(self): self.calls=[]
            async def query(self, args):
                self.calls.append(args)
                return {"selected_devices": [
                    {"id":"10","has_power":True},
                    {"id":"20","has_power":False}
                ],"monitor_version":"fictional",
                 "monitor_observed_at_utc":"2026-10-18T11:00:00+00:00"}
        monitor=FakeMonitor()
        runtime.app.state.device_monitor=monitor
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=runtime.app),
                base_url="http://test") as client:
                blocked=await client.get("/api/sources/device-monitor/check")
                self.assertEqual(blocked.status_code,403)
                result=await client.get("/api/sources/device-monitor/check",
                   headers={"X-Homebrain-Request":"1"})
                self.assertEqual(result.status_code,200)
                data=result.json()
                self.assertTrue(data["reachable"])
                self.assertEqual(data["selected_power_capable_devices"],1)
                self.assertFalse(data["historical_sample_coverage_verified"])
                self.assertEqual(monitor.calls,[{"mode":"status"}])
                self.assertNotIn("token",result.text.lower())
        finally:
            runtime.app.state._state.clear()
            runtime.app.state._state.update(previous)


if __name__ == "__main__":
    unittest.main()

"""Alpha.52 fictional source-neutral saved-history discovery and reconciliation tests.

Demonstrates that tools and receipt summaries are available to the model,
not that any live Gemma first answer will choose correctly. No live hub.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent
from conversation import ConversationEvidence
from device_monitor import TOOL_NAME, TOOL_DEFINITION
from investigation_review import (
    MEASUREMENT_REVIEW_PROMPT, review_kind, is_read_only_review_tool,
)


def prior_monitor_result():
    return {
        "local_device_monitor": {
            "source": "Fixture saved numeric bins",
            "device_id": "987",
            "metric": "humidity",
            "historical_start_utc": "2026-10-20T12:00:00Z",
            "historical_end_utc": "2026-10-21T12:00:00Z",
            "summary": {
                "saved_bin_extrema": {
                    "highest": {
                        "value": 81, "bin_start_utc": "2026-10-20T22:20:00Z",
                        "unit": "%RH",
                    },
                    "lowest": {
                        "value": 49, "bin_start_utc": "2026-10-20T17:20:00Z",
                        "unit": "%RH",
                    },
                },
                "expected_bin_positions": 288,
                "populated_bin_positions": 287,
                "missing_bin_positions_total": 1,
                "sensor_freshness_known_from_source": False,
            },
            "samples": [{"bin_start_utc": "2026-10-20T22:20:00Z",
                         "saved_value": 81}] * 100,
        },
    }


class ModelLedSourceDiscoveryTests(unittest.TestCase):
    def test_general_question_requires_no_monitor_keyword_for_review(self):
        question = "Check Fixture sensor humidity readings for the last 24 hours"
        self.assertNotIn("monitor", question.lower())
        self.assertEqual(review_kind(question), "historical_measurement")
        self.assertIn("requested interval", MEASUREMENT_REVIEW_PROMPT)
        self.assertIn("previous server-held receipt", MEASUREMENT_REVIEW_PROMPT)
        self.assertIn("threshold", MEASUREMENT_REVIEW_PROMPT)
        self.assertTrue(is_read_only_review_tool(TOOL_NAME))
        self.assertIn("source", TOOL_DEFINITION["function"]["description"].lower())
        self.assertIn("did NOT name the monitor", TOOL_DEFINITION["function"]["description"])

    def test_prior_index_has_bounded_historical_extrema_when_samples_are_long(self):
        store = ConversationEvidence(per_receipt_chars=150, max_context_chars=7000)
        cid = str(uuid4())
        payload = json.dumps(prior_monitor_result())
        store.record(cid, "Earlier saved humidity samples", [{
            "name": TOOL_NAME,
            "result_kind": "local_monitor_read",
            "arguments": {"mode": "history", "metric": "humidity",
                          "device_id": "987", "range": "24h"},
            "success": True, "response": payload,
        }])
        context, _ = store.context(cid)
        index = json.loads(context[context.index("{"):context.rfind("}")+1])["source_index"]
        self.assertEqual(len(index), 1)
        meta = index[0]
        self.assertEqual(meta["historical_source_kind"], "separate_saved_device_monitor")
        self.assertEqual(meta["historical_metric"], "humidity")
        self.assertEqual(meta["historical_device_id"], "987")
        self.assertEqual(meta["saved_bin_highest"]["value"], 81)
        self.assertEqual(meta["saved_bin_highest"]["unit"], "%RH")
        self.assertEqual(meta["saved_bin_highest"]["bin_start_utc"],
                         "2026-10-20T22:20:00Z")
        self.assertEqual(meta["missing_bin_positions_total"], 1)
        self.assertFalse(meta["sensor_freshness_known_from_source"])
        self.assertIn("server-held", context.lower())
        self.assertNotIn("SECRET", context)

    def test_no_source_summary_invented_for_native_or_invalid_historian(self):
        from conversation import _source_shape
        self.assertEqual(_source_shape('{"local_device_monitor": null}'), {})
        self.assertEqual(_source_shape('{"other":"fixture"}'), {})
        native = _source_shape(json.dumps({
            "content": [{"type": "text", "text": json.dumps({
                "events": [{"date": "2026-10-21T08:00:00Z"}],
                "count": 1, "attributeFilter": "humidity",
            })}],
        }))
        self.assertEqual(native["events_returned"], 1)
        self.assertNotIn("saved_bin_highest", native)


class FakeHub:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [{"name": "hub_list_device_events", "description":
                 "Read returned native device events",
                 "inputSchema": {"type": "object"}}]

    async def call(self, name, args):
        self.calls.append((name, args))
        return {
            "content": [{"type": "text", "text": json.dumps({
                "device": "Fictional Sensor",
                "attributeFilter": "humidity", "count": 2,
                "sinceTimestamp": "2026-10-20T12:00:00Z",
                "events": [
                    {"name": "humidity", "value": "62",
                     "date": "2026-10-21T08:00:00Z"},
                    {"name": "humidity", "value": "51",
                     "date": "2026-10-21T10:00:00Z"},
                ],
            })}],
        }


class FakeMonitor:
    def __init__(self):
        self.calls = []

    async def query(self, args):
        self.calls.append(args)
        return prior_monitor_result()["local_device_monitor"]


def tc(name, args):
    return {"function": {"name": name, "arguments": args}}


class ScriptedAgent(Agent):
    def __init__(self, replies):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 10)
        self.replies = list(replies)
        self.inputs = []
        self.tools_seen = []

    async def round(self, messages, tools, remaining):
        self.inputs.append(list(messages))
        self.tools_seen.append([t["function"]["name"] for t in tools])
        return self.replies.pop(0)


class HistorySourceSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_may_select_monitor_without_source_name_after_review(self):
        hub, monitor = FakeHub(), FakeMonitor()
        agent = ScriptedAgent([
            {"content": "", "tool_calls": [
                tc("hub_list_device_events", {
                    "attribute": "humidity", "deviceId": "987",
                    "hoursBack": 24, "limit": 100})]},
            {"content": "The returned 62% is the whole-day peak.", "tool_calls": []},
            {"content": "", "tool_calls": [
                tc(TOOL_NAME, {"mode": "history", "device_id": "987",
                               "metric": "humidity", "range": "24h"})]},
            {"content": ("Native returned events only show a later excerpt; "
                         "saved bins include an earlier 81% reading. "
                         "Whether every bin was a fresh report is unknown."),
             "tool_calls": []},
        ])
        try:
            out = await agent.answer(
                "Check humidity readings of Fixture sensor over last 24 hours",
                [], hub, 90, device_monitor=monitor,
            )
        finally:
            await agent.close()
        self.assertTrue(out["success"])
        self.assertTrue(out["source_review_invoked"])
        self.assertEqual(out["rounds"], 4)
        self.assertEqual([x["name"] for x in out["tool_calls"]],
                         ["hub_list_device_events", TOOL_NAME])
        self.assertEqual(len(hub.calls), 1)
        self.assertEqual(monitor.calls, [{
            "mode": "history", "device_id": "987",
            "metric": "humidity", "range": "24h",
        }])
        self.assertIn(TOOL_NAME, agent.tools_seen[0])
        self.assertIn("SOURCE-NEUTRAL", agent.inputs[0][0]["content"])
        self.assertIn("previous server-held receipt", agent.inputs[2][-1]["content"])
        self.assertIn("81% reading", out["answer"])

    async def test_no_forced_read_and_no_claim_of_source_reconciliation(self):
        hub, monitor = FakeHub(), FakeMonitor()
        agent = ScriptedAgent([
            {"content": "I cannot determine a full-day maximum from two events.",
             "tool_calls": []},
            {"content": ("The returned native window alone cannot establish "
                         "the preceding evening's humidity."),
             "tool_calls": []},
        ])
        try:
            out = await agent.answer(
                "Check Fictional Sensor humidity for last 24 hours", [],
                hub, 90, device_monitor=monitor,
            )
        finally:
            await agent.close()
        self.assertEqual(out["rounds"], 2)
        self.assertEqual(hub.calls, [])
        self.assertEqual(monitor.calls, [])
        self.assertIn("preceding evening", out["answer"])

    async def test_no_monitor_tool_when_not_configured(self):
        hub = FakeHub()
        agent = ScriptedAgent([
            {"content": "The native source does not establish the full day.",
             "tool_calls": []},
            {"content": "No other source was checked. The gap is unknown.",
             "tool_calls": []},
        ])
        try:
            out = await agent.answer(
                "Check Fictional Sensor readings over last 24 hours", [],
                hub, 90,
            )
        finally:
            await agent.close()
        self.assertFalse(out["available_read_sources"]["hub_device_monitor"]["configured"])
        self.assertNotIn(TOOL_NAME, agent.tools_seen[0])
        self.assertEqual(hub.calls, [])


if __name__ == "__main__":
    unittest.main()

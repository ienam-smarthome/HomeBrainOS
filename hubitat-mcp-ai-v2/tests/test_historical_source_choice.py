"""Alpha.52 historical source-selection semantics.

Offline scripted model and fictional timestamps only. These contracts confirm
that a model CAN choose a second relevant read, that the source instructions
are available without naming a recorder in the user question, and that the
client does not force an archive read or modify an answer. They do NOT
establish any live Gemma first-answer improvement.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent, _SKILL
from investigation_review import (
    MEASUREMENT_REVIEW_PROMPT, review_kind, is_read_only_review_tool,
)


def mcp_response(rows):
    return {"content": [{"type": "text", "text": json.dumps({
        "events": rows, "count": len(rows), "attributeFilter": "temperature",
        "sinceTimestamp": "2026-10-18T00:00:00Z",
    })}]}


class SyntheticNative:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [{"name": "hub_list_device_events", "description": "Read native events",
                 "inputSchema": {"type": "object", "properties": {
                     "deviceId": {"type": "string"},
                     "hoursBack": {"type": "integer"},
                     "attribute": {"type": "string"},
                 }}}]

    async def call(self, name, args):
        self.calls.append((name, args))
        return mcp_response([
            {"name": "temperature", "value": "18",
             "date": "2026-10-18T08:00:00Z"},
            {"name": "temperature", "value": "19",
             "date": "2026-10-18T11:00:00Z"},
        ])


class FictionalArchive:
    def __init__(self):
        self.calls = []

    async def query(self, args):
        self.calls.append(dict(args))
        return {
            "source": "Fictional separate saved-bin archive",
            "metric": "temperature", "unit": "°C",
            "window_start_utc": "2026-10-18T00:00:00Z",
            "window_end_exclusive_utc": "2026-10-19T00:00:00Z",
            "summary": {
                "saved_bin_extrema": {
                    "highest": {
                        "value": 25,
                        "bin_start_utc": "2026-10-18T03:15:00Z",
                    },
                },
                "sensor_freshness_known_from_source": False,
                "populated_bin_positions": 240,
                "expected_bin_positions": 288,
            },
        }


def call(name, args):
    return {"function": {"name": name, "arguments": args}}


class ScriptedAgent(Agent):
    def __init__(self, replies):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 60)
        self.replies = list(replies)
        self.seen = []
        self.tool_catalogs = []

    async def answer(self, *args, **kwargs):
        # These legacy roundtrip fixtures intentionally test the pre-audit
        # source-review contract; dedicated tests exercise the new default.
        kwargs.setdefault("enable_final_claim_audit", False)
        return await super().answer(*args, **kwargs)

    async def round(self, messages, tools, remaining):
        self.seen.append([dict(msg) for msg in messages])
        self.tool_catalogs.append([tool["function"]["name"] for tool in tools])
        return self.replies.pop(0)


class HistoricalChoiceTests(unittest.TestCase):
    def test_prompts_apply_to_any_metric_without_device_name(self):
        self.assertIn("whether or not the user named that source", _SKILL)
        self.assertIn("returned timestamps/window", _SKILL)
        self.assertIn("automatically authoritative just because its name", _SKILL)
        self.assertIn("whether the user named a historian", MEASUREMENT_REVIEW_PROMPT)
        self.assertIn("returned native event interval", MEASUREMENT_REVIEW_PROMPT)
        self.assertIn("prior source receipts", MEASUREMENT_REVIEW_PROMPT)
        for private_target in ("Bathroom Meter", "7851", "Shower",
                               "Bedroom 3 PC", "7104"):
            self.assertNotIn(private_target, MEASUREMENT_REVIEW_PROMPT)
        self.assertTrue(is_read_only_review_tool("homebrain_read_device_monitor"))
        self.assertTrue(is_read_only_review_tool("hub_list_device_events"))
        self.assertFalse(is_read_only_review_tool("hub_set_rule"))
        for metric in ("humidity", "temperature", "power", "level"):
            self.assertEqual(
                review_kind(f"Check {metric} levels for fictional sensor in last 24 hours"),
                "historical_measurement",
            )


class ModelDecidesHistorySourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_can_choose_archive_after_incomplete_native_interval(self):
        native = SyntheticNative()
        archive = FictionalArchive()
        agent = ScriptedAgent([
            {"content": "", "tool_calls": [
                call("hub_list_device_events",
                     {"attribute": "temperature", "deviceId": "901", "hoursBack": 24})
            ]},
            {"content": "The 24-hour peak was 19°C.", "tool_calls": []},
            {"content": "", "tool_calls": [
                call("homebrain_read_device_monitor",
                     {"mode": "history", "metric": "temperature",
                      "device_id": "901", "range": "24h"})
            ]},
            {"content": (
                "Native events returned only morning samples; a separate "
                "saved-bin source returned a 25°C high at 03:15. Sensor-bin "
                "freshness remains unverified, and the actual physical peak is unknown."
            ), "tool_calls": []},
        ])
        question = "Check the temperature history of fictional sensor in the last 24 hours."
        try:
            result = await agent.answer(question, [], native, 120,
                                        device_monitor=archive)
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(result["source_review_kind"], "historical_measurement")
        self.assertEqual(result["rounds"], 4)
        self.assertEqual(len(native.calls), 1)
        self.assertEqual(len(archive.calls), 1)
        self.assertEqual(result["tool_calls"][0]["name"], "hub_list_device_events")
        self.assertEqual(result["tool_calls"][1]["name"], "homebrain_read_device_monitor")
        self.assertIn("25°C", result["answer"])
        self.assertIn("freshness remains unverified", result["answer"])
        self.assertIn("source coverage", agent.seen[0][0]["content"])
        self.assertIn("whether the user named a historian",
                      agent.seen[2][-1]["content"])
        self.assertIn("homebrain_read_device_monitor", agent.tool_catalogs[0])
        self.assertIn("homebrain_read_device_monitor", agent.tool_catalogs[2])

    async def test_checkpoint_does_not_force_archive_or_rewrite_native_answer(self):
        native = SyntheticNative()
        archive = FictionalArchive()
        agent = ScriptedAgent([
            {"content": "", "tool_calls": [
                call("hub_list_device_events",
                     {"attribute": "temperature", "deviceId": "901", "hoursBack": 24})
            ]},
            {"content": "Native events returned 18°C and 19°C.", "tool_calls": []},
            {"content": "Only returned native events have been checked; the "
                        "earlier interval remains unverified.", "tool_calls": []},
        ])
        try:
            result = await agent.answer(
                "Show the temperature history for synthetic sensor last 24 hours.",
                [], native, 90, device_monitor=archive,
            )
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"], 3)
        self.assertEqual(len(native.calls), 1)
        self.assertEqual(archive.calls, [])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertIn("earlier interval remains unverified", result["answer"])

    async def test_nonhistorical_simple_query_keeps_single_round(self):
        native = SyntheticNative()
        archive = FictionalArchive()
        agent = ScriptedAgent([
            {"content": "The requested value is unknown.", "tool_calls": []},
        ])
        try:
            result = await agent.answer("List the fictional device names", [],
                                        native, 60, device_monitor=archive)
        finally:
            await agent.close()
        self.assertFalse(result["source_review_invoked"])
        self.assertEqual(result["rounds"], 1)
        self.assertEqual(native.calls, [])
        self.assertEqual(archive.calls, [])


if __name__ == "__main__":
    unittest.main()

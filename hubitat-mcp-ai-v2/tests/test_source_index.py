"""Synthetic alpha.9 regression: indexed sources are not lost behind newer excerpts.

No real household IDs/history, model credentials or live Hubitat access.
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
from mcp import MCPError


def source(device_id, dates, *, size=0, count=None):
    """Two-layer MCP text block resembling native device-event source shape."""
    body = {
        "source": "device", "device": "Fixture " + str(device_id),
        "deviceId": str(device_id), "hoursBack": 24,
        "events": [{"name": "fixtureState", "value": "idle",
                    "date": timestamp, "description": "fixture" + "x" * size}
                   for timestamp in dates],
        "count": len(dates) if count is None else count,
    }
    return json.dumps({"content": [{"type": "text", "text": json.dumps(body)}]})


def read_receipt(device, response, *, success=True):
    return {
        "name": "hub_read_devices", "arguments": {
            "tool": "hub_list_device_events",
            "args": {"deviceId": str(device), "hoursBack": 24}
        },
        "response": response, "success": success, "result_kind": "tool_result",
    }


class SourceIndexTests(unittest.TestCase):
    def _scenario(self):
        cache = ConversationEvidence(max_context_chars=11000, per_receipt_chars=1600)
        sid = str(uuid4())
        dates = ["2026-11-06T08:30:15+0000", "2026-11-06T09:23:33+0000"]
        receipts = [
            {"name": "hub_read_devices", "arguments": {"args": {}},
             "success": False, "result_kind": "contract_error",
             "response": '{"error":"fixture contract error"}'},
            read_receipt("main", source("main", dates, size=9000)),
        ]
        for number in range(1, 7):
            receipts.append(read_receipt(
                f"zone-{number}",
                source(f"zone-{number}",
                       [f"2026-11-06T15:00:{number:02d}+0000"], size=8000)
            ))
        cache.record(sid, "Compare earlier device history", receipts)
        return cache, sid, dates

    def test_index_shows_old_source_even_with_bounded_excerpts(self):
        cache, sid, dates = self._scenario()
        context, excerpt_count = cache.context(sid)
        self.assertLess(len(context), 12500)
        self.assertGreater(excerpt_count, 0)
        structured = json.loads(context[context.index("{"):context.rfind("}") + 1])
        self.assertEqual(structured["source_index_total"], 8)
        self.assertEqual(structured["source_index_omitted"], 0)
        index = structured["source_index"]
        self.assertEqual(len(index), 8)
        first = next(x for x in index if x.get("device") == "Fixture main")
        self.assertTrue(first["archive_available"])
        self.assertEqual(first["earliest_returned_event"], dates[0])
        self.assertEqual(first["latest_returned_event"], dates[1])
        self.assertEqual(first["event_window_complete"], "not established by event timestamps")
        self.assertEqual(first["arguments"]["args"]["deviceId"], "main")
        self.assertEqual(len(structured["source_excerpts"]), excerpt_count)
        self.assertTrue(any(x["excerpt_truncated"] for x in structured["source_excerpts"]))
        self.assertIn("A source missing from excerpts", context)

    def test_original_source_can_be_read_in_chunks_with_timestamps(self):
        cache, sid, dates = self._scenario()
        body, _ = cache.context(sid)
        structured = json.loads(body[body.index("{"):body.rfind("}") + 1])
        source_id = next(x["receipt_id"] for x in structured["source_index"]
                         if x.get("device") == "Fixture main")
        chunks = []
        offset = 0
        for _ in range(10):
            part = cache.read_receipt(sid, source_id, offset=offset, max_chars=16000)
            chunks.append(part["chunk"])
            if part["next_offset"] is None:
                break
            offset = part["next_offset"]
        full = "".join(chunks)
        original = source("main", dates, size=9000)
        self.assertEqual(json.loads(full), json.loads(original))
        self.assertIn(dates[0], full)
        self.assertEqual(part["origin"], "server-held historical MCP receipt, NOT a fresh hub read")
        self.assertTrue(part["archive_complete"])

    def test_session_cross_access_reset_and_invalid_arguments_are_rejected(self):
        cache, sid, _ = self._scenario()
        context, _ = cache.context(sid)
        structured = json.loads(context[context.index("{"):context.rfind("}") + 1])
        source_id = structured["source_index"][1]["receipt_id"]
        with self.assertRaisesRegex(MCPError, "expired or"):
            cache.read_receipt(str(uuid4()), source_id)
        with self.assertRaisesRegex(MCPError, "out of range"):
            cache.read_receipt(sid, source_id, offset=-1)
        with self.assertRaisesRegex(MCPError, "out of range"):
            cache.read_receipt(sid, source_id, max_chars=20000)
        with self.assertRaisesRegex(MCPError, "Invalid"):
            cache.read_receipt(sid, "invented")
        cache.clear(sid)
        with self.assertRaisesRegex(MCPError, "expired or"):
            cache.read_receipt(sid, source_id)

    def test_eviction_retains_index_and_explicitly_marks_missing_archive(self):
        cache = ConversationEvidence(max_archive_chars=2000, max_single_archive_chars=2000)
        sid = str(uuid4())
        cache.record(sid, "First", [
            read_receipt("first", source("first", ["2026-11-06T10:00:00+0000"], size=1300)),
            read_receipt("second", source("second", ["2026-11-06T11:00:00+0000"], size=1300)),
        ])
        body, _ = cache.context(sid)
        structured = json.loads(body[body.index("{"):body.rfind("}") + 1])
        items = structured["source_index"]
        self.assertEqual(len(items), 2)
        self.assertFalse(items[0]["archive_available"])
        self.assertTrue(items[0]["archive_evicted"])
        self.assertTrue(items[1]["archive_available"])
        with self.assertRaisesRegex(MCPError, "evicted"):
            cache.read_receipt(sid, items[0]["receipt_id"])

    def test_model_can_select_local_receipt_tool_without_mcp_call(self):
        class FakeHub:
            calls = 0
            async def list_tools(self, refresh=False):
                return []
            async def call(self, name, args):
                self.calls += 1
                raise AssertionError("local prior receipt must not go to the Hub")

        class FakeAgent(Agent):
            def __init__(self, source_id):
                super().__init__("http://127.0.0.1:11434", "fixture-model", "", 20)
                self.rid = source_id
                self.rounds_seen = 0
            async def round(self, messages, tools, remaining):
                self.rounds_seen += 1
                self.tool_names = [t["function"]["name"] for t in tools]
                if self.rounds_seen == 1:
                    return {"content": "Retrieve earlier source", "tool_calls": [{
                        "function": {"name": "homebrain_read_prior_evidence",
                                     "arguments": {"receipt_id": self.rid, "max_chars": 16000}}
                    }]}
                self.last_context = list(messages)
                return {"content": "Source history retrieved; no fresh hub calls.",
                        "tool_calls": []}

        async def run():
            cache = ConversationEvidence()
            sid = str(uuid4())
            raw = source("main", ["2026-11-06T09:17:33+0000"], size=7000)
            cache.record(sid, "Earlier investigation", [read_receipt("main", raw)])
            prior, count = cache.context(sid)
            indexed = json.loads(prior[prior.index("{"):prior.rfind("}") + 1])
            rid = indexed["source_index"][0]["receipt_id"]
            agent = FakeAgent(rid)
            hub = FakeHub()
            try:
                response = await agent.answer(
                    "Re-check the original source", [], hub, 60,
                    prior_evidence=prior, prior_receipts=count,
                    prior_reader=lambda receipt_id, offset, max_chars:
                        cache.read_receipt(sid, receipt_id, offset=offset, max_chars=max_chars),
                )
                self.assertTrue(response["success"])
                self.assertEqual(hub.calls, 0)
                self.assertEqual(len(response["tool_calls"]), 1)
                self.assertEqual(response["tool_calls"][0]["result_kind"], "prior_evidence_read")
                self.assertFalse(response["tool_calls"][0]["operation_executed"])
                self.assertIn("homebrain_read_prior_evidence", agent.tool_names)
                self.assertIn("2026-11-06T09:17:33", agent.last_context[-1]["content"]
                              if agent.last_context[-1]["role"] == "tool"
                              else json.dumps(agent.last_context))
                cache.record(sid, "Second answer", response["tool_calls"])
                self.assertEqual(cache.source_count(sid), 1)
            finally:
                await agent.close()
        asyncio.run(run())

    def test_not_enabled_without_prior_evidence_and_no_hidden_write(self):
        class FakeHub:
            async def list_tools(self, refresh=False):
                return []
        class FakeAgent(Agent):
            async def round(self, messages, tools, remaining):
                self.tool_names = [t["function"]["name"] for t in tools]
                return {"content": "No historical source", "tool_calls": []}
        async def run():
            agent = FakeAgent("http://127.0.0.1:11434", "fixture-model", "", 20)
            try:
                await agent.answer("new conversation", [], FakeHub(), 60)
                self.assertNotIn("homebrain_read_prior_evidence", agent.tool_names)
            finally:
                await agent.close()
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

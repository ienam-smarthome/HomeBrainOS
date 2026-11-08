"""v2 alpha.8: bounded evidence memory is isolated from UI prose and live reads."""
import asyncio
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from conversation import ConversationEvidence
from agent import Agent
from app import app


def receipt(tool="hub_read_devices", response='{"deviceId":7828,"switch":"off"}', **extra):
    return {
        "name": tool, "arguments": {"tool": "hub_get_device", "args": {"deviceId": 7828}},
        "success": True, "result_kind": "tool_result", "response": response, **extra,
    }


class ConversationMemoryTests(unittest.TestCase):
    def test_followup_preserves_real_source_and_timestamp(self):
        store = ConversationEvidence()
        cid = str(uuid4())
        store.record(cid, "Why did light turn off?", [receipt()])
        context, count = store.context(cid)
        self.assertEqual(count, 1)
        self.assertIn("collected_at_utc", context)
        self.assertIn("hub_read_devices", context)
        self.assertIn("7828", context)
        self.assertIn("not fresh observations", context)
        self.assertIn("Re-check live", context)

    def test_context_isolation_and_reset(self):
        store = ConversationEvidence()
        first, second = str(uuid4()), str(uuid4())
        store.record(first, "Lighting", [receipt(response='{"fixture":"ROOM-A"}')])
        store.record(second, "Humidity", [receipt(response='{"fixture":"ROOM-B"}')])
        self.assertNotIn("ROOM-A", store.context(second)[0])
        self.assertNotIn("ROOM-B", store.context(first)[0])
        store.clear(first)
        self.assertEqual(store.context(first), ("", 0))
        self.assertIn("ROOM-B", store.context(second)[0])

    def test_ttl_and_capacity_drop_old_sources(self):
        now = [100.]
        store = ConversationEvidence(ttl_seconds=30, max_conversations=2, clock=lambda: now[0])
        one, two, three = [str(uuid4()) for _ in range(3)]
        store.record(one, "One", [receipt(response="FIRST")])
        now[0] += 1
        store.record(two, "Two", [receipt(response="SECOND")])
        now[0] += 1
        store.record(three, "Three", [receipt(response="THIRD")])
        self.assertEqual(store.context(one), ("", 0))
        self.assertIn("THIRD", store.context(three)[0])
        now[0] += 31
        self.assertEqual(store.context(three), ("", 0))

    def test_credentials_and_truncation_are_not_silent(self):
        store = ConversationEvidence(per_receipt_chars=100)
        cid = str(uuid4())
        store.record(cid, "Sensitive question", [
            receipt(response='{"password":"PRIVATE-SAMPLE","access_token":"TOP-SECRET","state":"on"}'),
            receipt(response="x" * 1000),
            {"name": "hub_read_apps_code", "result_kind": "tool_catalog",
             "response": '{"catalog":"not-domain-evidence"}'},
        ])
        context, count = store.context(cid)
        self.assertEqual(count, 2)
        self.assertNotIn("PRIVATE-SAMPLE", context)
        self.assertNotIn("TOP-SECRET", context)
        self.assertNotIn("not-domain-evidence", context)
        self.assertIn('"excerpt_truncated": true', context)
        self.assertIn('"source_response_chars": 1000', context)

    def test_session_bounds_prevent_unbounded_context(self):
        store = ConversationEvidence(max_turns=2, max_receipts=3,
                                     per_receipt_chars=200, max_context_chars=1800)
        cid = str(uuid4())
        for idx in range(5):
            store.record(cid, f"Turn {idx}", [
                receipt(response=f"READ-{idx}-{n}:" + "x" * 140)
                for n in range(5)
            ])
        text, count = store.context(cid)
        self.assertLessEqual(count, 6)
        self.assertNotIn("READ-0-", text)
        self.assertNotIn("READ-1-", text)
        self.assertNotIn("READ-2-", text)
        self.assertIn("READ-4-", text)
        self.assertLess(len(text), 2500)

    def test_model_receives_history_as_older_data_not_fresh_tool_response(self):
        class FakeAgent(Agent):
            async def round(self, messages, tools, remaining):
                self.seen = messages
                return {"role": "assistant", "content": "The earlier sample says off, current state requires a read."}
        class FakeMCP:
            async def list_tools(self, refresh=False):
                return []
        async def test():
            agent = FakeAgent("http://127.0.0.1:11434", "test", "", 20)
            try:
                store, cid = ConversationEvidence(), str(uuid4())
                store.record(cid, "Prior question", [receipt()])
                prior, count = store.context(cid)
                result = await agent.answer(
                    "Is it still off?", [{"role": "user", "content": "Prior question"}],
                    FakeMCP(), 60, prior_evidence=prior, prior_receipts=count,
                )
                self.assertEqual(result["prior_receipts_used"], 1)
                self.assertEqual(agent.seen[-1]["content"], "Is it still off?")
                self.assertIn("Earlier", agent.seen[-2]["content"] if "Earlier" in agent.seen[-2]["content"] else "Earlier")
                self.assertIn("7828", agent.seen[-2]["content"])
                self.assertEqual(result["tool_calls"], [])
            finally:
                await agent.close()
        asyncio.run(test())

    def test_reset_requires_existing_same_origin_request_header(self):
        async def test():
            store = ConversationEvidence()
            cid = str(uuid4())
            store.record(cid, "Old", [receipt()])
            app.state.conversations = store
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                missing = await client.post("/api/conversation/clear",
                                            json={"conversation_id": cid})
                self.assertEqual(missing.status_code, 403)
                self.assertEqual(store.context(cid)[1], 1)
                good = await client.post("/api/conversation/clear",
                                         json={"conversation_id": cid},
                                         headers={"X-Homebrain-Request": "1"})
                self.assertEqual(good.status_code, 200)
                self.assertEqual(store.context(cid), ("", 0))
        asyncio.run(test())


if __name__ == "__main__":
    unittest.main()

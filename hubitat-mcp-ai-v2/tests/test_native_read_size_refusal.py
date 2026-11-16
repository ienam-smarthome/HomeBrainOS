"""Fictional V2 source refusal tests; no live hub, writes or LLM calls."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from native_read_size_refusal import native_read_size_refusal


OVERSIZE = {
    "response_too_large": True, "truncated": True,
    "estimatedBytes": 120519, "sizeLimitBytes": 120000,
    "tool": "hub_list_devices",
    "suggestion": "Narrow the read and retry if useful",
}


def wrapped(payload):
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


class NativeReadLimitTests(unittest.TestCase):
    def test_upstream_refusal_is_not_native_data_success(self):
        original = wrapped(OVERSIZE)
        before = json.dumps(original, sort_keys=True)
        result = native_read_size_refusal(original, "hub_list_devices")
        self.assertEqual(result["status"], "native_response_too_large")
        self.assertFalse(result["usable_native_rows_returned"])
        self.assertEqual(result["estimatedBytes"], 120519)
        self.assertEqual(before, json.dumps(original, sort_keys=True))

    def test_payload_contract_and_tool_scope(self):
        for result, name in (
            (wrapped(OVERSIZE), "hub_get_device"),
            (wrapped(dict(OVERSIZE, truncated=False)), "hub_list_devices"),
            (wrapped({"devices": [{"label": "response_too_large"}]}),
             "hub_list_devices"),
            (wrapped({"response_too_large": "true", "truncated": True}),
             "hub_list_devices"),
            ({"content": [{"type": "text", "text": "{not json}"}]},
             "hub_list_devices"),
            ({"content": [{"type": "text", "text": json.dumps(OVERSIZE)},
                          {"type": "text", "text": "extra"}]},
             "hub_list_devices"),
            ({"isError": True, **wrapped(OVERSIZE)}, "hub_list_devices"),
        ):
            with self.subTest(result=result, name=name):
                self.assertIsNone(native_read_size_refusal(result, name))

    def test_direct_native_refusal(self):
        self.assertEqual(
            native_read_size_refusal(OVERSIZE, "hub_list_devices")["status"],
            "native_response_too_large",
        )


class FakeMCP:
    def __init__(self, refusal=True):
        self.calls = []
        self.refusal = refusal

    async def list_tools(self, refresh=False):
        return [{"name": "hub_list_devices", "description": "Read only device list",
                 "inputSchema": {"type": "object",
                                 "properties": {"format": {"type": "string"}}}}]

    async def call(self, name, args):
        self.calls.append((name, args))
        assert name == "hub_list_devices"
        if self.refusal:
            return wrapped(OVERSIZE)
        return wrapped({"devices": [{"id": "F-1", "label": "Fixture Device"}],
                        "count": 1, "total": 1})


class ScriptedAgent(Agent):
    def __init__(self, *messages):
        super().__init__("http://127.0.0.1:11434", "fixture", "", 20)
        self.messages = list(messages)
        self.snapshots = []

    async def round(self, messages, tools, remaining):
        self.snapshots.append(json.loads(json.dumps(messages)))
        if not self.messages:
            raise AssertionError("Unexpected extra model round")
        return self.messages.pop(0)


class ReadLimitIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_oversized_read_is_failed_evidence_without_retry(self):
        hub = FakeMCP()
        agent = ScriptedAgent(
            {"content": "", "tool_calls": [{
                "function": {"name": "hub_list_devices",
                             "arguments": {"format": "detailed"}},
            }]},
            {"content": "The attempted inventory was too large; no usable device list returned."},
        )
        try:
            result = await agent.answer(
                "Explain why the fixture output changed. Do not change anything.",
                [], hub, 90, enable_source_review=False,
                enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        self.assertEqual(len(hub.calls), 1)
        self.assertEqual(result["rounds"], 2)
        self.assertFalse(result["tool_calls"][0]["success"])
        self.assertEqual(result["tool_calls"][0]["source_limit"]["status"],
                         "native_response_too_large")
        self.assertFalse(result["current_read_source_progress"][
            "has_successful_current_source"
        ])
        model_view = agent.snapshots[1][-1]["content"]
        self.assertIn("client_source_limit", model_view)
        self.assertIn("response_too_large", model_view)
        self.assertIn("no usable device list returned", result["answer"])

    async def test_normal_returned_inventory_remains_successful(self):
        hub = FakeMCP(refusal=False)
        agent = ScriptedAgent(
            {"content": "", "tool_calls": [{
                "function": {"name": "hub_list_devices",
                             "arguments": {"format": "summary"}},
            }]},
            {"content": "The original device list returned one fixture."},
        )
        try:
            result = await agent.answer(
                "Why did the fixture change? Do not change anything.",
                [], hub, 90, enable_source_review=False,
                enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        self.assertTrue(result["tool_calls"][0]["success"])
        self.assertNotIn("source_limit", result["tool_calls"][0])
        self.assertTrue(result["current_read_source_progress"][
            "has_successful_current_source"
        ])


if __name__ == "__main__":
    unittest.main()

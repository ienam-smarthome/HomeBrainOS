"""Fictional deadline finalization tests: no real Hubitat or cloud access."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [{
            "name": "hub_get_device",
            "description": "Synthetic read-only device source",
            "inputSchema": {
                "type": "object",
                "properties": {"deviceId": {"type": "integer"}},
                "required": ["deviceId"],
            },
        }]

    async def call(self, name, args):
        self.calls.append((name, args))
        return {"content": [{"type": "text", "text": (
            '{"timestamp":"2030-01-01T12:00:00Z","state":"idle",'
            '"prior_state":"unknown","cause":"unknown"}'
        )}]}


class ClockedAgent(Agent):
    def __init__(self, clock, second_tool=False):
        super().__init__("http://127.0.0.1:11434", "fixture", "", 20)
        self.clock = clock
        self.rounds_seen = 0
        self.second_tools = None
        self.second_tool = second_tool

    async def round(self, messages, tools, remaining):
        self.rounds_seen += 1
        if self.rounds_seen == 1:
            self.clock[0] = 95.0  # 25 seconds remain of the synthetic 120 s budget
            return {"tool_calls": [{"function": {
                "name": "hub_get_device", "arguments": {"deviceId": 101}
            }}]}
        self.second_tools = tools
        if self.second_tool:
            # The model must NEVER gain an executable tool merely by asking.
            return {"tool_calls": [{"function": {
                "name": "hub_reboot", "arguments": {"confirm": True}
            }}]}
        return {"content": (
            "Fictional valve reports idle at 12:00 UTC. "
            "No prior heating state or initiating cause was observed."
        )}


class DeadlineFinalizeTests(unittest.TestCase):
    def test_causal_sources_finalize_without_extra_reads_or_model_rounds(self):
        async def run():
            clock = [0.0]
            mcp = FakeMCP()
            agent = ClockedAgent(clock)
            try:
                with patch("agent.time.monotonic", side_effect=lambda: clock[0]):
                    result = await agent.answer(
                        "Investigate why the fictional valve stopped heating. Do not change anything.",
                        [], mcp, 120,
                    )
                self.assertTrue(result["success"])
                self.assertEqual(result["rounds"], 2)
                self.assertEqual(result["final_claim_audit_status"], "deadline_finalized")
                self.assertTrue(result["deadline_finalization_invoked"])
                self.assertEqual(agent.second_tools, [])
                self.assertEqual(mcp.calls, [("hub_get_device", {"deviceId": 101})])
                self.assertEqual(len(result["tool_calls"]), 1)
                self.assertTrue(result["tool_calls"][0]["success"])
                self.assertIn("unknown", result["answer"])
            finally:
                await agent.close()
        asyncio.run(run())

    def test_unsolicited_tool_at_finalization_is_never_dispatched(self):
        async def run():
            clock = [0.0]
            mcp = FakeMCP()
            agent = ClockedAgent(clock, second_tool=True)
            try:
                with patch("agent.time.monotonic", side_effect=lambda: clock[0]):
                    result = await agent.answer(
                        "Investigate why a fictional valve changed. Do not change anything.",
                        [], mcp, 120,
                    )
                self.assertFalse(result["success"])
                self.assertEqual(result["error"], "deadline")
                self.assertEqual(result["deadline_finalization_status"],
                                 "unoffered_tool_rejected")
                self.assertTrue(result["deadline_finalization_invoked"])
                self.assertEqual(agent.second_tools, [])
                self.assertEqual(mcp.calls, [("hub_get_device", {"deviceId": 101})])
                self.assertEqual(len(result["tool_calls"]), 1)
            finally:
                await agent.close()
        asyncio.run(run())

    def test_noncausal_question_does_not_force_early_finalization(self):
        async def run():
            clock = [0.0]
            mcp = FakeMCP()
            agent = ClockedAgent(clock)
            try:
                with patch("agent.time.monotonic", side_effect=lambda: clock[0]):
                    result = await agent.answer(
                        "Show the reported state of fictional device 101",
                        [], mcp, 120, enable_source_review=False,
                    )
                self.assertTrue(result["success"])
                self.assertFalse(result["deadline_finalization_invoked"])
                self.assertNotEqual(agent.second_tools, [])
                self.assertEqual(mcp.calls, [("hub_get_device", {"deviceId": 101})])
            finally:
                await agent.close()
        asyncio.run(run())

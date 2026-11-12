"""Alpha.58: observe model reasoning stages without modifying a decision.

All devices and answers are fictional. These scripted runs prove only that
the private diagnostics can show where an overclaim was introduced, not that
any model in production reasons correctly or that a review caused an error.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent


class FictionalMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [{"name": "hub_list_device_events",
                 "inputSchema": {"type": "object", "properties": {
                     "deviceId": {"type": "string"}}}}]

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        return {"content": [{"type": "text", "text":
                             '{"events":[{"name":"switch","value":"off"}],'
                             '"count":1,"attributeFilter":null}'}]}


class ScriptedAgent(Agent):
    def __init__(self, replies):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 20)
        self.replies = list(replies)
        self.offered = []

    async def round(self, messages, tools, remaining):
        self.offered.append([tool["function"]["name"] for tool in tools])
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def answer(value):
    return {"content": value, "tool_calls": []}


def call(name, arguments):
    return {"content": "", "tool_calls": [{
        "function": {"name": name, "arguments": arguments}}]}


class StageTraceTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_evidence_can_show_an_audit_introducing_false_certainty(self):
        # This is an intentionally WRONG final scripted answer. Diagnostics must
        # expose this regression rather than labeling completed audit as correct.
        model = ScriptedAgent([
            answer("The synthetic bridge reported OFF; initiator unknown."),
            answer("No command issuer has been verified by these records."),
            answer("The synthetic event was definitely externally initiated."),
        ])
        mcp = FictionalMCP()
        try:
            result = await model.answer(
                "Why did this fictional light turn off? Read only.", [], mcp, 60)
        finally:
            await model.close()
        self.assertTrue(result["final_claim_audit_invoked"])
        self.assertEqual(result["final_claim_audit_status"], "completed")
        self.assertEqual(result["rounds"], 3)
        self.assertEqual([row["stage"] for row in result["answer_stage_trace"]], [
            "pre_source_review", "pre_final_audit", "post_final_audit"])
        self.assertEqual([row["tool_receipts_seen"] for row in
                          result["answer_stage_trace"]], [0, 0, 0])
        self.assertIn("initiator unknown", result["answer_stage_trace"][0]["answer"])
        self.assertIn("externally initiated",
                      result["answer_stage_trace"][-1]["answer"])
        self.assertEqual(result["answer"],
                         result["answer_stage_trace"][-1]["answer"])
        self.assertEqual(mcp.calls, [])

    async def test_review_can_add_an_independently_chosen_read(self):
        model = ScriptedAgent([
            answer("Fictional bridge reported OFF; no origin evidence yet."),
            call("hub_list_device_events", {"deviceId": "SYN-9"}),
            answer("One switch state returned. Command issuer remains unknown."),
            answer("One switch state returned; cause cannot be inferred."),
        ])
        mcp = FictionalMCP()
        try:
            result = await model.answer("Why did the fictional lamp turn off?",
                                        [], mcp, 90)
        finally:
            await model.close()
        rows = result["answer_stage_trace"]
        self.assertEqual([row["tool_receipts_seen"] for row in rows], [0, 1, 1])
        self.assertEqual([row["successful_tool_receipts_seen"] for row in rows],
                         [0, 1, 1])
        self.assertEqual([row["after_model_round"] for row in rows], [1, 3, 4])
        self.assertEqual(mcp.calls, [("hub_list_device_events",
                                     {"deviceId": "SYN-9"})])
        self.assertEqual(model.offered[-1], [],
                         "Final review remains tool-free")
        self.assertEqual(result["final_claim_audit_status"], "completed")

    async def test_model_failure_preserves_pre_audit_draft_in_trace(self):
        model = ScriptedAgent([
            answer("Cause not established from synthetic receipts."),
            answer("No verified command issuer in returned samples."),
            RuntimeError("synthetic model timeout"),
        ])
        try:
            result = await model.answer("Why did test lamp switch off?", [],
                                        FictionalMCP(), 60)
        finally:
            await model.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["final_claim_audit_status"], "model_error_fallback")
        self.assertEqual([row["stage"] for row in result["answer_stage_trace"]],
                         ["pre_source_review", "pre_final_audit"])
        self.assertEqual(result["answer"],
                         "No verified command issuer in returned samples.")

    async def test_disabled_audit_and_source_review_are_visible(self):
        model = ScriptedAgent([
            answer("Fictional state report observed."),
            answer("Fictional state report, origin remains unknown."),
        ])
        try:
            result = await model.answer(
                "Why did fixture stop?", [], FictionalMCP(), 60,
                enable_final_claim_audit=False,
            )
        finally:
            await model.close()
        self.assertEqual(result["final_claim_audit_status"], "skipped_low_time")
        self.assertEqual([row["stage"] for row in result["answer_stage_trace"]],
                         ["pre_source_review",
                          "post_source_review_without_audit"])

        model = ScriptedAgent([answer("Synthetic status only.")])
        try:
            result = await model.answer(
                "Show status", [], FictionalMCP(), 60,
                enable_source_review=False,
            )
        finally:
            await model.close()
        self.assertEqual(result["rounds"], 1)
        self.assertFalse(result["source_review_invoked"])
        self.assertEqual(result["answer_stage_trace"], [])


if __name__ == "__main__":
    unittest.main()

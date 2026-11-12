"""Fictional alpha.56 tests for final, tool-free source-to-claim audit.

These tests exercise agent orchestration only. They do not establish how a
cloud model will perform on live Hubitat receipts, and perform no writes.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from investigation_review import (
    FINAL_CLAIM_AUDIT_PROMPT, should_audit_completion,
)


class FictionalHistoryMCP:
    def __init__(self, with_command=False):
        self.calls = []
        self.with_command = with_command

    async def list_tools(self, refresh=False):
        return [{"name": "hub_list_device_events", "inputSchema": {
            "type": "object", "properties": {
                "deviceId": {"type": "string"},
                "limit": {"type": "integer"},
            },
        }}]

    async def call(self, name, args):
        self.calls.append((name, args))
        assert name == "hub_list_device_events"
        events = []
        if self.with_command:
            events.append({
                "name": "command-off", "type": "command",
                "date": "2026-03-02T20:10:00+0000",
                "producedBy": {"appId": 801, "name": "Fictional Scheduler"},
            })
        events.append({
            "name": "switch", "value": "off", "type": "physical",
            "date": "2026-03-02T20:10:01+0000",
            "producedBy": {"deviceId": "BRIDGE-1", "name": "Fictional Bridge"},
            "triggered": [{"appId": 802, "name": "Fictional Observer"}],
        })
        return {"content": [{"type": "text", "text": json.dumps({
            "deviceId": "LAB-4", "events": events, "count": len(events),
        })}]}


class ScriptedAgent(Agent):
    def __init__(self, answers):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 20)
        self.answers = list(answers)
        self.seen = []
        self.offered = []

    async def round(self, messages, tools, remaining):
        self.seen.append([dict(m) for m in messages])
        self.offered.append([t["function"]["name"] for t in tools])
        value = self.answers.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def call(name, args):
    return {"function": {"name": name, "arguments": args}}


def msg(content="", tool_calls=None):
    return {"content": content, "tool_calls": tool_calls or []}


class ClaimAuditOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_final_pass_challenges_false_external_attribution_without_tools(self):
        model = ScriptedAgent([
            msg(tool_calls=[call("hub_list_device_events",
                                 {"deviceId": "LAB-4", "limit": 10})]),
            msg("The bridge reported OFF; external action is verified."),
            msg("No command row was found; the hub did not initiate it."),
            msg("The fictional bridge reported OFF at 20:10:01. The limited "
                "returned events contain no command row, but neither a "
                "Hubitat-issued command nor external initiation has been "
                "established. The actual initiator is unknown."),
        ])
        mcp = FictionalHistoryMCP()
        try:
            result = await model.answer(
                "Why did the fictional lamp most recently switch OFF? "
                "Do not change anything.", [], mcp, 90,
            )
        finally:
            await model.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"], 4)
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(result["source_review_kind"], "causal")
        self.assertTrue(result["final_claim_audit_invoked"])
        self.assertEqual(result["final_claim_audit_status"], "completed")
        self.assertEqual(model.offered[3], [])
        self.assertIn("initiator is unknown", result["answer"])
        self.assertEqual(len(mcp.calls), 1)
        self.assertIn("Final source-to-claim", model.seen[3][-1]["content"])

    async def test_positive_command_issuer_survives_final_calibration(self):
        model = ScriptedAgent([
            msg(tool_calls=[call("hub_list_device_events",
                                 {"deviceId": "LAB-4", "limit": 10})]),
            msg("The fictional bridge reported OFF."),
            msg("Cause unknown because the bridge only reports the state."),
            msg("At 20:10:00 a recorded command-off came from Fictional "
                "Scheduler. The bridge reported OFF at 20:10:01; its "
                "reporter is not the command issuer. The scheduler's "
                "internal reason remains unverified."),
        ])
        mcp = FictionalHistoryMCP(with_command=True)
        try:
            result = await model.answer(
                "Why did the fictional lamp most recently turn OFF? "
                "Do not change anything.", [], mcp, 90,
            )
        finally:
            await model.close()
        self.assertEqual(result["final_claim_audit_status"], "completed")
        self.assertIn("command-off", result["answer"])
        self.assertIn("internal reason remains unverified", result["answer"])
        self.assertEqual(len(mcp.calls), 1)
        self.assertEqual(model.offered[-1], [])

    async def test_audit_model_error_preserves_pre_audit_draft(self):
        draft = "Observed an OFF state; issuer not established by returned rows."
        model = ScriptedAgent([
            msg(tool_calls=[call("hub_list_device_events",
                                 {"deviceId": "LAB-4", "limit": 10})]),
            msg("An OFF state was recorded."),
            msg(draft),
            RuntimeError("Synthetic model failure"),
        ])
        mcp = FictionalHistoryMCP()
        try:
            result = await model.answer("Why did the lamp switch OFF?",
                                        [], mcp, 90)
        finally:
            await model.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["answer"], draft)
        self.assertEqual(result["final_claim_audit_status"], "model_error_fallback")
        self.assertEqual(len(mcp.calls), 1)

    async def test_unsolicited_final_tool_request_never_executes(self):
        draft = "The returned events do not establish the initiator."
        model = ScriptedAgent([
            msg(tool_calls=[call("hub_list_device_events",
                                 {"deviceId": "LAB-4", "limit": 10})]),
            msg("An OFF state was reported."),
            msg(draft),
            msg(tool_calls=[call("hub_list_device_events",
                                 {"deviceId": "LAB-4", "limit": 20})]),
        ])
        mcp = FictionalHistoryMCP()
        try:
            result = await model.answer("Why did the lamp switch OFF?",
                                        [], mcp, 90)
        finally:
            await model.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["answer"], draft)
        self.assertEqual(result["final_claim_audit_status"], "tool_request_fallback")
        self.assertEqual(len(mcp.calls), 1)
        self.assertEqual(model.offered[-1], [])


class FinalAuditPromptTests(unittest.TestCase):
    def test_audit_is_general_and_time_bounded(self):
        self.assertIn("original successful tool receipts", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("physical-tagged state report", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("real command-off issuer", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("There are NO tools", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertTrue(should_audit_completion(
            source_review_invoked=True, already_audited=False,
            remaining_seconds=40, has_draft=True,
        ))
        self.assertFalse(should_audit_completion(
            source_review_invoked=True, already_audited=False,
            remaining_seconds=3, has_draft=True,
        ))
        self.assertFalse(should_audit_completion(
            source_review_invoked=False, already_audited=False,
            remaining_seconds=40, has_draft=True,
        ))


if __name__ == "__main__":
    unittest.main()

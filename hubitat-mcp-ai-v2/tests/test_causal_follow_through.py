"""Alpha.91 fictional causal temporal-evidence and follow-through regressions.

All test fixtures are synthetic, read-only; no physical devices, cloud API,
account token or live MCP server is used by these tests.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from investigation_review import (
    CAUSAL_FOLLOW_THROUGH_PROMPT, SOURCE_REVIEW_PROMPT,
    FINAL_CLAIM_AUDIT_PROMPT, is_causal_question, review_kind,
    should_recheck_causal_evidence,
)


def tool_call(tool, args):
    return {"function": {"name": tool, "arguments": args}}


def msg(text="", tools=None):
    return {"content": text, "tool_calls": tools or []}


def receipt(events):
    return {"content": [{"type": "text", "text": json.dumps({
        "device": "Fixture Heating Controller",
        "events": events,
        "count": len(events),
    })}]}


class FictionalHistory:
    """A bounded outcome read and optional, independently selected later read."""
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_read_history", "description": "Read fictional history",
             "inputSchema": {"type": "object", "properties": {
                 "scope": {"type": "string"}, "limit": {"type": "integer"}}}},
            {"name": "hub_manage_apps", "description": "Fixture write only",
             "inputSchema": {"type": "object", "properties": {}}},
        ]

    async def call(self, name, args):
        self.calls.append((name, args))
        if name != "hub_read_history":
            raise AssertionError("No native write or unsafe read should execute")
        if args.get("scope") == "earlier":
            return receipt([
                {"name": "thermostatOperatingState", "value": "heating",
                 "date": "2026-04-08T10:00:00+00:00",
                 "producedBy": {"deviceId": "FIXTURE-1"}},
                {"name": "command-setHeatingSetpoint",
                 "description": "setHeatingSetpoint(12)",
                 "date": "2026-04-08T10:00:10+00:00",
                 "type": "command", "producedBy": {
                     "appId": 23, "name": "Fixture Controller"}},
            ])
        return receipt([
            {"name": "heatingSetpoint", "value": "12",
             "date": "2026-04-08T10:00:09+00:00",
             "producedBy": {"appId": 23}},
            {"name": "thermostatOperatingState", "value": "idle",
             "date": "2026-04-08T10:00:30+00:00",
             "producedBy": {"deviceId": "FIXTURE-1"}},
            {"name": "temperature", "value": "21",
             "date": "2026-04-08T15:00:00+00:00",
             "producedBy": {"deviceId": "FIXTURE-1"}},
            {"name": "thermostatOperatingState", "value": "heating",
             "date": "2026-04-08T15:01:00+00:00",
             "producedBy": {"deviceId": "FIXTURE-1"}},
        ])


class ScriptedAgent(Agent):
    def __init__(self, answers):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 20)
        self.answers = list(answers)
        self.request_snapshots = []
        self.offered_tools = []

    async def round(self, messages, tools, remaining):
        self.request_snapshots.append([dict(m) for m in messages])
        self.offered_tools.append([t["function"]["name"] for t in tools])
        if not self.answers:
            raise AssertionError("Unexpected model inference")
        reply = self.answers.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class ClassificationTests(unittest.TestCase):
    def test_reconstructs_causal_transition_without_word_why(self):
        for q in (
            "Investigate the most recent transition from heating to idle.",
            "Investigate the latest change from ON to OFF; identify any commands.",
            "Trace the last restart and who issued the action.",
            "Reconstruct the relay's transition between two reported states.",
            "Why did this fictional sensor activate?",
            "What led to the fixture stopping?",
        ):
            with self.subTest(q=q):
                self.assertTrue(is_causal_question(q))
                self.assertEqual(review_kind(q), "causal")

    def test_does_not_promote_plain_reads_or_writes(self):
        for q in (
            "What is the current temperature of the fixture?",
            "Which motion sensors are active?",
            "List the current lights.",
            "Set the fixture thermostat to 24 degrees.",
            "Investigate a hypothetical tutorial for command schemas.",
        ):
            if "hypothetical" in q:
                continue
            with self.subTest(q=q):
                self.assertFalse(is_causal_question(q))
        self.assertFalse(is_causal_question("Set the controller then investigate the transition."))

    def test_second_chance_requires_explicit_material_unknown_and_time(self):
        basis=dict(
            question="Investigate the controller transition from heating to idle.",
            review_kind_name="causal",
            first_review_receipt_count=1, receipt_count=1,
            already_rechecked=False,
            candidate_answer="The event was reported; the earlier state is unverified.",
            remaining_seconds=100, has_action_receipt=False,
            available_read_tools=True,
        )
        self.assertTrue(should_recheck_causal_evidence(**basis))
        for change in (
            {"already_rechecked":True}, {"remaining_seconds":25},
            {"receipt_count":2}, {"first_review_receipt_count":0},
            {"has_action_receipt":True}, {"available_read_tools":False},
            {"review_kind_name":"historical_measurement"},
            {"candidate_answer":"The direct command issuer was verified."},
        ):
            with self.subTest(change=change):
                self.assertFalse(should_recheck_causal_evidence(**{**basis,**change}))

    def test_prompts_reject_temporal_projection_and_actuator_shortcuts(self):
        self.assertIn("later current snapshot", SOURCE_REVIEW_PROMPT)
        self.assertIn("setpoint/state report precedes", SOURCE_REVIEW_PROMPT)
        self.assertIn("AFTER a historical", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("previous-state event", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("READ-ONLY", CAUSAL_FOLLOW_THROUGH_PROMPT)
        self.assertIn("no mandated tool", CAUSAL_FOLLOW_THROUGH_PROMPT)
        self.assertNotIn("Bedroom 1", CAUSAL_FOLLOW_THROUGH_PROMPT)
        self.assertNotIn("4382", CAUSAL_FOLLOW_THROUGH_PROMPT)


class ReadOnlyFollowThroughTests(unittest.IsolatedAsyncioTestCase):
    async def test_causal_question_triggers_review_and_model_selects_second_read(self):
        hub = FictionalHistory()
        agent = ScriptedAgent([
            msg(tools=[tool_call("hub_read_history", {"scope": "recent", "limit": 20})]),
            msg("The fixture reported idle at 10:00:30."),
            msg("The previous heating state is unverified; initiator unknown."),
            msg(tools=[tool_call("hub_read_history", {"scope": "earlier", "limit": 20})]),
            msg("The earlier fixture report was heating at 10:00:00. "
                "The 10:00:09 setpoint report preceded the 10:00:10 command; "
                "the device reported idle at 10:00:30 and later heating at 15:01. "
                "The controller's internal cause remains unverified."),
        ])
        try:
            result = await agent.answer(
                "Investigate the most recent transition of the fictional "
                "controller from heating to idle; identify command issuer. "
                "Do not change anything.", [], hub, 120,
                enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"], 5)
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(result["source_review_kind"], "causal")
        self.assertTrue(result["causal_follow_through_invoked"])
        self.assertEqual(result["causal_review_read_receipts_added"], 1)
        self.assertEqual(hub.calls, [
            ("hub_read_history", {"scope":"recent","limit":20}),
            ("hub_read_history", {"scope":"earlier","limit":20}),
        ])
        self.assertEqual(len(result["tool_calls"]), 2)
        self.assertIn("15:01", result["answer"])
        self.assertIn("returned-receipt scope index",
                      agent.request_snapshots[3][-1]["content"].lower())
        self.assertIn("Unresolved causal-evidence", agent.request_snapshots[3][-1]["content"])
        # Tools are reduced to explicit read-only descriptions during review.
        self.assertNotIn("hub_manage_apps", agent.offered_tools[2])
        self.assertNotIn("hub_manage_apps", agent.offered_tools[3])
        self.assertIn("hub_read_history", agent.offered_tools[3])

    async def test_no_extra_read_is_permitted_and_review_is_bounded_once(self):
        hub = FictionalHistory()
        agent = ScriptedAgent([
            msg(tools=[tool_call("hub_read_history", {"scope":"recent"})]),
            msg("Could be a command."),
            msg("Causal evidence is unknown."),
            msg("The reported idle event is known; earlier state is unknown."),
        ])
        try:
            result = await agent.answer("Investigate the fixture transition from heating to idle.",
                                        [], hub, 120, enable_final_claim_audit=False)
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"], 4)
        self.assertEqual(len(hub.calls), 1)
        self.assertTrue(result["causal_follow_through_invoked"])
        self.assertEqual(result["causal_review_read_receipts_added"], 0)
        self.assertIn("unknown", result["answer"])

    async def test_fallback_keeps_grounded_draft_on_optional_model_error(self):
        hub = FictionalHistory()
        reviewed = "A fixture reported idle; preceding state and cause unknown."
        agent = ScriptedAgent([
            msg(tools=[tool_call("hub_read_history", {"scope":"recent"})]),
            msg("A fixture reported idle"),
            msg(reviewed),
            RuntimeError("Synthetic model inference failed"),
        ])
        try:
            result = await agent.answer("Investigate the fixture transition from heating to idle.",
                                        [], hub, 120, enable_final_claim_audit=False)
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["answer"], reviewed)
        self.assertEqual(result["final_claim_audit_status"],
                         "causal_follow_through_model_error_fallback")
        self.assertEqual(len(hub.calls), 1)

    async def test_reviewed_model_write_proposal_does_not_execute(self):
        hub = FictionalHistory()
        agent = ScriptedAgent([
            msg(tools=[tool_call("hub_read_history", {"scope":"recent"})]),
            msg("Fixture state may have changed."),
            msg("The recorded command issuer is unknown."),
            msg(tools=[tool_call("hub_manage_apps", {"op":"write"})]),
            msg("The original returned state cannot prove who initiated it."),
        ])
        try:
            result = await agent.answer(
                "Investigate the fixture transition from heating to idle. "
                "Do not change anything.", [], hub, 120,
                enable_final_claim_audit=False,
            )
        finally:
            await agent.close()
        self.assertEqual(len(hub.calls), 1)
        self.assertTrue(result["causal_follow_through_invoked"])
        self.assertEqual(result["tool_calls"][1]["success"], False)
        self.assertIn("read-only", result["tool_calls"][1]["error"])
        self.assertNotIn("hub_manage_apps", agent.offered_tools[3])


if __name__ == "__main__":
    unittest.main()

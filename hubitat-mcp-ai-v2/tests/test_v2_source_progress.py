"""V2 source-frontier and failed-read recovery, using fictional original receipts.

No real MCP hub, cloud AI, device writes or fabricated positive evidence.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from source_progress import current_source_progress
from investigation_review import should_offer_fresh_source_recovery
from test_fresh_source_recovery import QUESTION


def receipt(name, args=None, *, success=True, kind="tool_result",
            native=None, executed=True):
    if native is None:
        native = {"count": 1, "events": [{
            "name": "switch", "value": "off",
            "date": "2030-04-02T20:01:02.123+0000"}]}
    return {
        "name": name, "arguments": args or {}, "success": success,
        "result_kind": kind, "operation_executed": executed,
        "response": json.dumps({
            "content": [{"type": "text", "text": json.dumps(native)}]
        }),
    }


class OriginalSourceProgressTests(unittest.TestCase):
    def test_failed_and_successful_reads_have_different_evidence_status(self):
        rows = [
            receipt("hub_list_device_events", {"deviceId": 101}, success=False),
            receipt("hub_list_device_events", {"deviceId": 101}),
            receipt("hub_list_device_events", {"deviceId": 101}),  # duplicate
            receipt("hub_list_device_events", {"deviceId": 202}),
            receipt("hub_read_device_data", {"deviceId": 202},
                    success=True, native={"success": False, "error": "permission denied"}),
            receipt("hub_set_rule", {"id": 7}, success=True),
            receipt("homebrain_read_clock", {}, success=True),
            receipt("homebrain_inspect_mcp_catalog", {}, success=True),
            receipt("hub_get_tool_guide", {}, kind="tool_catalog"),
        ]
        outcome = current_source_progress(rows)
        self.assertEqual(outcome["read_attempts"], 5)
        self.assertEqual(outcome["successful_read_receipts"], 3)
        self.assertEqual(outcome["failed_read_receipts"], 2)
        self.assertEqual(outcome["distinct_successful_request_scopes"], 2)
        self.assertTrue(outcome["has_successful_current_source"])
        self.assertFalse(outcome["historical_coverage_verified"])
        self.assertFalse(outcome["source_sufficiency_assessed"])
        self.assertNotIn("deviceId", json.dumps(outcome))

    def test_only_failed_or_schema_reads_never_prove_source_completion(self):
        rows = [
            receipt("hub_read_history", {"deviceId": 101}, success=False),
            receipt("hub_get_device", {"deviceId": 101}, kind="contract_error",
                    success=False, executed=False),
            receipt("homebrain_read_prior_evidence", {"receipt_id": "x"}),
        ]
        outcome = current_source_progress(rows)
        self.assertFalse(outcome["has_successful_current_source"])
        self.assertEqual(outcome["read_attempts"], 1)
        self.assertEqual(outcome["successful_read_receipts"], 0)
        self.assertEqual(outcome["failed_read_receipts"], 1)

    def test_explicit_no_fresh_read_and_write_boundaries_unchanged(self):
        for q in (
            QUESTION + " No new tool calls.",
            QUESTION + " Use only previous receipts.",
        ):
            self.assertFalse(should_offer_fresh_source_recovery(
                q, kind="historical_measurement",
                has_current_read_attempt=True,
                has_successful_current_read=False,
                available_read_tools=True,
                has_action_receipt=False,
            ))
        self.assertTrue(should_offer_fresh_source_recovery(
            QUESTION, kind="historical_measurement",
            has_current_read_attempt=True,  # initial read failed
            has_successful_current_read=False,
            available_read_tools=True, has_action_receipt=False,
        ))
        self.assertFalse(should_offer_fresh_source_recovery(
            QUESTION, kind="historical_measurement",
            has_current_read_attempt=True,
            has_successful_current_read=True,
            available_read_tools=True, has_action_receipt=False,
        ))


class FakeSourceMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_list_device_events",
             "description": "Read-only event source",
             "inputSchema": {"type": "object", "properties": {
                 "deviceId": {"type": "integer"},
                 "hoursBack": {"type": "integer"}}}},
            {"name": "hub_list_devices",
             "description": "Read-only device inventory",
             "inputSchema": {"type": "object", "properties": {
                 "labelFilter": {"type": "string"}}}},
            {"name": "hub_set_rule",
             "inputSchema": {"type": "object", "properties": {}}},
        ]

    async def call(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "hub_list_device_events":
            # A native failed read is not evidence of an empty event store.
            return {"isError": True, "content": [
                {"type": "text", "text": "Temporary read failure"}
            ]}
        if name == "hub_list_devices":
            return {"content": [{"type": "text", "text": json.dumps({
                "devices": [{"id": "101", "label": "Fictional Kitchen Light"}],
                "count": 1, "total": 1, "labelFilter": args.get("labelFilter"),
            })}]}
        raise AssertionError("No write or invented tool should be called")


def tool(name, **args):
    return {"tool_calls": [{"function": {
        "name": name, "arguments": args,
    }}]}


class FictionalAgent(Agent):
    def __init__(self, script):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 10)
        self.script = list(script)
        self.prompts = []
        self.rounds_seen = 0

    async def round(self, messages, tools, remaining):
        self.rounds_seen += 1
        self.prompts.append(messages[-1]["content"] if messages else "")
        if not self.script:
            raise AssertionError("Source review wasted an extra cloud round")
        return self.script.pop(0)


class FailureAwareRecoveryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_failed_history_read_gets_existing_read_only_recovery(self):
        hub = FakeSourceMCP()
        model = FictionalAgent([
            tool("hub_list_device_events", deviceId=101, hoursBack=6),
            {"content": "The history call failed; event chronology is unknown."},
            tool("hub_list_devices", labelFilter="Fictional Kitchen Light"),
            {"content": "The device exists, but the event-history source failed; "
                        "its transitions and command issuers are unknown."},
        ])
        try:
            result = await model.answer(
                QUESTION, [], hub, 90,
                enable_final_claim_audit=False,
                enable_causal_follow_through=False,
            )
        finally:
            await model.close()
        self.assertEqual(model.rounds_seen, 4)
        self.assertTrue(result["source_review_invoked"])
        self.assertTrue(result["fresh_source_recovery_invoked"])
        self.assertIn("No successful current-request", model.prompts[2])
        self.assertEqual([x[0] for x in hub.calls], [
            "hub_list_device_events", "hub_list_devices",
        ])
        self.assertEqual(result["current_read_source_progress"]
                         ["successful_read_receipts"], 1)
        self.assertEqual(result["current_read_source_progress"]
                         ["failed_read_receipts"], 1)
        self.assertIn("unknown", result["answer"])

    async def test_failure_then_prose_only_has_no_extra_claim_audit(self):
        hub = FakeSourceMCP()
        model = FictionalAgent([
            tool("hub_list_device_events", deviceId=101, hoursBack=6),
            {"content": "Native event history failed; data could be missing."},
            {"content": "The event chronology is unverified because the native "
                        "read failed. No events can be excluded."},
        ])
        try:
            result = await model.answer(
                QUESTION, [], hub, 90,
                enable_causal_follow_through=False,
            )
        finally:
            await model.close()
        self.assertEqual(model.rounds_seen, 3)
        self.assertTrue(result["fresh_source_recovery_invoked"])
        self.assertFalse(result["final_claim_audit_invoked"])
        self.assertEqual(
            result["current_read_source_progress"]["successful_read_receipts"], 0)
        self.assertEqual(
            result["current_read_source_progress"]["failed_read_receipts"], 1)
        self.assertEqual(result["fresh_source_recovery_status"],
                         "read_attempt_failed")
        self.assertIn("unverified", result["answer"])


if __name__ == "__main__":
    unittest.main()

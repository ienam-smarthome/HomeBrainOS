"""Alpha.125 fictional command issuer vs internal decision regressions.

No cloud, native Hubitat account, real device, heating controller or write.
Fixtures cover a generic switch controller and generic log source.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from causal_decision_frontier import (
    causal_controller_frontier, CONTROLLER_DECISION_CHECKPOINT,
)
from investigation_review import should_prompt_controller_decision_gap


def source_receipt(events, device="FIXTURE-1"):
    return {
        "name": "hub_list_device_events",
        "arguments": {"deviceId": device, "hoursBack": 2, "limit": 30},
        "success": True,
        "response": json.dumps({"content": [{"type": "text", "text":
            json.dumps({"deviceId": device, "events": events, "count": len(events)})}]}),
    }


COMMAND = {
    "name": "command-on", "type": "command", "description": "Command called: on()",
    "date": "2030-11-16T11:32:35.270+0000",
    "producedBy": {"appId": 23, "name": "Fictional controller"},
}
ATTRIBUTE_BEFORE_COMMAND = {
    "name": "switch", "value": "on", "type": "physical",
    "date": "2030-11-16T11:32:35.205+0000",
    "producedBy": {"deviceId": "FIXTURE-1", "name": "Fixture bridge"},
    "triggered": [{"appId": 999, "name": "Fixture listener"}],
}


def scoped_log_receipt(app_id=23, *, success=True):
    return {
        "name": "hub_read_app_logs",
        "arguments": {"appId": app_id, "since": "2030-11-16T11:30:00Z"},
        "success": success,
        "response": json.dumps({"content": [{"type": "text", "text":
            json.dumps({"entries": [{
                "date": "2030-11-16T11:32:35.180+0000",
                "message": "Fixture input low; waiting interval completed",
                "appId": app_id,
            }]})}]}),
    }


class ControllerFrontierTests(unittest.TestCase):
    def test_real_command_issuer_not_listener_and_chronology_preserved(self):
        receipt = source_receipt([ATTRIBUTE_BEFORE_COMMAND, COMMAND])
        original = json.dumps(receipt, sort_keys=True)
        result = causal_controller_frontier([receipt])
        self.assertEqual(result["original_device_command_rows_indexed"], 1)
        self.assertEqual(result["recorded_issuer_app_ids"], ["23"])
        self.assertEqual(result["recent_original_command_rows"][0]["observed_original_date"],
                         COMMAND["date"])
        self.assertEqual(result["recent_original_command_rows"][0]["event_name"], "command-on")
        self.assertNotIn("999", result["recorded_issuer_app_ids"])
        self.assertTrue(result["controller_decision_source_unchecked_for_model_review"])
        self.assertTrue(result["recorded_command_is_not_independent_physical_activation"])
        self.assertEqual(original, json.dumps(receipt, sort_keys=True))

    def test_app_log_scope_and_failure_do_not_prove_decision(self):
        initial = source_receipt([COMMAND])
        unrelated = scoped_log_receipt(22)
        result = causal_controller_frontier([unrelated, initial])
        self.assertTrue(result["controller_decision_source_unchecked_for_model_review"])
        self.assertEqual(result["app_scoped_execution_log_attempts_for_recorded_issuers"], 0)
        attempted = causal_controller_frontier([initial, scoped_log_receipt(success=False)])
        self.assertFalse(attempted["controller_decision_source_unchecked_for_model_review"])
        self.assertEqual(attempted["app_scoped_execution_log_attempts_for_recorded_issuers"], 1)
        self.assertEqual(attempted["app_scoped_execution_log_successes_for_recorded_issuers"], 0)
        read = causal_controller_frontier([scoped_log_receipt(), initial])
        self.assertFalse(read["controller_decision_source_unchecked_for_model_review"])
        self.assertEqual(read["app_scoped_execution_log_successes_for_recorded_issuers"], 1)
        self.assertTrue(read["command_issuer_is_not_decision_trigger"])

    def test_reporter_only_and_current_app_config_do_not_verify_trigger(self):
        reading = source_receipt([ATTRIBUTE_BEFORE_COMMAND])
        self.assertFalse(causal_controller_frontier([reading])[
            "controller_decision_source_unchecked_for_model_review"])
        config = {"name": "hub_get_app", "arguments": {"appId": 23},
                  "success": True,
                  "response": json.dumps({"content": [{"type": "text",
                      "text": json.dumps({"id": 23, "settings": {}})}]})}
        frontier = causal_controller_frontier([source_receipt([COMMAND]), config])
        self.assertEqual(frontier["app_scoped_other_read_successes_for_recorded_issuers"], 1)
        self.assertTrue(frontier["controller_decision_source_unchecked_for_model_review"])
        self.assertFalse(causal_controller_frontier([{
            "name": "hub_list_device_events", "success": False,
            "response": source_receipt([COMMAND])["response"]}])[
                "controller_decision_source_unchecked_for_model_review"])

    def test_review_guard_no_extra_tool_for_forbidden_reads_or_writes(self):
        frontier = causal_controller_frontier([source_receipt([COMMAND])])
        normal = dict(
            review_kind_name="causal", source_frontier=frontier,
            has_action_receipt=False,
        )
        self.assertTrue(should_prompt_controller_decision_gap(
            "Why did the fixture switch on?", **normal))
        self.assertFalse(should_prompt_controller_decision_gap(
            "Why did the fixture switch on? Do not make any new tool calls.", **normal))
        self.assertFalse(should_prompt_controller_decision_gap(
            "Turn on the fixture and explain why.", **normal))
        self.assertFalse(should_prompt_controller_decision_gap(
            "What is the fixture's current state?", **normal))
        self.assertFalse(should_prompt_controller_decision_gap(
            "Why did the fixture switch on?",
            **{**normal, "has_action_receipt": True}))
        self.assertIn("READ-ONLY", CONTROLLER_DECISION_CHECKPOINT)
        self.assertIn("no relevant read", CONTROLLER_DECISION_CHECKPOINT)
        for forbidden in ("Bedroom 3", "Thermostat", "3970"):
            self.assertNotIn(forbidden, CONTROLLER_DECISION_CHECKPOINT)


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_list_device_events",
             "description": "Read fictional device history", "inputSchema": {
                 "type": "object", "properties": {
                     "deviceId": {"type": "string"},
                     "hoursBack": {"type": "integer"},
                     "limit": {"type": "integer"}}}},
            {"name": "hub_read_app_logs",
             "description": "Read fictional app runtime logs", "inputSchema": {
                 "type": "object", "properties": {
                     "appId": {"type": "integer"},
                     "since": {"type": "string"}}}},
            {"name": "hub_manage_apps", "description": "Unsafe write gateway",
             "inputSchema": {"type": "object", "properties": {}}},
        ]

    async def call(self, name, args):
        self.calls.append((name, args))
        if name == "hub_list_device_events":
            return json.loads(source_receipt([ATTRIBUTE_BEFORE_COMMAND, COMMAND])["response"])
        if name == "hub_read_app_logs":
            return json.loads(scoped_log_receipt(args["appId"])["response"])
        raise AssertionError("No native write may occur")


def tool_call(name, args):
    return {"content": "", "tool_calls": [{"function": {
        "name": name, "arguments": args,
    }}]}


class ScriptedAgent(Agent):
    def __init__(self, *replies):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 20)
        self.replies = list(replies)
        self.snapshots = []
        self.review_catalog = []

    async def round(self, messages, tools, remaining):
        self.snapshots.append([dict(m) for m in messages])
        self.review_catalog.append([x["function"]["name"] for x in tools])
        if not self.replies:
            raise AssertionError("Unexpected model round")
        return self.replies.pop(0)


class ModelLedDecisionReadTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_elects_app_log_in_existing_causal_review(self):
        log_args = {"appId": 23, "since": "2030-11-16T11:30:00Z"}
        agent = ScriptedAgent(
            tool_call("hub_list_device_events",
                      {"deviceId": "FIXTURE-1", "hoursBack": 2, "limit": 30}),
            {"content": "Fictional controller issued ON; its decision remains unknown."},
            tool_call("hub_read_app_logs", log_args),
            {"content": "The original app log records an input-low and "
                        "elapsed confirmation decision near the ON command. "
                        "The fixture reported ON; independent physical operation "
                        "remains unverified."},
        )
        hub = FakeMCP()
        try:
            result = await agent.answer(
                "Why did the fictional fixture switch on? Do not change anything.",
                [], hub, 90, enable_final_claim_audit=False,
                enable_causal_follow_through=False,
            )
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"], 4)
        self.assertTrue(result["source_review_invoked"])
        self.assertEqual(result["source_review_kind"], "causal")
        self.assertFalse(result["causal_follow_through_invoked"])
        self.assertEqual(hub.calls, [
            ("hub_list_device_events", {"deviceId": "FIXTURE-1", "hoursBack": 2, "limit": 30}),
            ("hub_read_app_logs", log_args),
        ])
        self.assertTrue(result["causal_controller_decision_frontier"][
            "app_scoped_execution_log_successes_for_recorded_issuers"] == 1)
        self.assertFalse(result["causal_controller_decision_frontier"][
            "controller_decision_source_unchecked_for_model_review"])
        self.assertIn("Controller-decision evidence checkpoint",
                      agent.snapshots[2][-1]["content"])
        self.assertNotIn("hub_manage_apps", agent.review_catalog[2])
        self.assertIn("independent physical", result["answer"])

    async def test_model_can_decline_and_host_does_not_force_app_read(self):
        agent = ScriptedAgent(
            tool_call("hub_list_device_events",
                      {"deviceId": "FIXTURE-1", "hoursBack": 2, "limit": 30}),
            {"content": "The app was the recorded issuer, not the known cause."},
            {"content": "The recorded command issuer is fixture app 23; "
                        "why that app decided to act remains unknown."},
        )
        hub = FakeMCP()
        try:
            result = await agent.answer(
                "Why did the fictional fixture switch on? Do not change anything.",
                [], hub, 90, enable_final_claim_audit=False,
                enable_causal_follow_through=False,
            )
        finally:
            await agent.close()
        self.assertTrue(result["success"])
        self.assertEqual(result["rounds"], 3)
        self.assertEqual(len(hub.calls), 1)
        self.assertTrue(result["causal_controller_decision_frontier"][
            "controller_decision_source_unchecked_for_model_review"])
        self.assertIn("unknown", result["answer"])


if __name__ == "__main__":
    unittest.main()

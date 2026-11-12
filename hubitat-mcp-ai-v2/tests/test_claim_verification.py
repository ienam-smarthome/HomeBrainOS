"""Alpha.55 model-led, source-to-claim verification regressions.

Purely fictional MCP receipts. Tests prove tool choice stays with the model
and source fields are not silently interpreted as stronger state claims.
No actual hub, network, model API, or write operation is used.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from config_evidence import config_source_map
from investigation_review import (
    VERIFICATION_REVIEW_PROMPT, MEASUREMENT_REVIEW_PROMPT,
    is_source_verification_question, is_causal_question, review_kind,
    should_review_completion,
)


def config_receipt(*, direct_paused=None, pause_button=True):
    app = {
        "id": 801, "label": "Fictional Scheduler",
        "name": "Synthetic Rule", "disabled": False, "installed": True,
        "parentAppId": 42, "appType": {
            "namespace": "fictional", "name": "Synthetic Rule",
            "system": False,
        },
    }
    if direct_paused is not None:
        app["paused"] = direct_paused
    response = {
        "success": True, "app": app,
        "page": {
            "name": "mainPage", "sections": [], "hrefs": [],
        },
        "controls": (
            [{"kind": "button", "name": "pauseToggle", "title": "Pause"}]
            if pause_button else []
        ),
    }
    return {"content": [{"type": "text", "text": json.dumps(response)}]}


def event_receipt():
    rows = [
        {"name": "command-off", "type": "command",
         "date": "2026-03-01T11:00:00.000+0000",
         "producedBy": {"appId": 801, "name": "Fictional Scheduler"}},
        {"name": "switch", "value": "off", "type": "physical",
         "date": "2026-03-01T11:00:01.000+0000",
         "producedBy": {"deviceId": "BRIDGE-1", "name": "Fictional Bridge"}},
    ]
    return {"content": [{"type": "text", "text": json.dumps({
        "device": "Fictional Lamp", "events": rows, "count": 2,
    })}]}


class EvidencePropertiesTests(unittest.TestCase):
    def test_control_button_and_disabled_false_do_not_establish_paused(self):
        raw = config_receipt()
        unchanged = json.dumps(raw, sort_keys=True)
        result = config_source_map(raw)
        self.assertEqual(result["typed_boolean_flags_in_returned_app_record"][
            "disabled"], False)
        self.assertEqual(result["returned_app_type_identity"]["name"], "Synthetic Rule")
        self.assertNotIn("paused", result["typed_boolean_flags_in_returned_app_record"])
        self.assertFalse(result["ui_control_labels_verify_status"])
        self.assertTrue(result["app_flags_absent_from_this_record_are_unknown"])
        self.assertFalse(result["parent_app_identity_verified_by_this_page"])
        self.assertEqual(json.dumps(raw, sort_keys=True), unchanged)

    def test_directly_returned_typed_paused_flag_is_preserved(self):
        value = config_source_map(config_receipt(direct_paused=True))
        self.assertIs(value["typed_boolean_flags_in_returned_app_record"]["paused"], True)
        value2 = config_source_map(config_receipt(direct_paused=False))
        self.assertIs(value2["typed_boolean_flags_in_returned_app_record"]["paused"], False)

    def test_claim_boundary_headline_precedes_unchanged_native_config(self):
        agent = Agent.__new__(Agent)
        agent.cpu_cores = 4
        raw = config_receipt()
        displayed = agent.present_native_result(raw, {"appId": "801"})
        self.assertEqual(next(iter(displayed)), "client_claim_evidence_headline")
        headline = displayed["client_claim_evidence_headline"]
        self.assertTrue(headline["ui_control_labels_are_not_typed_status_values"])
        self.assertNotIn("paused", headline["typed_app_boolean_fields"])
        self.assertFalse(headline["parent_app_identity_independently_verified"])
        self.assertEqual(displayed["content"], raw["content"])

    def test_event_row_limit_is_exposed_without_erasing_issuer(self):
        agent = Agent.__new__(Agent)
        agent.cpu_cores = 4
        raw = event_receipt()
        displayed = agent.present_native_result(raw, {
            "deviceId": "LAB-20", "limit": 2,
        })
        headline = displayed["client_claim_evidence_headline"]
        self.assertEqual(headline["source_kind"], "bounded returned device event rows")
        self.assertTrue(headline["row_limit_reached"])
        self.assertEqual(headline["observed_command_row_count"], 1)
        self.assertFalse(headline["unseen_rows_or_commands_proven_absent"])
        self.assertEqual(displayed["content"], raw["content"])
        self.assertEqual(
            displayed["client_command_issuer_scope"]["command_rows_returned"], 1
        )

    def test_intent_routing_is_general_and_protects_short_requests(self):
        for question in (
            "Inspect the configuration, current status, and evidence for relay 8.",
            "Verify the typed health flags of this service.",
            "Audit the collected event logs for an unknown appliance.",
        ):
            self.assertTrue(is_source_verification_question(question), question)
            self.assertEqual(review_kind(question), "source_verification")
        self.assertTrue(is_causal_question(
            "Investigate whether a pump's last change was caused by a timer"
        ))
        self.assertEqual(review_kind(
            "Investigate whether a pump's last change was caused by a timer"),
            "causal")
        self.assertFalse(is_source_verification_question(
            "Investigate the last reported activity of a sensor. Distinguish "
            "stale telemetry from proven outage or session failure. Check "
            "device health, relevant events and logs. State limitations."
        ))
        self.assertIsNone(review_kind("Show current status"))
        self.assertFalse(is_source_verification_question(
            "Turn on the valve then inspect its status"
        ))
        self.assertTrue(should_review_completion(
            "Inspect device status and evidence", available_tools=True,
            already_reviewed=False, remaining_seconds=20,
        ))
        self.assertFalse(should_review_completion(
            "Inspect device status and evidence", available_tools=True,
            already_reviewed=False, remaining_seconds=2,
        ))
        self.assertIn("READ-ONLY", VERIFICATION_REVIEW_PROMPT)
        self.assertIn("An absent", VERIFICATION_REVIEW_PROMPT)
        self.assertIn("user's evidence conditions", MEASUREMENT_REVIEW_PROMPT)
        self.assertNotIn("Fictional Scheduler", VERIFICATION_REVIEW_PROMPT)


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [
            {"name": "hub_get_app_config",
             "inputSchema": {"type": "object", "properties": {
                 "appId": {"type": "string"}}}},
            {"name": "hub_get_app_status",
             "inputSchema": {"type": "object", "properties": {
                 "appId": {"type": "string"}}}},
            {"name": "hub_manage_apps",
             "inputSchema": {"type": "object", "properties": {}}},
        ]

    async def call(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "hub_get_app_config":
            return config_receipt()
        if name == "hub_get_app_status":
            return {"content": [{"type": "text",
                                 "text": '{"appId":801,"paused":false}'}]}
        raise AssertionError("Attempted a write or unknown tool")


def function_call(name, args):
    return {"function": {"name": name, "arguments": args}}


class ScriptedAgent(Agent):
    def __init__(self, script):
        super().__init__("http://127.0.0.1:11434", "fictional", "", 20)
        self.script = list(script)
        self.seen = []
        self.catalog_seen = []

    async def round(self, messages, tools, remaining):
        self.seen.append([dict(row) for row in messages])
        self.catalog_seen.append([tool["function"]["name"] for tool in tools])
        return self.script.pop(0)


class VerificationRoundtripTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_chooses_typed_followup_after_checkpoint(self):
        model = ScriptedAgent([
            {"content": "", "tool_calls": [
                function_call("hub_get_app_config", {"appId": "801"})]},
            {"content": "The Pause button proves the scheduler is not paused.",
             "tool_calls": []},
            {"content": "", "tool_calls": [
                function_call("hub_get_app_status", {"appId": "801"})]},
            {"content": (
                "The separate typed status read returned paused=false. "
                "The rendered Pause button alone did not prove that."
            ), "tool_calls": []},
            {"content": (
                "The verified status is paused=false from the typed status "
                "receipt. The Pause button is not status evidence."
            ), "tool_calls": []},
        ])
        mcp = FakeMCP()
        try:
            reply = await model.answer(
                "Inspect and verify this controller's current status and configuration. "
                "Do not change anything.", [], mcp, 90
            )
        finally:
            await model.close()
        self.assertTrue(reply["success"])
        self.assertTrue(reply["source_review_invoked"])
        self.assertEqual(reply["source_review_kind"], "source_verification")
        self.assertEqual(reply["rounds"], 5)
        self.assertTrue(reply["final_claim_audit_invoked"])
        self.assertEqual(reply["final_claim_audit_status"], "completed")
        self.assertEqual(model.catalog_seen[4], [])
        self.assertEqual([name for name, _ in mcp.calls],
                         ["hub_get_app_config", "hub_get_app_status"])
        self.assertEqual(model.catalog_seen[2],
                         ["hub_get_app_config", "hub_get_app_status"])
        self.assertIn("verification checkpoint", model.seen[2][-1]["content"])
        self.assertIn("paused=false", reply["answer"])
        self.assertTrue(all(x["success"] for x in reply["tool_calls"]))

    async def test_unknown_can_be_reported_without_forcing_second_read(self):
        model = ScriptedAgent([
            {"content": "", "tool_calls": [
                function_call("hub_get_app_config", {"appId": "801"})]},
            {"content": "The pause button indicates no pause.", "tool_calls": []},
            {"content": ("The current page has a Pause button and disabled=false; "
                         "a typed paused flag was not returned, so pause is unknown."),
             "tool_calls": []},
            {"content": ("The paused state is unknown. The current Pause "
                          "button and disabled=false do not verify paused."),
             "tool_calls": []},
        ])
        mcp = FakeMCP()
        try:
            reply = await model.answer(
                "Verify the paused state in a controller's configuration. "
                "Do not change anything.", [], mcp, 90
            )
        finally:
            await model.close()
        self.assertEqual(len(mcp.calls), 1)
        self.assertEqual(reply["rounds"], 4)
        self.assertTrue(reply["source_review_invoked"])
        self.assertEqual(reply["final_claim_audit_status"], "completed")
        self.assertIn("unknown", reply["answer"])


if __name__ == "__main__":
    unittest.main()

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
    final_claim_receipt_scope_index,
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

    async def answer(self, *args, **kwargs):
        # This fixture isolates the pre-existing final textual claim audit.
        # Alpha.91 follow-through is tested independently with opt-in fixtures.
        kwargs.setdefault("enable_causal_follow_through", False)
        return await super().answer(*args, **kwargs)

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
        self.assertIn("Returned-receipt scope index", model.seen[3][-1]["content"])
        self.assertIn('"limit":10', model.seen[3][-1]["content"])
        self.assertIn('"deviceId":"LAB-4"', model.seen[3][-1]["content"])

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
        # Time-window overlap and physical claims must be audited against
        # original receipts, not inferred from the first returned event.
        self.assertIn("first returned row is NOT the query start",
                      FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("inside the query", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("intervening nonzero readings", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertIn("independent physical verification",
                      FINAL_CLAIM_AUDIT_PROMPT)
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


    def test_scope_index_preserves_disjoint_returned_rows_and_requested_window(self):
        """Fictional overlap: requested interval includes focal event, but returned
        sensor rows begin later. The source index must not invent a retention cause.
        """
        native = {
            "sinceTimestamp": "2026-03-01T11:48:00+0000",
            "hoursBack": 24,
            "events": [{"name": "humidity", "value": "52",
                        "date": "2026-03-02T02:05:40+0000"}],
            "count": 1,
        }
        receipt = {
            "name": "hub_list_device_events",
            "arguments": {"deviceId": "LAB-SENSOR", "hoursBack": 24,
                          "secret": "do-not-export"},
            "success": True,
            "response": json.dumps({
                "client_claim_evidence_headline": {
                    "source_kind": "bounded returned device event rows",
                    "returned_row_count": 1,
                    "oldest_returned_event": "2026-03-02T02:05:40+0000",
                    "row_limit_reached": False,
                },
                "content": [{"type": "text", "text": json.dumps(native)}],
            }),
        }
        original = json.loads(receipt["response"])
        index = json.loads(final_claim_receipt_scope_index([receipt]))
        item = index["indexed_receipts"][0]
        self.assertEqual(item["arguments"]["hoursBack"], 24)
        self.assertEqual(item["original_returned_fields"]["sinceTimestamp"],
                         native["sinceTimestamp"])
        self.assertEqual(item["source_headline"]["oldest_returned_event"],
                         "2026-03-02T02:05:40+0000")
        self.assertNotIn("secret", json.dumps(index))
        self.assertNotIn("retention", json.dumps(index))
        self.assertEqual(json.loads(receipt["response"]), original,
                         "Read-only scope indexing must never mutate receipts")

    def test_fictional_reported_power_is_not_independent_confirmation(self):
        # No hardware/driver assumptions in the model-only audit contract.
        prompt = FINAL_CLAIM_AUDIT_PROMPT
        for requirement in ("device-reported 0 W",
                            "intervening nonzero readings",
                            "physical shutdown",
                            "reported outcome",
                            "independent physical verification"):
            self.assertIn(requirement, prompt)
        self.assertNotIn("Dehumidifier 1", prompt)
        self.assertNotIn("Bathroom Meter", prompt)



class SourceCoverageNavigationTests(unittest.TestCase):
    """Synthetic, non-identifying receipts; never live hub or cloud traffic."""

    def test_bounded_event_names_logs_and_controller_inputs_are_indexed(self):
        event_rows = {
            "client_event_attribute_scope": {
                "event_names": [
                    {"event_name": "command-off", "returned_count": 4,
                     "first_returned_event_utc": "2026-05-07T12:00:00Z"},
                    {"event_name": "switch", "returned_count": 6},
                    {"event_name": "networkStatus", "returned_count": 2},
                ],
            },
            "client_event_source_scope": {
                "events_returned": 12,
                "requested_limit": 12,
                "limit_reached": True,
            },
            "content": [{"type": "text", "text": json.dumps({
                "events": [{"name": "command-off", "date": "2026-05-07T12:00:00Z"}],
                "count": 12,
            })}],
        }
        config_rows = {
            "client_config_source_map": {
                "selected_input_groups": [
                    {"name": "sensors", "returned_selected_count": 2, "selected": [
                        {"value": "SIM-1", "label": "Fictional west sensor"},
                        {"value": "SIM-2", "label": "Fictional east sensor"},
                    ]},
                    {"name": "overrideSwitch", "returned_selected_count": 1,
                     "selected": [{"value": "SIM-3",
                                   "label": "Fictional override"}]},
                ],
                "historical_configuration_proven_by_this_page": False,
            },
            "content": [{"type": "text", "text": json.dumps({
                "app": {"id": "SIM-APP"},
                "page": {"sections": []},
                "secret": "test-secret-must-not-leak",
            })}],
        }
        log_rows = {
            "content": [{"type": "text", "text": json.dumps({
                "mode": "past", "total": 5000, "matched": 2303, "count": 3,
                "entries": [
                    {"time": "2026-05-07 12:05:00.000", "message":
                     "test-secret-must-not-leak"},
                    {"time": "2026-05-07 12:04:00.000", "message":
                     "PRIVATE device reference; do not index"},
                    {"time": "2026-05-07 12:01:00.000", "message":
                     "another private event"},
                ],
            })}],
        }
        receipts = [
            {"name": "hub_list_device_events",
             "arguments": {"deviceId": "SIM-LAMP", "limit": 12},
             "success": True, "response": json.dumps(event_rows)},
            {"name": "hub_get_app_config",
             "arguments": {"appId": "SIM-APP"},
             "success": True, "response": json.dumps(config_rows)},
            {"name": "hub_get_logs",
             "arguments": {
                 "mode": "past", "since": "2026-05-07T12:00:00+0000",
                 "until": "2026-05-07T12:30:00+0000", "limit": 3},
             "success": True, "response": json.dumps(log_rows)},
        ]
        before = json.dumps(receipts, sort_keys=True)
        index = json.loads(final_claim_receipt_scope_index(receipts))
        self.assertEqual(json.dumps(receipts, sort_keys=True), before)
        items = index["indexed_receipts"]
        names = items[0]["event_names_in_returned_rows"]
        self.assertEqual(names["returned_event_name_counts"][0],
                         {"event_name": "command-off", "returned_count": 4})
        self.assertFalse(names["unreturned_events_proven_absent"])
        selected = items[1]["config_selected_inputs"]
        self.assertEqual(selected["selected_input_groups"][0]["returned_selected_count"], 2)
        self.assertEqual([r["value"] for r in
                          selected["selected_input_groups"][0]["selected"]],
                         ["SIM-1", "SIM-2"])
        self.assertFalse(selected["historical_configuration_verified"])
        logs = items[2]["returned_log_scope"]
        self.assertEqual(logs["matched_count"], 2303)
        self.assertEqual(logs["returned_entries"], 3)
        self.assertEqual(logs["oldest_returned_time_as_reported"],
                         "2026-05-07 12:01:00.000")
        self.assertEqual(logs["newest_returned_time_as_reported"],
                         "2026-05-07 12:05:00.000")
        self.assertFalse(logs["complete_requested_window_proven"])
        self.assertFalse(logs["time_zone_inferred_from_log_time"])
        flat = json.dumps(index)
        self.assertNotIn("test-secret-must-not-leak", flat)
        self.assertNotIn("PRIVATE device reference", flat)

    def test_malformed_or_failed_sources_cannot_promote_complete_coverage(self):
        records = [
            {"name": "hub_get_logs", "arguments": {"limit": 5},
             "success": False, "response": json.dumps({
                 "matched": 500, "count": 5, "entries": [{"time": "2026-04-01"}]})},
            {"name": "hub_get_logs", "arguments": {"limit": 5},
             "success": True, "response": "invalid JSON"},
            {"name": "hub_get_logs", "arguments": {"limit": 5},
             "success": True, "response": json.dumps({
                 "content": [{"type": "text", "text": json.dumps({
                     "matched": 7, "count": 0, "entries": [],
                 })}]})},
        ]
        index = json.loads(final_claim_receipt_scope_index(records))["indexed_receipts"]
        self.assertNotIn("returned_log_scope", index[0])
        self.assertNotIn("returned_log_scope", index[1])
        self.assertEqual(index[2]["returned_log_scope"]["returned_entries"], 0)
        self.assertEqual(index[2]["returned_log_scope"]["matched_count"], 7)
        self.assertFalse(index[2]["returned_log_scope"]["complete_requested_window_proven"])

    def test_failed_source_remains_visible_without_leaking_raw_error(self):
        receipts = [
            {"name": "hub_read_app_events",
             "arguments": {"appId": "LAB-APP", "hoursBack": 2},
             "success": False,
             "error": "MCP HTTP 503 source contained FAKE-PRIVATE-CREDENTIAL"},
            {"name": "hub_read_app_events",
             "arguments": {"appId": "LAB-APP", "hoursBack": 4},
             "success": False,
             "error": "Upstream response lost FAKE-PRIVATE-CREDENTIAL"},
            {"name": "hub_read_app_events",
             "arguments": {"appId": "LAB-APP", "hoursBack": 1},
             "success": True,
             "response": json.dumps({"content": [{"type": "text",
                 "text": json.dumps({"events": [], "count": 0})}]})},
        ]
        index = json.loads(final_claim_receipt_scope_index(receipts))
        self.assertEqual(index["failed_calls_in_indexed_receipts"], 2)
        self.assertEqual(index["indexed_receipts"][0]["http_status"], 503)
        self.assertEqual(index["indexed_receipts"][0]["read_error_class"], "http")
        self.assertFalse(index["indexed_receipts"][0]["no_matching_records_proven"])
        self.assertEqual(index["indexed_receipts"][1]["read_error_class"], "unknown")
        self.assertFalse(index["indexed_receipts"][1]["no_matching_records_proven"])
        self.assertNotIn("read_failed", index["indexed_receipts"][2])
        self.assertNotIn("FAKE-PRIVATE-CREDENTIAL", json.dumps(index))

    def test_empty_capability_inputs_are_bounded_and_current_only(self):
        source = {
            "client_config_source_map": {
                "selected_input_groups": [{"name": "configured",
                    "selected": [{"value": "LAB-1", "label": "Test light"}],
                    "returned_selected_count": 1}],
                "explicitly_empty_capability_inputs": [
                    {"name": "motionInput", "type": "capability.motionSensor",
                     "returned_value_kind": "null"},
                    {"name": "otherInput", "type": "capability.switch",
                     "returned_value_kind": "empty_list"},
                    {"name": "badType", "type": "html",
                     "returned_value_kind": "null"},
                ],
            },
            "content": [{"type": "text", "text": json.dumps({
                "app": {"id": "LAB-APP"},
                "page": {"sections": []},
            })}],
        }
        index = json.loads(final_claim_receipt_scope_index([{
            "name": "hub_get_app_config",
            "arguments": {"appId": "LAB-APP"},
            "success": True, "response": json.dumps(source),
        }]))["indexed_receipts"][0]["config_selected_inputs"]
        self.assertEqual(
            [(v["input_group"], v["returned_value_kind"])
             for v in index["explicitly_null_or_empty_capability_inputs"]],
            [("motionInput", "null"), ("otherInput", "empty_list")],
        )
        self.assertFalse(index["historical_configuration_verified"])
        self.assertFalse(index["event_specific_callback_verified"])

    def test_final_audit_preserves_failed_status_and_requests_concise_prose(self):
        for expected in (
            "A FAILED receipt is not an empty successful response.",
            "relevant read",
            "failed",
            "about 350–550 words",
            "contrary or",
            "no matching records",
            "There are NO tools",
        ):
            self.assertIn(expected, FINAL_CLAIM_AUDIT_PROMPT)
        self.assertNotIn("Bathroom Light", FINAL_CLAIM_AUDIT_PROMPT)
        self.assertNotIn("4013", FINAL_CLAIM_AUDIT_PROMPT)

    def test_final_audit_prompt_checks_all_returned_commands_and_selected_inputs(self):
        p = FINAL_CLAIM_AUDIT_PROMPT
        for text in (
            "EVERY relevant exact event name/count",
            "source-matched",
            "entries ACTUALLY returned",
            "selected input",
            "historical input values",
            "cannot prove historical",
            "internal reason",
            "There are NO tools",
        ):
            self.assertIn(text, p)
        self.assertNotIn("Hallway Light", p)
        self.assertNotIn("4012", p)


if __name__ == "__main__":
    unittest.main()

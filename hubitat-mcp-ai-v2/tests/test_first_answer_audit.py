"""V2 first-answer export auditing: privacy, anti-score fabrication and scope.

Synthetic fixture only: no Hubitat device/event data, model or network needed.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "tools" / "first_answer_audit.py"
SPEC = importlib.util.spec_from_file_location("v2_first_answer_audit_for_test", FILE)
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def fixture(*, prior=0):
    personal_value = "PRIVATE-FIXTURE-TARGET-DEVICE-222-SECRET"
    raw = {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "events": [{
                    "name": "sampleState", "value": personal_value,
                    "date": "2026-11-08T10:00:00+00:00",
                }]
            }),
        }],
        "client_event_source_scope": {
            "events_returned": 1,
            "oldest_returned_event": "2026-11-08T10:00:00+00:00",
            "newest_returned_event": "2026-11-08T10:00:00+00:00",
            "requested_lookback_hours": 48, "requested_limit": 50,
            "limit_reached": False,
            "can_infer_requested_window_fully_covered": False,
        }
    }
    return {
        "ui_version": "2.0.0-alpha.16",
        "model": "fixture-model",
        "request_id": "fixture-private-request-id",
        "question": "Tell me why " + personal_value + " went idle",
        "captured_at": "2026-11-08T10:04:00+00:00",
        "client_elapsed_ms": 14020,
        "server_elapsed_ms": 13980,
        "response": {
            "success": True, "answer": "Private statement about " + personal_value,
            "rounds": 3, "elapsed_ms": 13980,
            "prior_sources_indexed": prior, "prior_receipts_used": 1 if prior else 0,
            "leaf_schema_discoveries": 0,
            "tool_calls": [
                {
                    "name": "hub_list_device_events",
                    "arguments": {"deviceId": personal_value,
                                  "attribute": "thermostatOperatingState",
                                  "limit": 50, "hoursBack": 48},
                    "success": True, "result_kind": "tool_result",
                    "elapsed_ms": 350,
                    "response": json.dumps(raw),
                },
                {
                    "name": "hub_get_app_config",
                    "arguments": {"appId": "SENSITIVE_APP_7"},
                    "success": False, "result_kind": "contract_error",
                    "operation_executed": False,
                    "elapsed_ms": 9, "error": "PRIVATE-FIXTURE-SERVER-ERROR",
                    "response": '{"error":"PRIVATE-FIXTURE-SERVER-ERROR"}',
                },
            ],
        },
    }


class FirstAnswerAuditTests(unittest.TestCase):
    def test_private_export_never_leaks_answer_question_target_args_or_events(self):
        summary = audit.summarize([audit.audit_export(fixture())])
        report = json.dumps(summary)
        for forbidden in (
            "PRIVATE-FIXTURE-TARGET-DEVICE",
            "PRIVATE-FIXTURE-SERVER-ERROR",
            "SENSITIVE_APP_7",
            "fixture-private-request-id",
            "thermostatOperatingState",
            "2026-11-08T10:00:00",
            "Tell me why",
        ):
            self.assertNotIn(forbidden, report)
        self.assertEqual(summary["quality_status"], "not_measured")
        self.assertIsNone(summary["grounded_claim_rate"])
        self.assertIsNone(summary["useful_first_answer_rate"])
        self.assertIsNone(summary["unsupported_definitive_causal_claim_count"])
        self.assertEqual(summary["samples"], 1)
        self.assertEqual(summary["median_browser_seconds"], 14.02)

    def test_native_calls_counted_separately_from_local_schema_reads(self):
        inp = fixture()
        inp["response"]["tool_calls"].extend([
            {"name": "hub_read_devices", "arguments": {},
             "success": True, "result_kind": "tool_catalog",
             "operation_executed": False, "response": "{}"},
            {"name": "homebrain_read_prior_evidence",
             "arguments": {"receipt_id": "private-session-receipt"},
             "success": True, "result_kind": "prior_evidence_read",
             "operation_executed": False, "response": "{}"},
        ])
        result = audit.audit_export(inp)
        calls = result["native_tools"]
        self.assertEqual(calls["attempted"], 2)
        self.assertEqual(calls["successful"], 1)
        self.assertEqual(calls["failed"], 1)
        self.assertEqual(calls["locally_rejected"], 1)
        self.assertEqual(calls["known_nonexecuted_contract_errors"], 1)
        self.assertEqual(result["history_receipts"]["event_scope_receipts"], 1)
        self.assertEqual(result["history_receipts"]["event_rows_returned_total"], 1)
        self.assertEqual(result["history_receipts"]["all_history_windows_complete"],
                         "not_established")

    def test_context_carryover_is_not_a_fresh_isolated_first_question(self):
        self.assertEqual(
            audit.audit_export(fixture(prior=3))["source"]["first_answer_isolated"],
            "prior_session_context_present",
        )
        self.assertEqual(
            audit.audit_export(fixture())["source"]["first_answer_isolated"],
            "no_prior_context_reported_not_proof_of_new_session",
        )

    def test_limit_reached_and_upstream_truncation_are_flags_not_retention_cause(self):
        inp = fixture()
        body = json.loads(inp["response"]["tool_calls"][0]["response"])
        body["client_event_source_scope"].update({
            "events_returned": 50, "requested_limit": 50,
            "limit_reached": True, "upstream_truncated": True,
        })
        inp["response"]["tool_calls"][0]["response"] = json.dumps(body)
        record = audit.audit_export(inp)
        self.assertTrue(record["history_receipts"]["any_request_limit_reached"])
        self.assertTrue(record["history_receipts"]["any_upstream_truncation_flag"])
        self.assertEqual(record["history_receipts"]["all_history_windows_complete"],
                         "not_established")

    def test_failed_and_metadata_only_scope_payloads_do_not_count_as_history(self):
        inp = fixture()
        history = inp["response"]["tool_calls"][0]
        history["success"] = False
        inp["response"]["tool_calls"].append({
            "name": "hub_read_devices", "arguments": {},
            "success": True, "result_kind": "tool_catalog",
            "operation_executed": False, "response": history["response"],
        })
        result = audit.audit_export(inp)
        self.assertEqual(result["history_receipts"]["event_scope_receipts"], 0)
        self.assertEqual(result["history_receipts"]["event_rows_returned_total"], 0)
        self.assertEqual(
            result["history_receipts"]["excluded_non_success_event_scopes"], 2
        )
        self.assertEqual(result["history_receipts"]["unique_events_across_receipts"],
                         "not_established")

    def test_model_tool_and_argument_labels_cannot_escape_into_public_report(self):
        inp = fixture()
        inp["model"] = "PRIVATE-FIXTURE-MODEL-TOKEN"
        inp["ui_version"] = "PRIVATE-FIXTURE-BUILD-TOKEN"
        call = inp["response"]["tool_calls"][0]
        call["name"] = "PRIVATE-FIXTURE-TOOL-TOKEN"
        call["arguments"]["PRIVATE-FIXTURE-SCHEMA-KEY"] = "private-value"
        result = audit.audit_export(inp)
        report = json.dumps(audit.summarize([result]))
        self.assertNotIn("PRIVATE-FIXTURE", report)
        self.assertNotIn("private-value", report)
        self.assertEqual(result["build"]["version"], "unrecognised")
        self.assertEqual(len(result["build"]["model_sha256_prefix"]), 16)
        self.assertEqual(result["native_tools"]["distinct_model_selected_tool_names"], 2)
        self.assertEqual(
            len(result["native_tools"]["requested_argument_field_counts_per_call"]), 2
        )

    def test_native_flat_event_rows_counted_without_client_annotation(self):
        inp = fixture()
        source = inp["response"]["tool_calls"][0]
        source["arguments"]["limit"] = 2
        source["response"] = json.dumps({"content": [{
            "type": "text",
            "text": json.dumps({
                "device": "PRIVATE-DEVICE-ABC",
                "events": [
                    {"date": "2026-11-08T10:00:00Z", "value": "PRIVATE-EVENT-A"},
                    {"date": "2026-11-08T10:01:00Z", "value": "PRIVATE-EVENT-B"},
                ],
                "count": 999,
            }),
        }]})
        report = audit.audit_export(inp)
        history = report["history_receipts"]
        self.assertEqual(history["event_scope_receipts"], 1)
        self.assertEqual(history["scope_origin_native_event_rows"], 1)
        self.assertEqual(history["scope_origin_client_annotation"], 0)
        self.assertEqual(history["event_rows_returned_total"], 2)
        self.assertEqual(history["source_receipts_with_any_event_timestamp"], 1)
        self.assertTrue(history["any_request_limit_reached"])
        self.assertEqual(history["all_history_windows_complete"], "not_established")
        self.assertNotIn("PRIVATE-DEVICE", json.dumps(report))
        self.assertNotIn("PRIVATE-EVENT", json.dumps(report))

    def test_gateway_native_event_empty_history_preserves_unknown_coverage(self):
        inp = fixture()
        source = inp["response"]["tool_calls"][0]
        source["name"] = "hub_read_devices"
        source["arguments"] = {"tool": "hub_list_device_events",
                               "args": {"deviceId": "PRIVATE-DEVICE", "limit": 100}}
        source["response"] = json.dumps({"content": [{
            "type": "text",
            "text": json.dumps({"deviceId": "PRIVATE-DEVICE", "events": [], "count": 0}),
        }]})
        history = audit.audit_export(inp)["history_receipts"]
        self.assertEqual(history["event_scope_receipts"], 1)
        self.assertEqual(history["event_rows_returned_total"], 0)
        self.assertEqual(history["source_receipts_with_any_event_timestamp"], 0)
        self.assertFalse(history["any_request_limit_reached"])
        self.assertEqual(history["all_history_windows_complete"], "not_established")

    def test_generic_json_events_and_failed_native_result_do_not_create_evidence(self):
        inp = fixture()
        source = inp["response"]["tool_calls"][0]
        raw = json.dumps({"content": [{"type": "text", "text":
                         json.dumps({"device": "PRIVATE",
                                     "events": [{"date": "2026-11-08T12:00:00Z"}]})}]})
        source["response"] = raw
        source["name"] = "hub_list_devices"
        unrelated = audit.audit_export(inp)["history_receipts"]
        self.assertEqual(unrelated["event_scope_receipts"], 0)
        source["name"] = "hub_list_device_events"
        source["success"] = False
        failed = audit.audit_export(inp)["history_receipts"]
        self.assertEqual(failed["event_scope_receipts"], 0)
        self.assertEqual(failed["excluded_non_success_event_scopes"], 1)
        source["success"] = True
        source["operation_executed"] = False
        not_executed = audit.audit_export(inp)["history_receipts"]
        self.assertEqual(not_executed["event_rows_returned_total"], 0)
        source.pop("operation_executed")
        source["response"] = json.dumps({
            "isError": True, "content": json.loads(raw)["content"]
        })
        mcp_error = audit.audit_export(inp)["history_receipts"]
        self.assertEqual(mcp_error["event_rows_returned_total"], 0)

    def test_unknown_and_invalid_receipts_do_not_fabricate_success(self):
        inp = fixture()
        inp["response"]["tool_calls"][0]["success"] = None
        out = audit.audit_export(inp)
        self.assertEqual(out["native_tools"]["unknown_status"], 1)
        self.assertEqual(out["native_tools"]["successful"], 0)
        with self.assertRaises(audit.AuditInputError):
            audit.audit_export({"question": "x", "response": {"tool_calls": {}}})
        with self.assertRaises(audit.AuditInputError):
            audit.audit_export({**fixture(), "model": None})

    def test_many_models_are_descriptive_not_claims_of_quality(self):
        first = audit.audit_export(fixture())
        second_input = fixture()
        second_input["client_elapsed_ms"] = 20000
        second_input["model"] = "other-model"
        second = audit.audit_export(second_input)
        result = audit.summarize([first, second])
        self.assertEqual(result["samples"], 2)
        self.assertEqual(result["median_browser_seconds"], 17.01)
        self.assertEqual(result["p95_browser_seconds"], 20.0)
        self.assertEqual(result["quality_status"], "not_measured")

    def test_command_line_output_does_not_copy_private_source_text(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "private-input.json"
            out = Path(temp) / "audit-output.json"
            path.write_text(json.dumps(fixture()), encoding="utf-8")
            import subprocess
            run = subprocess.run(
                [sys.executable, str(FILE), str(path), "--output", str(out)],
                capture_output=True, text=True, timeout=15, check=False,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = out.read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE-FIXTURE", payload)
            self.assertNotIn("SENSITIVE_APP_7", payload)
            self.assertIn('"quality_status": "not_measured"', payload)
            self.assertEqual(json.loads(payload)["samples"], 1)


if __name__ == "__main__":
    unittest.main()

"""Synthetic-only tests for the optional mobile frozen-evidence evaluator."""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rootfs" / "app"))
from frozen_evaluation import (  # noqa: E402
    FrozenEvaluationError, freeze_capture, replay_frozen_capture,
)


def capture():
    return {"ui_version": "2.0.0-alpha.58",
            "question": "Why did the fictional hallway light report OFF?",
            "response": {"prior_receipts_used": 0,
                         "answer": "Earlier unverified model guess must not be reused.",
                         "tool_calls": [
                             {"name": "hub_list_device_events",
                              "arguments": {"deviceId": "FICTION-42", "attribute": "switch"},
                              "success": True, "result_kind": "tool_result",
                              "response": '{"events":[{"name":"switch","value":"off",'
                                          '"producedBy":{"name":"Fictional Reporter"}}],'
                                          '"count":1}'},
                             {"name": "hub_get_app_config",
                              "arguments": {"appId": 42}, "success": False,
                              "result_kind": "contract_error",
                              "operation_executed": False},
                         ]}}


class FakeModel:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    async def round(self, messages, tools, remaining):
        import copy
        self.calls.append((copy.deepcopy(messages), copy.deepcopy(tools)))
        return next(self.replies)


class FrozenEvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def test_three_model_rounds_with_same_original_receipts_no_tools(self):
        payload = freeze_capture(capture())
        model = FakeModel([
            {"content": "Fictional reporter saw off; no verified initiator."},
            {"content": "Original filtered sample does not prove command absence."},
            {"content": "State OFF observed. Cause unknown."},
        ])
        result = await replay_frozen_capture(model, payload)
        self.assertTrue(result["success"])
        self.assertEqual(result["mcp_calls_executed"], 0)
        self.assertEqual(result["hubitat_writes_executed"], 0)
        self.assertEqual(result["original_tool_receipts"], 2)
        self.assertEqual(result["failed_tool_receipts"], 1)
        self.assertEqual(result["model_rounds"], 3)
        self.assertEqual([row["stage"] for row in result["stages"]],
                         ["single_answer", "source_review", "source_review_and_audit"])
        self.assertEqual(len(model.calls), 3)
        self.assertTrue(all(tools == [] for _, tools in model.calls))
        self.assertEqual(model.calls[0][0], model.calls[1][0][:3])
        self.assertEqual(model.calls[0][0], model.calls[2][0][:3])
        self.assertNotIn("Earlier unverified model guess",
                         model.calls[0][0][2]["content"])
        self.assertIn("FICTION-42", model.calls[2][0][2]["content"])
        self.assertNotIn("FICTION-42", str(result))

    async def test_model_tool_request_rejected_without_execution(self):
        payload = freeze_capture(capture())
        model = FakeModel([{"content": "", "tool_calls": [
            {"function": {"name": "hub_get_logs", "arguments": "{}"}}]}])
        with self.assertRaises(FrozenEvaluationError):
            await replay_frozen_capture(model, payload)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(model.calls[0][1], [])

    async def test_no_partial_success_on_empty_second_response(self):
        model = FakeModel([{"content": "Fictional first answer"},
                           {"content": ""}])
        with self.assertRaises(FrozenEvaluationError):
            await replay_frozen_capture(model, freeze_capture(capture()))
        self.assertEqual(len(model.calls), 2)

    async def test_rejects_nonread_and_uncertain_execution(self):
        p = capture()
        p["response"]["tool_calls"][0]["name"] = "hub_manage_switch"
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)
        p = capture()
        p["response"]["tool_calls"][1].pop("operation_executed")
        p["response"]["tool_calls"][1]["result_kind"] = "tool_result"
        p["response"]["tool_calls"][1]["read_only"] = False
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)

    async def test_failed_local_monitor_validation_is_retained_as_failed_read(self):
        p = capture()
        p["response"]["tool_calls"].append({
            "name": "homebrain_read_device_monitor", "success": False,
            "arguments": {"mode": "history", "metric": "temperature",
                          "device_id": "FICTION-42", "range": "custom",
                          "start": "2026-11-11T20:00:00Z"},
            "error": "Custom history requires both start and end",
            "response": '{"error":"Custom history requires both start and end"}'
        })
        frozen = freeze_capture(p)
        self.assertEqual(frozen["failed_reads"], 2)
        self.assertEqual(frozen["successful_reads"], 1)
        self.assertIn("Custom history requires both start and end",
                      frozen["serialized"])
        model = FakeModel([{"content": "Initial"},
                           {"content": "Review"},
                           {"content": "Final"}])
        result = await replay_frozen_capture(model, frozen)
        self.assertEqual(result["failed_tool_receipts"], 2)
        self.assertEqual(result["mcp_calls_executed"], 0)
        self.assertEqual(len(model.calls), 3)

    async def test_monitor_exception_does_not_extend_to_write_like_modes_or_native_reads(self):
        p = capture()
        record = {"name": "homebrain_read_device_monitor", "success": False,
                  "arguments": {"mode": "mutate", "device_id": "FICTION-42"},
                  "error": "Rejected action"}
        p["response"]["tool_calls"].append(record)
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)
        record["arguments"]["mode"] = "history"
        record["read_only"] = False
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)
        record["read_only"] = True
        record["name"] = "hub_manage_rule"
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)

    async def test_failed_native_read_timeout_is_safe_to_replay_as_failed(self):
        p = capture()
        failed = {"name": "hub_list_devices",
                  "arguments": {"format": "detailed", "labelFilter": ""},
                  "success": False, "elapsed_ms": 25000,
                  "error": "MCP timed out",
                  "response": '{"error":"MCP timed out"}'}
        p["response"]["tool_calls"].insert(0, failed)
        frozen = freeze_capture(p)
        self.assertEqual(frozen["failed_reads"], 2)
        self.assertIn("MCP timed out", frozen["serialized"])
        self.assertEqual(frozen["records"][0]["success"], False)
        model = FakeModel([{"content": "Initial incomplete inventory"},
                           {"content": "Review: timeout is not no devices"},
                           {"content": "Final: inventory scope limited"}])
        result = await replay_frozen_capture(model, frozen)
        self.assertEqual(result["mcp_calls_executed"], 0)
        self.assertEqual(result["hubitat_writes_executed"], 0)
        self.assertEqual(result["failed_tool_receipts"], 2)
        self.assertEqual(len(model.calls), 3)

        failed["read_only"] = False
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)
        failed.pop("read_only")
        failed["name"] = "hub_manage_devices"
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)

    async def test_frozen_inventory_verification_question_without_live_review(self):
        p = capture()
        p["question"] = (
            "Which battery-powered devices currently have battery below 20%? "
            "Give their latest reading times and identify verified offline status. "
            "Do not change anything."
        )
        p["response"]["tool_calls"].insert(0, {
            "name": "hub_list_devices", "success": False,
            "arguments": {"format": "detailed"},
            "error": "MCP timed out",
            "response": '{"error":"MCP timed out"}'
        })
        frozen = freeze_capture(p)
        self.assertEqual(frozen["review_kind"], "source_verification")
        model = FakeModel([{"content": "Initial inventory answer"},
                           {"content": "Review device age and attribute times"},
                           {"content": "Verified status remains unknown"}])
        outcome = await replay_frozen_capture(model, frozen)
        self.assertEqual(outcome["mcp_calls_executed"], 0)
        self.assertEqual(outcome["failed_tool_receipts"], 2)
        self.assertEqual(outcome["model_rounds"], 3)
        p["question"] = "Turn on a fictional device"
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)
        p["question"] = "Tell me a joke"
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)

    async def test_api_rejects_missing_consent_and_missing_ui_header(self):
        from app import evaluation_replay, EvaluationReplayRequest
        from fastapi import HTTPException
        from starlette.requests import Request

        allowed = Request({"type": "http",
                           "headers": [(b"x-homebrain-request", b"1")]})
        blocked = Request({"type": "http", "headers": []})
        with self.assertRaises(HTTPException) as denied:
            await evaluation_replay(EvaluationReplayRequest(capture=capture()),
                                    allowed)
        self.assertEqual(denied.exception.status_code, 403)
        with self.assertRaises(HTTPException) as forbidden:
            await evaluation_replay(EvaluationReplayRequest(
                capture=capture(),
                send_private_evidence_to_configured_model=True), blocked)
        self.assertEqual(forbidden.exception.status_code, 403)

    async def test_api_can_run_with_existing_configured_model_without_mcp(self):
        from app import app, evaluation_replay, EvaluationReplayRequest
        from starlette.requests import Request

        previous = dict(app.state._state)
        try:
            model = FakeModel([{"content": "Unverified"},
                               {"content": "Still unverified"},
                               {"content": "Initiator unknown"}])
            app.state.model = model
            app.state.options = {
                "model_base_url": "https://ollama.com",
                "model_api_key": "fictional-placeholder",
                "investigation_timeout_seconds": 120,
            }
            app.state.configuration_error = None
            app.state.ask_lock = asyncio.Lock()
            request = Request({"type": "http",
                               "headers": [(b"x-homebrain-request", b"1")]})
            result = await evaluation_replay(EvaluationReplayRequest(
                capture=capture(),
                send_private_evidence_to_configured_model=True), request)
            self.assertEqual(result["mcp_calls_executed"], 0)
            self.assertEqual(len(model.calls), 3)
            self.assertEqual(result["model_rounds"], 3)
        finally:
            app.state._state.clear()
            app.state._state.update(previous)

    async def test_no_hidden_prior_receipts_and_replay_requires_evidence(self):
        p = capture()
        p["response"]["prior_receipts_used"] = 1
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)
        p = capture()
        p["response"]["tool_calls"] = []
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)
        p = capture()
        p["response"]["tool_calls"][0]["success"] = False
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)

    async def test_no_silent_context_truncation(self):
        p = capture()
        p["response"]["tool_calls"][0]["response"] = "x" * 300000
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)

    async def test_ui_contains_explicit_consent_and_no_auto_run(self):
        ui = (ROOT / "rootfs" / "app" / "ui.html").read_text(encoding="utf-8")
        self.assertIn("id=\"evaluationTab\"", ui)
        self.assertIn("id=\"evalConsent\"", ui)
        self.assertIn("id=\"evalRun\"", ui)
        self.assertIn("send_private_evidence_to_configured_model:true", ui)
        self.assertIn("technicalDetails", ui)
        self.assertIn("api/evaluation/replay", ui)
        self.assertIn('const UI_VERSION="2.0.0-alpha.84"', ui)
        self.assertIn("byId('evalConsent').checked=false", ui)


if __name__ == "__main__":
    unittest.main()

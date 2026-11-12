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
        with self.assertRaises(FrozenEvaluationError):
            freeze_capture(p)

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
        self.assertIn('const UI_VERSION="2.0.0-alpha.59"', ui)
        self.assertIn("byId('evalConsent').checked=false", ui)


if __name__ == "__main__":
    unittest.main()

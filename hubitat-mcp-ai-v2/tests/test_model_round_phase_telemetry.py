"""Fictional phase metrics regression and private offline performance profile.

No live hub, model provider, home data, HTTP calls, polling, writing or replay
of captured household evidence. These assert observational telemetry only.
"""
from __future__ import annotations

from copy import deepcopy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hubitat-mcp-ai-v2" / "rootfs" / "app"))

from agent import Agent
from first_answer_latency_profile import (
    ProfileError, main, profile_export, _phase,
)


def fake_export(new_phase=False):
    rows = [
        {"round": 1, "total_ms": 200, "prompt_eval_count": 150, "eval_count": 20},
        {"round": 2, "total_ms": 220, "prompt_eval_count": 190, "eval_count": 21},
        {"round": 3, "total_ms": 230, "prompt_eval_count": 240, "eval_count": 26},
        {"round": 4, "total_ms": 400, "prompt_eval_count": 280, "eval_count": 40},
        {"round": 5, "total_ms": 250, "prompt_eval_count": 310, "eval_count": 33},
    ]
    if new_phase:
        for n, row in enumerate(rows):
            row.update({
                "phase": (
                    "initial_investigation" if n <= 2 else
                    "source_review" if n == 3 else "final_claim_audit"
                ),
                "client_round_elapsed_ms": row["total_ms"] + 12,
                "source_receipts_before": 0 if n == 0 else 1,
                "tools_offered": 0 if n == 4 else 2,
                "model_messages_before": 2 + 2 * n,
            })
    return {
        "ui_version": "2.0.0-alpha.fixture",
        "model": "fixture",
        "question": "PRIVATE FIXTURE DEVICE DO NOT SERIALIZE",
        "client_elapsed_ms": 2900,
        "response": {
            "success": True, "rounds": 5,
            "model_round_metrics": rows,
            "answer_stage_trace": [
                {"stage": "pre_source_review", "after_model_round": 3,
                 "answer": "SECRET MODEL FIRST DRAFT"},
                {"stage": "pre_final_audit", "after_model_round": 4,
                 "answer": "SECRET MODEL AUDITED DRAFT"},
            ],
            "tool_calls": [
                {"name": "hub_list_device_events",
                 "arguments": {"deviceId": "SECRET-LAMP"},
                 "success": True, "elapsed_ms": 100,
                 "response": '{"secret":"PRIVATE NATIVE SOURCE"}'},
            ],
            "action_performance": {
                "model_input_tokens_reported": 1170,
                "model_output_tokens_reported": 140,
                "model_reported_ms": 1300,
            },
        },
    }


class OfflineProfilerTests(unittest.TestCase):
    def test_old_capture_derives_phases_with_honest_label(self):
        doc = fake_export()
        source = json.dumps(doc).encode()
        before = deepcopy(doc)
        result = profile_export(doc, source)
        self.assertEqual(result["first_review_draft_after_round"], 3)
        self.assertEqual([r["phase"] for r in result["model_rounds"]],
                         ["initial_investigation"] * 3 +
                         ["source_review", "final_claim_audit"])
        self.assertEqual(
            {r["phase_attribution"] for r in result["model_rounds"]},
            {"derived_from_stage_trace"})
        self.assertEqual(result["provider_reported_input_tokens_sum"], 1170)
        self.assertEqual(result["provider_reported_output_tokens_sum"], 140)
        self.assertEqual(result["provider_reported_ms_sum"], 1300)
        self.assertEqual(result["source_tool_attempts"], 1)
        self.assertEqual(result["source_tool_success_count"], 1)
        self.assertEqual(result["sum_reported_tool_attempt_ms"], 100)
        self.assertIsNone(result["quality_score"])
        self.assertFalse(result["quality_reviewed"])
        self.assertEqual(doc, before)

    def test_new_capture_records_actual_phase_and_round_counts(self):
        doc = fake_export(new_phase=True)
        out = profile_export(doc, json.dumps(doc).encode())
        self.assertTrue(all(r["phase_attribution"] == "recorded_by_agent"
                            for r in out["model_rounds"]))
        self.assertEqual(out["model_rounds"][-1]["tools_offered"], 0)
        self.assertEqual(out["model_rounds"][3]["source_receipts_before"], 1)
        self.assertEqual(out["phase_totals"]["source_review"]["rounds"], 1)
        self.assertEqual(out["phase_totals"]["final_claim_audit"]["rounds"], 1)
        self.assertEqual(out["phase_totals"]["initial_investigation"]["rounds"], 3)

    def test_unknown_or_malformed_phases_never_fabricate(self):
        self.assertEqual(_phase(3, {}, {}), ("unknown", "not_established"))
        for bad in ([], None, {"response": {}}, {
            "response": {"model_round_metrics": None, "tool_calls": []},
        }):
            with self.assertRaises(ProfileError):
                profile_export(bad, b"{}")
        d = fake_export()
        d["response"]["model_round_metrics"][1]["round"] = 1
        with self.assertRaises(ProfileError):
            profile_export(d, b"{}")
        d = fake_export()
        d["response"]["rounds"] = 4
        with self.assertRaises(ProfileError):
            profile_export(d, b"{}")

    def test_private_output_create_only(self):
        import tempfile
        from io import StringIO
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "private-input.json"
            target = Path(tmp) / "private-round-profile.json"
            src.write_text(json.dumps(fake_export()), encoding="utf-8")
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(main([str(src), "--output", str(target)]), 0)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            text = target.read_text(encoding="utf-8")
            self.assertNotIn("SECRET-LAMP", text)
            self.assertNotIn("PRIVATE NATIVE SOURCE", text)
            self.assertNotIn("SECRET MODEL", text)
            self.assertNotIn("PRIVATE FIXTURE DEVICE", text)
            self.assertIn("quality_status", text)
            self.assertIn("No factual-quality improvement", out.getvalue())
            with self.assertRaises(SystemExit):
                main([str(src), "--output", str(target)])

    def test_tool_failure_is_not_counted_as_success_and_missing_counters_unknown(self):
        d = fake_export()
        d["response"]["tool_calls"][0]["success"] = False
        d["response"]["model_round_metrics"][2].pop("prompt_eval_count")
        out = profile_export(d, json.dumps(d).encode())
        self.assertEqual(out["source_tool_success_count"], 0)
        self.assertEqual(out["model_rounds"][2]["prompt_tokens"], None)
        self.assertEqual(out["quality_score"], None)


class FictionalMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self, refresh=False):
        return [{"name": "hub_list_device_events", "inputSchema": {
            "type": "object", "properties": {"deviceId": {"type": "string"}}
        }}]

    async def call(self, name, args):
        self.calls.append((name, args))
        if name != "hub_list_device_events":
            raise AssertionError("Only original fictional read may execute")
        return {"content": [{"type": "text", "text": json.dumps({
            "source": "device", "deviceId": "FX-LAMP", "device": "Fixture Lamp",
            "events": [{"name": "switch", "value": "off",
                        "date": "2030-11-16T19:22:57+00:00"}],
        })}]}


def scripted(content=None, call=None, n=1):
    data = {"content": content or "", "_inference_metrics": {
        "provider_reported_model": "fictional",
        "prompt_eval_count": 100 * n, "eval_count": 10 * n,
        "total_ms": 50 * n,
    }}
    if call is not None:
        data["tool_calls"] = [{"function": {
            "name": call, "arguments": {"deviceId": "FX-LAMP"}}}]
    return data


class ScriptedAgent(Agent):
    def __init__(self, *rounds):
        super().__init__("http://127.0.0.1:11434", "fixture", "", 20)
        self.replies = list(rounds)

    async def round(self, messages, tools, remaining):
        if not self.replies:
            raise AssertionError("Unexpected model round")
        return self.replies.pop(0)


class RuntimePhaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_phase_tags_follow_existing_review_and_final_claim_audit(self):
        hub = FictionalMCP()
        model = ScriptedAgent(
            scripted(call="hub_list_device_events", n=1),
            scripted("Device reported OFF, cause unknown.", n=2),
            scripted("Device reported OFF; the initiator is unverified.", n=3),
            scripted("Device reported OFF; the initiator is unknown.", n=4),
        )
        try:
            result = await model.answer(
                "Why did Fixture Lamp switch OFF? Do not change anything.",
                [], hub, 90,
                enable_causal_follow_through=False,
            )
        finally:
            await model.close()
        metrics = result["model_round_metrics"]
        self.assertEqual(result["rounds"], 4)
        self.assertEqual([m["phase"] for m in metrics],
                         ["initial_investigation", "initial_investigation",
                          "source_review", "final_claim_audit"])
        self.assertEqual([m["source_receipts_before"] for m in metrics],
                         [0, 1, 1, 1])
        self.assertEqual([m["tools_offered"] for m in metrics][-1], 0)
        self.assertTrue(all(m["client_round_elapsed_ms"] >= 0 for m in metrics))
        self.assertEqual(len(hub.calls), 1)
        self.assertEqual(result["answer_fallback_status"], "not_used")
        self.assertEqual(result["final_claim_audit_status"], "completed")
        self.assertFalse(result["action_lifecycle"]["native_write_submitted"])


if __name__ == "__main__":
    unittest.main()

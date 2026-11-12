"""Fictional frozen-receipt model replay tests: no network, no real devices."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "evaluation" / "frozen_model_replay.py"
spec = importlib.util.spec_from_file_location("frozen_model_replay", SCRIPT)
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def fixture():
    return {"schema": replay.PACKET_SCHEMA,
            "question": "Why did the fictional table lamp report OFF? Do not change anything.",
            "tool_calls": [
                {"name": "hub_list_device_events",
                 "arguments": {"deviceId": "FICTIONAL-99", "attribute": "switch"},
                 "success": True, "result_kind": "tool_result",
                 "response": '{"events":[{"name":"switch","value":"off"}],"count":1}'},
                {"name": "hub_get_app_config",
                 "arguments": {"appId": 42}, "success": False,
                 "operation_executed": False, "result_kind": "contract_error"},
            ]}


class FrozenReplayTests(unittest.TestCase):
    def test_two_conditions_share_initial_draft_and_exact_receipts(self):
        packet = replay.frozen_packet(fixture())
        calls = []
        answers = iter([
            {"content": "Fictional bridge reports off; no issuer verified."},
            {"content": "The returned sample cannot establish who initiated it."},
            {"content": "Cause remains unverified; one OFF report returned."},
        ])
        def model(messages):
            calls.append(json.loads(json.dumps(messages)))
            return next(answers)
        result = replay.replay(packet, model, system="FICTIONAL SKILL")
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][0]["role"], "system")
        self.assertEqual(calls[0], calls[1][:len(calls[0])])
        self.assertEqual(calls[0], calls[2][:len(calls[0])])
        self.assertIn("ORIGINAL FROZEN MCP RECEIPTS", calls[0][2]["content"])
        self.assertIn("SOURCE", calls[1][-1]["content"].upper())
        self.assertIn("Returned-receipt scope index", calls[2][-1]["content"])
        self.assertEqual([stage["stage"] for stage in result["stages"]],
                         ["single_answer", "source_review", "source_review_and_audit"])
        self.assertTrue(result["no_mcp_calls"])

    def test_rejects_non_read_or_uncertain_failed_receipts(self):
        payload = fixture()
        payload["tool_calls"][0]["name"] = "hub_manage_device"
        with self.assertRaises(replay.ReplayError):
            replay.frozen_packet(payload)
        payload = fixture()
        payload["tool_calls"][1].pop("operation_executed")
        payload["tool_calls"][1]["result_kind"] = "tool_result"
        payload["tool_calls"][1]["read_only"] = False
        with self.assertRaises(replay.ReplayError):
            replay.frozen_packet(payload)

    def test_failed_reserved_monitor_read_is_preserved_not_promoted(self):
        payload = fixture()
        payload["tool_calls"].append({
            "name": "homebrain_read_device_monitor",
            "success": False,
            "arguments": {"mode": "history", "metric": "temperature",
                          "range": "custom", "start": "2026-11-11T20:00:00Z"},
            "error": "Both start and end are required"
        })
        result = replay.frozen_packet(payload)
        self.assertEqual(len(result["tool_calls"]), 3)
        self.assertFalse(result["tool_calls"][-1]["success"])
        self.assertIn("Both start and end are required", result["serialized_receipts"])
        payload["tool_calls"][-1]["arguments"]["mode"] = "switch"
        with self.assertRaises(replay.ReplayError):
            replay.frozen_packet(payload)
        payload["tool_calls"][-1]["arguments"]["mode"] = "history"
        payload["tool_calls"][-1]["name"] = "hub_manage_rule"
        with self.assertRaises(replay.ReplayError):
            replay.frozen_packet(payload)

    def test_failed_native_read_timeout_retained_without_untrusted_writes(self):
        payload = fixture()
        failure = {"name": "hub_list_devices",
                   "arguments": {"format": "detailed", "labelFilter": ""},
                   "success": False, "elapsed_ms": 25000,
                   "error": "MCP timed out", "response": '{"error":"MCP timed out"}'}
        payload["tool_calls"].insert(0, failure)
        data = replay.frozen_packet(payload)
        self.assertFalse(data["tool_calls"][0]["success"])
        self.assertIn("MCP timed out", data["serialized_receipts"])
        failure["read_only"] = False
        with self.assertRaises(replay.ReplayError):
            replay.frozen_packet(payload)
        failure.pop("read_only")
        failure["name"] = "hub_manage_rule"
        with self.assertRaises(replay.ReplayError):
            replay.frozen_packet(payload)

    def test_technical_json_export_supported_without_using_prior_answers(self):
        f = fixture()
        payload = {"question": f["question"],
                   "response": {"tool_calls": f["tool_calls"], "prior_receipts_used": 0,
                                "answer": "PRIVATE prior model opinion"}}
        p = replay.frozen_packet(payload)
        self.assertNotIn("PRIVATE prior model opinion", p["serialized_receipts"])
        payload["response"]["prior_receipts_used"] = 1
        with self.assertRaises(replay.ReplayError):
            replay.frozen_packet(payload)

    def test_reject_unsolicited_model_tool_calls(self):
        with self.assertRaises(replay.ReplayError):
            replay.extract_answer({"content": "Not executed", "tool_calls": [
                {"function": {"name": "hub_get_logs"}}]})

    def test_local_endpoint_default_and_remote_consent(self):
        self.assertEqual(replay.model_endpoint("http://127.0.0.1:11434"),
                         "http://127.0.0.1:11434/api/chat")
        for url in ("http://example.org", "https://example.org",
                    "http://127.0.0.1:11434/user:pass", "http://user:pass@localhost:11434"):
            with self.assertRaises(replay.ReplayError):
                replay.model_endpoint(url)
        self.assertEqual(replay.model_endpoint("https://example.org", True),
                         "https://example.org/api/chat")

    def test_blinding_and_private_reuse_refusal(self):
        f = fixture()
        p = replay.frozen_packet(f)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "case.json"
            source.write_text(json.dumps(f))
            stages = {
                "stages": [
                    {"stage": "single_answer", "answer": "PRIVATE INITIAL",
                     "elapsed_ms": 100, "model_rounds": 1},
                    {"stage": "source_review", "answer": "PRIVATE MID"},
                    {"stage": "source_review_and_audit", "answer": "PRIVATE FINAL",
                     "elapsed_ms": 300, "model_rounds": 3},
                ],
                "no_mcp_calls": True, "evidence_identical_for_all_stages": True,
            }
            out = Path(temp) / "private-output"
            summary = replay.save_blinded(out, source, "fictional", stages)
            self.assertEqual(summary["blinded_answer_files"], 2)
            a = (out / "blinded" / "A.txt").read_text().strip()
            b = (out / "blinded" / "B.txt").read_text().strip()
            self.assertEqual(set((a, b)), {"PRIVATE INITIAL", "PRIVATE FINAL"})
            self.assertNotIn("mode", (out / "blinded" / "A.txt").read_text())
            mapping = json.loads((out / "PRIVATE_assignment.json").read_text())
            self.assertEqual({arm["mode"] for arm in mapping["arms"]},
                             {"single_answer", "source_review_and_audit"})
            with self.assertRaises(replay.ReplayError):
                replay.save_blinded(out, source, "fictional", stages)

    def test_prevents_context_truncation(self):
        f = fixture()
        f["tool_calls"][0]["response"] = "x" * (replay.MAX_CONTEXT_CHARS + 5)
        with self.assertRaises(replay.ReplayError):
            replay.frozen_packet(f)


if __name__ == "__main__":
    unittest.main()

"""Synthetic, no-network tests of explicit opt-in Ollama A/B runner."""
from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
import sys
sys.path.insert(0, str(TOOLS))

import fixed_source_benchmark as bench
import run_fixed_source_pairs_ollama as runner


def mcp(payload):
    return json.dumps({"content": [{"type": "text", "text": json.dumps(payload)}]})


def synthetic():
    device = "SYNTHETIC-SECRET-DEVICE-999"
    return {
        "ui_version": "2.0.0-alpha.18",
        "model": "synthetic",
        "question": "Turn SYNTHETIC-SECRET-DEVICE-999 on",
        "response": {
            "prior_sources_indexed": 0,
            "prior_receipts_used": 0,
            "answer": "PRIVATE-ORIGINAL-ANSWER",
            "tool_calls": [
                {"name": "hub_call_device_command",
                 "arguments": {"deviceId": device, "command": "on"},
                 "success": True,
                 "response": mcp({"success": True, "command": "on",
                                  "state": {"switch": {"value": "off"}}})},
                {"name": "hub_get_device_attribute",
                 "arguments": {"deviceId": device, "attribute": "switch"},
                 "success": True,
                 "response": mcp({"attribute": "switch", "value": "on"})},
            ],
        },
    }


def args(folder, **changes):
    data = dict(
        directory=folder, model="gemma4:31b-cloud",
        endpoint="http://127.0.0.1:11434/api/chat",
        seed=42, timeout=30, max_pairs=1, case=None,
        run=False, acknowledge_private_mcp_data=False,
        allow_cloud_model=False, allow_remote_endpoint=False,
    )
    data.update(changes)
    return argparse.Namespace(**data)


def prepare(temp):
    root = Path(temp)
    source = root / "source.json"
    source.write_text(json.dumps(synthetic()), encoding="utf-8")
    folder = root / "PRIVATE"
    bench.prepare([source], folder, 42)
    return folder


class FakeResponse:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def read(self):
        return json.dumps({"message": {"role": "assistant",
                                      "content": "Synthetic model text only."}}).encode()


class OllamaPairRunnerTests(unittest.TestCase):
    def test_dry_run_never_calls_network(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = prepare(temp)
            with patch.object(runner, "urlopen", side_effect=AssertionError("network")):
                result = runner.execute(args(folder))
            self.assertEqual(result["mode"], "dry_run")
            self.assertEqual(result["source_pairs_verified"], 1)
            self.assertEqual(result["model_requests_pending"], 2)
            self.assertEqual(result["model_requests_completed_this_run"], 0)
            self.assertFalse(list((folder / "answers").glob("*.txt")))

    def test_actual_run_requires_source_consent_and_cloud_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = prepare(temp)
            with patch.object(runner, "urlopen", side_effect=AssertionError("network")):
                with self.assertRaisesRegex(ValueError, "acknowledge"):
                    runner.execute(args(folder, run=True))
                with self.assertRaisesRegex(ValueError, "Cloud"):
                    runner.execute(args(folder, run=True,
                                        acknowledge_private_mcp_data=True))

    def test_default_endpoint_is_loopback_only(self):
        runner._validate_endpoint("http://localhost:11434/api/chat", False)
        runner._validate_endpoint("http://127.0.0.1:11434/api/chat", False)
        runner._validate_endpoint("http://[::1]:11434/api/chat", False)
        for bad in (
            "http://192.0.2.1:11434/api/chat",
            "http://model.example/api/chat",
            "https://user:password@host.example/api/chat",
            "http://127.0.0.1:11434/api/chat?token=secret",
            "http://127.0.0.1:11434/api/generate",
        ):
            with self.assertRaises(ValueError):
                runner._validate_endpoint(bad, False)
        with self.assertRaises(ValueError):
            runner._validate_endpoint("http://model.example/api/chat", True)
        runner._validate_endpoint("https://model.example/api/chat", True)

    def test_only_two_same_model_tool_free_requests_and_answer_files(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = prepare(temp)
            submitted = []
            def fake_urlopen(request, timeout):
                body = json.loads(request.data)
                submitted.append(body)
                self.assertNotIn("tools", body)
                self.assertEqual(body["model"], "gemma4:31b-cloud")
                self.assertEqual(body["stream"], False)
                self.assertEqual(body["options"]["temperature"], 0)
                self.assertEqual(body["messages"][0]["role"], "system")
                self.assertIn("SYNTHETIC-SECRET-DEVICE-999",
                              body["messages"][1]["content"])
                return FakeResponse()
            with patch.object(runner, "urlopen", side_effect=fake_urlopen):
                result = runner.execute(args(folder, run=True,
                    acknowledge_private_mcp_data=True, allow_cloud_model=True))
            self.assertEqual(len(submitted), 2)
            self.assertEqual(result["model_requests_completed_this_run"], 2)
            answers = [folder / "answers" / f"case-001-{label}.txt"
                       for label in ("A", "B")]
            self.assertTrue(all(x.read_text() == "Synthetic model text only."
                                for x in answers))
            metadata = json.loads((folder / "blind_ratings.json").read_text())
            self.assertTrue(all(metadata["cases"]["case-001"][label]["elapsed_ms"] >= 0
                                for label in ("A", "B")))
            self.assertTrue(all(metadata["cases"]["case-001"][label]["ratings"]
                                ["factual_grounding"] is None for label in ("A", "B")))
            with patch.object(runner, "urlopen", side_effect=AssertionError("rerun")):
                rerun = runner.execute(args(folder, run=True,
                    acknowledge_private_mcp_data=True, allow_cloud_model=True))
            self.assertEqual(rerun["model_requests_pending"], 0)

    def test_response_with_tool_calls_refused(self):
        class BadResponse(FakeResponse):
            def read(self):
                return json.dumps({"message": {
                    "content": "Need tools", "tool_calls": [{"function": {}}]}}).encode()
        with patch.object(runner, "urlopen", return_value=BadResponse()):
            with self.assertRaisesRegex(ValueError, "standalone"):
                runner._model_answer("local", "http://127.0.0.1:11434/api/chat",
                                     {"instructions": "Private",
                                      "recorded_user_question": "Test",
                                      "native_tool_receipts": []}, 5, 42)

    def test_frozen_source_tampering_stops_before_model(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = prepare(temp)
            path = folder / "case-001-A.json"
            bundle = json.loads(path.read_text())
            bundle["native_tool_receipts"][0]["success"] = False
            path.write_text(json.dumps(bundle))
            with patch.object(runner, "urlopen", side_effect=AssertionError("network")):
                with self.assertRaisesRegex(ValueError, "SHA"):
                    runner.execute(args(folder, run=True,
                                        acknowledge_private_mcp_data=True,
                                        allow_cloud_model=True))

    def test_case_selection_rejects_unknown_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = prepare(temp)
            with patch.object(runner, "urlopen", side_effect=AssertionError("network")):
                with self.assertRaises(ValueError):
                    runner.execute(args(folder, run=True, case=["case-999"],
                                        acknowledge_private_mcp_data=True,
                                        allow_cloud_model=True))

    def test_model_error_is_scrubbed_without_sending_duplicate_commands(self):
        from urllib.error import URLError
        with tempfile.TemporaryDirectory() as temp:
            folder = prepare(temp)
            with patch.object(runner, "urlopen",
                              side_effect=URLError("PRIVATE-RAW-SERVER-ERROR")):
                with self.assertRaises(ValueError) as cm:
                    runner.execute(args(folder, run=True,
                                        acknowledge_private_mcp_data=True,
                                        allow_cloud_model=True))
            self.assertNotIn("PRIVATE-RAW-SERVER-ERROR", str(cm.exception))
            self.assertFalse(list((folder / "answers").glob("*.txt")))


if __name__ == "__main__":
    unittest.main()

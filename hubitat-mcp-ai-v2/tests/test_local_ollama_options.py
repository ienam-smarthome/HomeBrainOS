"""Fictional alpha.87 LAN Ollama option, timing and Supervisor schema tests.

No live model, Hubitat, OpenRouter, HA Supervisor or native writes.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent
from model_routing import RoutedAgent, is_lan_ollama


class FakeOllamaResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "message": {"role": "assistant", "content": "OK"},
            "total_duration": 8761216200,
            "load_duration": 8343065000,
            "prompt_eval_count": 15,
            "prompt_eval_duration": 352887000,
            "eval_count": 2,
            "eval_duration": 58432000,
        }


class LocalEndpointClassificationTests(unittest.TestCase):
    def test_private_lan_and_local_hostnames(self):
        for url in ("http://192.168.1.20:11434", "http://10.42.1.9:11434",
                    "http://localhost:11434", "http://gmktec.local:11434",
                    "http://homebrain.home.arpa:11434"):
            with self.subTest(url=url):
                self.assertTrue(is_lan_ollama(url))

    def test_public_cloud_endpoints_do_not_receive_local_tuning(self):
        for url in ("https://ollama.com", "https://openrouter.ai",
                    "https://models.example.com"):
            with self.subTest(url=url):
                self.assertFalse(is_lan_ollama(url))

    def test_invalid_local_context_or_thinking_settings_are_refused(self):
        for ctx in (4095, 32769, True, 8192.5):
            with self.subTest(ctx=ctx), self.assertRaises(ValueError):
                RoutedAgent("http://192.168.1.20:11434", "qwen3.5:4b",
                            "", 120, local_ollama_num_ctx=ctx)
        with self.assertRaises(ValueError):
            RoutedAgent("http://192.168.1.20:11434", "qwen3.5:4b",
                        "", 120, local_ollama_think="false")


class LocalInferenceTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_lan_request_matches_successful_windows_test(self):
        agent = RoutedAgent(
            "http://192.168.1.20:11434", "qwen3.5:4b", "", 120,
            local_ollama_think=False, local_ollama_num_ctx=8192,
        )
        tools = [{"type": "function", "function": {"name": "hub_list_devices"}}]
        messages = [{"role": "user", "content": "read only fictional check"}]
        try:
            with patch.object(agent.client, "post",
                              AsyncMock(return_value=FakeOllamaResponse())) as post:
                reply = await agent.round(messages, tools, 120)
            self.assertEqual(reply["content"], "OK")
            self.assertEqual(reply["_inference_metrics"]["total_ms"], 8761.22)
            self.assertEqual(reply["_inference_metrics"]["load_ms"], 8343.06)
            self.assertEqual(reply["_inference_metrics"]["prompt_eval_count"], 15)
            request = post.call_args.kwargs["json"]
            self.assertEqual(request["model"], "qwen3.5:4b")
            self.assertEqual(request["think"], False)
            self.assertEqual(request["options"], {"num_ctx": 8192})
            self.assertEqual(request["tools"], tools)
            self.assertEqual(request["messages"], messages)
            self.assertEqual(reply.get("tool_calls"), None)
            status = agent.route_status()
            self.assertTrue(status["local_ollama_options_active"])
            self.assertFalse(status["local_think_enabled"])
            self.assertEqual(status["local_num_ctx"], 8192)
            self.assertEqual(status["last_attempt"]["provider"], "local")
        finally:
            await agent.close()

    async def test_local_tuning_is_configurable_without_new_tool_calls(self):
        agent = RoutedAgent(
            "http://192.168.1.23:11434", "fictional:4b", "", 120,
            local_ollama_think=True, local_ollama_num_ctx=16384,
        )
        try:
            with patch.object(agent.client, "post",
                              AsyncMock(return_value=FakeOllamaResponse())) as post:
                await agent.round([{"role": "user", "content": "test"}], [], 30)
            data = post.call_args.kwargs["json"]
            self.assertIs(data["think"], True)
            self.assertEqual(data["options"], {"num_ctx": 16384})
            self.assertEqual(data["tools"], [])
        finally:
            await agent.close()

    async def test_legacy_ollama_cloud_does_not_get_local_only_fields(self):
        agent = RoutedAgent(
            "https://ollama.com", "gemma4:31b-cloud", "fictional-key", 120,
            local_ollama_think=False, local_ollama_num_ctx=8192,
        )
        try:
            with patch.object(agent.client, "post",
                              AsyncMock(return_value=FakeOllamaResponse())) as post:
                await agent.round([{"role": "user", "content": "test"}], [], 30)
            data = post.call_args.kwargs["json"]
            self.assertNotIn("think", data)
            self.assertNotIn("options", data)
            self.assertFalse(agent.route_status()["local_ollama_options_active"])
        finally:
            await agent.close()

    async def test_local_generation_timeout_is_not_cloud_failover(self):
        agent = RoutedAgent(
            "http://192.168.1.20:11434", "qwen3.5:4b", "", 120,
        )
        try:
            with patch.object(agent.client, "post",
                              AsyncMock(side_effect=asyncio.TimeoutError)):
                with self.assertRaisesRegex(RuntimeError, "Model request timed out"):
                    await agent.round([{"role": "user", "content": "slow"}], [], 120)
            status = agent.route_status()["last_attempt"]
            self.assertIsNone(status["provider"])
            self.assertEqual(status["attempted_provider"], "local")
            self.assertEqual(status["status"], "no_completed_model_round")
            self.assertFalse(status["cloud_fallback_used"])
        finally:
            await agent.close()


class FictionalMetricsMCP:
    async def list_tools(self, refresh=False):
        return []


class ModelAnswerMetricTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_answer_records_only_numerical_round_metrics(self):
        agent = Agent("http://localhost:11434", "fixture", "", 120)
        try:
            with patch.object(agent, "round", AsyncMock(return_value={
                "role": "assistant", "content": "Synthetic status only.",
                "tool_calls": [],
                "_inference_metrics": {
                    "total_ms": 870.3, "prompt_eval_count": 1400,
                    "eval_count": 5,
                },
            })) as round_call:
                answer = await agent.answer(
                    "Show current status", [], FictionalMetricsMCP(), 60
                )
            self.assertTrue(answer["success"])
            self.assertEqual(round_call.await_count, 1)
            self.assertEqual(answer["tool_calls"], [])
            self.assertEqual(answer["model_round_metrics"], [{
                "round": 1, "total_ms": 870.3,
                "prompt_eval_count": 1400, "eval_count": 5,
            }])
        finally:
            await agent.close()


class SupervisorOptionalOptionsTests(unittest.TestCase):
    def test_optional_credentials_not_required_by_default_options(self):
        config = (Path(__file__).resolve().parents[1] / "config.yaml").read_text()
        defaults = config.split("\noptions:\n", 1)[1].split("\nschema:\n", 1)[0]
        schema = config.split("\nschema:\n", 1)[1]
        for key in (
            "model_api_key", "cloud_fallback_api_key", "hubitat_mcp_token",
            "hubitat_mcp_url", "device_monitor_access_token",
            "device_monitor_api_base", "ha_tts_notify_service",
        ):
            with self.subTest(option=key):
                self.assertNotIn("\n  " + key + ":", defaults)
                self.assertIn("\n  " + key + ":", schema)
        self.assertIn("local_ollama_think: false", defaults)
        self.assertIn("local_ollama_num_ctx: 8192", defaults)
        self.assertIn("local_ollama_think: bool", schema)
        self.assertIn("local_ollama_num_ctx: int(4096,32768)", schema)


if __name__ == "__main__":
    unittest.main()

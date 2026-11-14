"""Fictional Ollama Cloud paid-provider tests; no real network, Hubitat or spend."""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from model_routing import CloudAgent, probe_cloud_tool_call
from ollama_cloud import OllamaCloudChat, ollama_cloud_model_name


class FakeReply:
    def __init__(self, body=None, status=200):
        self.body = body or {"model": "nemotron-3-super", "message": {
            "role": "assistant", "content": "I can inspect the fixture.",
            "tool_calls": [{"function": {"name": "fixture_read_state",
                         "arguments": {"fixture_id": "DEMO_SWITCH"}}}],
        }}
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            import httpx
            req = httpx.Request("POST", "https://ollama.com/api/chat")
            raise httpx.HTTPStatusError(
                "Sensitive response should never be exposed",
                request=req, response=httpx.Response(self.status, request=req)
            )

    def json(self):
        return self.body


class ProviderSelectionTests(unittest.TestCase):
    def test_ollama_model_id_is_fixed_and_no_url(self):
        for name in ("nemotron-3-super", "mimo-v2.6-flash", "gemma4:31b"):
            self.assertEqual(ollama_cloud_model_name(name), name)
        for bad in ("", "https://ollama.com/api/chat", "openrouter/free",
                    "../foo", " model space ", "*", "a?b"):
            with self.subTest(model=bad), self.assertRaises(ValueError):
                ollama_cloud_model_name(bad)

    def test_free_mode_never_uses_paid_provider_or_ollama_api_key(self):
        agent = CloudAgent(
            mode="free", paid_provider="ollama", api_key="fictional-openrouter",
            ollama_model="nemotron-3-super", ollama_api_key="",
            paid_consent=False,
        )
        try:
            self.assertEqual(agent.provider, "openrouter")
            self.assertEqual(agent.model, "openrouter/free")
            self.assertEqual(agent.route_status()["primary"], "openrouter")
            self.assertFalse(agent.route_status()["paid_mode"])
            self.assertFalse(agent.route_status()["automatic_paid_fallback"])
        finally:
            asyncio.run(agent.close())

    def test_ollama_requires_paid_mode_explicit_consent_and_own_key(self):
        with self.assertRaisesRegex(ValueError, "explicit"):
            CloudAgent(mode="paid", paid_provider="ollama",
                       ollama_api_key="test", paid_consent=False)
        with self.assertRaisesRegex(ValueError, "Ollama Cloud API key"):
            CloudAgent(mode="paid", paid_provider="ollama",
                       api_key="openrouter-does-not-count", paid_consent=True)
        with self.assertRaisesRegex(ValueError, "Paid provider"):
            CloudAgent(mode="free", paid_provider="local",
                       api_key="test")
        with self.assertRaisesRegex(ValueError, "boolean"):
            CloudAgent(mode="paid", paid_consent="true",
                       paid_provider="ollama", ollama_api_key="test")
        paid = CloudAgent(mode="paid", paid_provider="ollama",
                          ollama_api_key="test", paid_consent=True)
        try:
            self.assertEqual(paid.model, "nemotron-3-super")
            self.assertEqual(paid.provider, "ollama")
            self.assertEqual(paid.route_status()["primary"], "ollama")
            self.assertFalse(paid.route_status()["automatic_paid_fallback"])
            self.assertNotIn("test", json.dumps(paid.route_status()))
        finally:
            asyncio.run(paid.close())

    def test_openrouter_paid_remains_separate(self):
        agent = CloudAgent(mode="paid", paid_provider="openrouter",
                           paid_model="google/gemini-3.1-flash-lite",
                           paid_consent=True, api_key="openrouter-only")
        try:
            self.assertEqual(agent.provider, "openrouter")
            self.assertEqual(agent.model, "google/gemini-3.1-flash-lite")
            self.assertEqual(agent.route_status()["mode"], "paid")
        finally:
            asyncio.run(agent.close())


class OllamaTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.agent = CloudAgent(mode="paid", paid_provider="ollama",
                                ollama_api_key="fixture-secret",
                                paid_consent=True, model_timeout=40)
    async def asyncTearDown(self):
        await self.agent.close()

    async def test_native_ollama_chat_uses_correct_https_endpoint_and_receipts(self):
        messages = [
            {"role": "system", "content": "Synthetic catalog only"},
            {"role": "user", "content": "Find DEMO_SWITCH"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "fixture_read_state",
                              "arguments": {"fixture_id": "DEMO_SWITCH"}}}
            ]},
            {"role": "tool", "tool_name": "fixture_read_state",
             "content": '{"switch":"off","reported_at":"2026-01-01T00:00:00Z"}'},
        ]
        tools = [{"type": "function", "function": {
            "name": "fixture_read_state",
            "parameters": {"type": "object", "properties": {
                "fixture_id": {"type": "string"}}, "required": ["fixture_id"]},
        }}]
        before = json.dumps(messages)
        reply_body = {
            "model": "nemotron-3-super", "message": {"role": "assistant",
               "content": "Fixture reports OFF; the origin is unknown.",
               "tool_calls": []},
            "prompt_eval_count": 4022, "eval_count": 80,
            "total_duration": 1200000000, "eval_duration": 500000000,
        }
        with patch.object(self.agent.cloud.client, "post",
                          AsyncMock(return_value=FakeReply(reply_body))) as post:
            answer = await self.agent.round(messages, tools, 40)
        self.assertEqual(before, json.dumps(messages))
        self.assertEqual(post.call_args.args[0], "https://ollama.com/api/chat")
        request = post.call_args.kwargs["json"]
        self.assertEqual(request["model"], "nemotron-3-super")
        self.assertEqual(request["messages"], messages)
        self.assertEqual(request["tools"], tools)
        self.assertEqual(request["stream"], False)
        self.assertNotIn("fixture-secret", json.dumps(request))
        self.assertNotIn("think", request)
        self.assertEqual(answer["content"], reply_body["message"]["content"])
        self.assertEqual(answer["_inference_metrics"]["prompt_eval_count"], 4022)
        self.assertEqual(answer["_inference_metrics"]["total_ms"], 1200.0)
        self.assertEqual(answer["_inference_metrics"]["provider_reported_model"],
                         "nemotron-3-super")
        self.assertNotIn("provider_reported_cost_usd", answer["_inference_metrics"])
        self.assertEqual(self.agent.last_attempt["provider"], "ollama")

    async def test_model_native_tool_call_normalized_for_agent(self):
        with patch.object(self.agent.cloud.client, "post",
                          AsyncMock(return_value=FakeReply())):
            message = await self.agent.round(
                [{"role": "user", "content": "fictional tool check"}], [], 30)
        self.assertEqual(message["tool_calls"][0]["function"]["name"],
                         "fixture_read_state")
        self.assertEqual(message["tool_calls"][0]["function"]["arguments"],
                         {"fixture_id": "DEMO_SWITCH"})

    async def test_model_only_probe_uses_ollama_paid_no_mcp(self):
        with patch.object(self.agent.cloud.client, "post",
                          AsyncMock(return_value=FakeReply())) as post:
            result = await probe_cloud_tool_call(self.agent)
        self.assertTrue(result["tool_call_test_passed"])
        self.assertEqual(result["provider"], "ollama")
        self.assertEqual(result["mode"], "paid")
        self.assertEqual(post.await_count, 1)
        self.assertEqual(post.call_args.kwargs["json"]["tools"][0]
                         ["function"]["name"], "fixture_read_state")

    async def test_http_error_timeout_and_invalid_reply_do_not_fallback(self):
        for code in (402, 429, 503):
            with self.subTest(code=code):
                with patch.object(self.agent.cloud.client, "post",
                                  AsyncMock(return_value=FakeReply(status=code))) as post:
                    with self.assertRaisesRegex(RuntimeError, f"HTTP {code}"):
                        await self.agent.round([], [], 30)
                self.assertEqual(post.await_count, 1)
                self.assertEqual(self.agent.route_status()["primary"], "ollama")
        with patch.object(self.agent.cloud.client, "post",
                          AsyncMock(side_effect=asyncio.TimeoutError)):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                await self.agent.round([], [], 30)
        with patch.object(self.agent.cloud.client, "post",
                          AsyncMock(return_value=FakeReply(body={"x": 1}))):
            with self.assertRaisesRegex(RuntimeError, "invalid model response"):
                await self.agent.round([], [], 30)

    async def test_provider_provenance_in_private_answer(self):
        from agent import Agent
        async def pretend_agent_answer(_agent, *args, **kwargs):
            await _agent.round([{"role": "user", "content": "fictional"}], [], 30)
            return {"success": True, "answer": "fixture", "rounds": 1,
                    "tool_calls": []}
        with patch.object(Agent, "answer", pretend_agent_answer), \
             patch.object(self.agent.cloud.client, "post",
                          AsyncMock(return_value=FakeReply())):
            answer = await self.agent.answer("fixture", [], None, 30)
        self.assertEqual(answer["model_route"]["provider"], "cloud")
        self.assertEqual(answer["model_route"]["attempted_provider"], "ollama")
        self.assertEqual(answer["model_route"]["status"], "completed_model_round")
        self.assertEqual(answer["model_route"]["cloud_fallback_used"], False)


class SupervisorSchemaTests(unittest.TestCase):
    def test_ollama_key_is_optional_but_never_in_default_config(self):
        cfg = (Path(__file__).resolve().parents[1] / "config.yaml").read_text()
        self.assertIn('version: "2.0.0-alpha.93"', cfg)
        defaults = cfg.split("\noptions:\n", 1)[1].split("\nschema:\n", 1)[0]
        schema = cfg.split("\nschema:\n", 1)[1]
        self.assertIn("  cloud_paid_provider: \"openrouter\"", defaults)
        self.assertIn("  ollama_cloud_model: \"nemotron-3-super\"", defaults)
        self.assertIn("  ollama_cloud_api_key: password?", schema)
        self.assertNotIn("  ollama_cloud_api_key:", defaults)
        self.assertNotIn("  cloud_api_key:", defaults)

    def test_runtime_keeps_key_private_and_new_defaults(self):
        import app
        self.assertEqual(app.DEFAULTS["cloud_paid_provider"], "openrouter")
        self.assertEqual(app.DEFAULTS["ollama_cloud_model"], "nemotron-3-super")
        self.assertEqual(app.DEFAULTS["ollama_cloud_api_key"], "")


if __name__ == "__main__":
    unittest.main()

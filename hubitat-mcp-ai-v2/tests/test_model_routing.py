"""Fictional OpenRouter-only cloud model tests. No network or Hubitat calls."""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent
from model_routing import (
    CloudAgent, OpenRouterChat, cloud_configuration, free_model_name,
    paid_model_name, openai_messages, probe_cloud_tool_call,
)


class ModelConfigurationTests(unittest.TestCase):
    def test_free_mode_strictly_forbids_paid_model(self):
        self.assertEqual(free_model_name("openrouter/free"), "openrouter/free")
        self.assertEqual(free_model_name("provider/tool-model:free"),
                         "provider/tool-model:free")
        for bad in ("", "openrouter/auto", "openrouter/auto-beta",
                    "google/gemini-3.1-flash-lite", " paid/tool:free " + " broken",
                    "http://localhost:11434", "model:free"):
            with self.subTest(model=bad), self.assertRaises(ValueError):
                free_model_name(bad)

    def test_paid_model_has_two_explicit_opt_ins_and_no_automatic_router(self):
        with self.assertRaisesRegex(ValueError, "explicit"):
            cloud_configuration(
                mode="paid", free_model="openrouter/free",
                paid_model="google/gemini-3.1-flash-lite",
                paid_consent=False, api_key="fictional-secret",
            )
        with self.assertRaises(ValueError):
            cloud_configuration(
                mode="free", free_model="google/gemini-3.1-flash-lite",
                paid_model="google/gemini-3.1-flash-lite",
                paid_consent=True, api_key="fictional-secret",
            )
        for invalid in ("openrouter/auto", "openrouter/free", "model/foo:free",
                        "http://localhost:11434", ""):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                paid_model_name(invalid)
        configured = cloud_configuration(
            mode="paid", free_model="openrouter/free",
            paid_model="google/gemini-3.1-flash-lite",
            paid_consent=True, api_key="fixture-secret",
        )
        self.assertEqual(configured["model"], "google/gemini-3.1-flash-lite")

    def test_missing_key_and_wrong_mode_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "API key"):
            CloudAgent(api_key="")
        with self.assertRaisesRegex(ValueError, "free or paid"):
            CloudAgent(mode="local", api_key="fixture")
        with self.assertRaisesRegex(ValueError, "boolean"):
            CloudAgent(mode="paid", paid_consent="true", api_key="fixture")
        with self.assertRaisesRegex(ValueError, "explicit"):
            CloudAgent(mode="paid", paid_consent=False, api_key="fixture")

    def test_openai_tool_receipt_ids_preserve_raw_mcp_content(self):
        original = [
            {"role": "system", "content": "fictional tool agent"},
            {"role": "user", "content": "Inspect two synthetic devices"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "hub_list_devices",
                              "arguments": {"labelFilter": "FICTIONAL"}}},
                {"function": {"name": "hub_list_device_events",
                              "arguments": '{"deviceId":"LAB-1"}'}},
            ]},
            {"role": "tool", "tool_name": "hub_list_devices",
             "content": '{"count":1}'},
            {"role": "tool", "tool_name": "hub_list_device_events",
             "content": '{"events":[]}'},
            {"role": "assistant", "content": "The source rows are incomplete."},
        ]
        before = json.dumps(original)
        converted = openai_messages(original)
        self.assertEqual(json.dumps(original), before)
        self.assertEqual(converted[2]["tool_calls"][0]["id"],
                         converted[3]["tool_call_id"])
        self.assertEqual(converted[2]["tool_calls"][1]["id"],
                         converted[4]["tool_call_id"])
        self.assertEqual(converted[-1]["content"], original[-1]["content"])
        self.assertEqual(json.loads(
            converted[2]["tool_calls"][0]["function"]["arguments"]),
            {"labelFilter": "FICTIONAL"})

    def test_orphaned_tool_receipts_rejected_without_execution(self):
        with self.assertRaises(ValueError):
            openai_messages([{"role": "tool", "tool_name": "x", "content": "a"}])
        with self.assertRaises(ValueError):
            openai_messages([{"role": "assistant", "tool_calls": [
                {"function": {"name": "x", "arguments": {}}},
            ]}])


class FakeResponse:
    def __init__(self, body=None, status=200):
        self.body = body or {"choices": [{"message": {
            "content": "Synthetic answer", "tool_calls": []
        }}]}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                "non-public failure",
                request=httpx.Request("POST", "https://openrouter.ai"),
                response=httpx.Response(self.status_code,
                                        request=httpx.Request("POST", "https://openrouter.ai")))
    def json(self):
        return self.body


class CloudTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cloud = OpenRouterChat(
            mode="free", free_model="openrouter/free",
            paid_model="google/gemini-3.1-flash-lite",
            paid_consent=False, api_key="fixture-secret", timeout=30,
        )
    async def asyncTearDown(self):
        await self.cloud.close()

    async def test_free_cloud_transmits_native_tool_schema_and_reports_usage(self):
        body = {"model": "provider/synthetic:free", "usage": {
            "prompt_tokens": 3200, "completion_tokens": 36,
            "total_tokens": 3236, "cost": 0.0,
        }, "choices": [{"message": {"content": "",
            "tool_calls": [{"function": {"name": "hub_list_devices",
                 "arguments": '{"labelFilter":"FICTIONAL"}'}}]}}]}
        tools = [{"type": "function", "function": {
            "name": "hub_list_devices", "description": "Fictional read",
            "parameters": {"type": "object"},
        }}]
        with patch.object(self.cloud.client, "post",
                          AsyncMock(return_value=FakeResponse(body))) as post:
            reply = await self.cloud.round(
                [{"role": "user", "content": "fictional status"}], tools, 20)
        self.assertEqual(reply["tool_calls"][0]["function"]["name"],
                         "hub_list_devices")
        self.assertEqual(reply["_inference_metrics"]["provider_reported_model"],
                         "provider/synthetic:free")
        self.assertEqual(reply["_inference_metrics"]["prompt_tokens"], 3200)
        self.assertEqual(reply["_inference_metrics"]["provider_reported_cost_usd"], 0.0)
        request = post.call_args.kwargs["json"]
        self.assertEqual(request["model"], "openrouter/free")
        self.assertEqual(request["tools"], tools)
        self.assertEqual(request["tool_choice"], "auto")
        self.assertEqual(request["stream"], False)
        self.assertNotIn("fixture-secret", json.dumps(request))
        self.assertEqual(post.call_args.args[0],
                         "https://openrouter.ai/api/v1/chat/completions")

    async def test_paid_mode_requires_consent_and_keeps_one_model(self):
        agent = CloudAgent(mode="paid", paid_consent=True,
                           paid_model="google/gemini-3.1-flash-lite",
                           api_key="fixture-secret")
        try:
            self.assertTrue(agent.route_status()["paid_mode"])
            self.assertFalse(agent.route_status()["automatic_paid_fallback"])
            with patch.object(agent.cloud.client, "post",
                              AsyncMock(return_value=FakeResponse())) as post:
                await agent.round([{"role": "user", "content": "fixture"}], [], 30)
                await agent.round([{"role": "user", "content": "fixture 2"}], [], 30)
            self.assertEqual(post.await_count, 2)
            for call in post.call_args_list:
                self.assertEqual(call.kwargs["json"]["model"],
                                 "google/gemini-3.1-flash-lite")
        finally:
            await agent.close()

    async def test_429_and_timeout_never_escalate_to_paid_or_other_provider(self):
        agent = CloudAgent(api_key="fixture-secret")
        try:
            with patch.object(agent.cloud.client, "post",
                              AsyncMock(return_value=FakeResponse(status=429))) as post:
                with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
                    await agent.round([{"role": "user", "content": "test"}], [], 30)
                self.assertEqual(post.await_count, 1)
            with patch.object(agent.cloud.client, "post",
                              AsyncMock(side_effect=asyncio.TimeoutError)):
                with self.assertRaisesRegex(RuntimeError, "timed out"):
                    await agent.round([{"role": "user", "content": "test"}], [], 30)
            self.assertEqual(agent.route_status()["mode"], "free")
        finally:
            await agent.close()

    async def test_synthetic_probe_requires_correct_arguments_and_no_real_mcp(self):
        agent = CloudAgent(api_key="fixture-secret")
        try:
            with patch.object(agent.cloud, "round", AsyncMock(return_value={
                "content": "", "tool_calls": [{"function": {
                    "name": "fixture_read_state",
                    "arguments": '{"fixture_id":"DEMO_SWITCH"}',
                }}], "_inference_metrics": {"prompt_tokens": 90},
            })) as model:
                outcome = await probe_cloud_tool_call(agent)
            self.assertTrue(outcome["tool_call_test_passed"])
            self.assertEqual(outcome["model_rounds"], 1)
            self.assertIn("no actual tool executed", outcome["note"])
            args = model.call_args.args
            self.assertEqual([x["function"]["name"] for x in args[1]],
                             ["fixture_read_state"])
            self.assertEqual(args[0][-1]["content"].count("DEMO_SWITCH"), 1)
            with patch.object(agent.cloud, "round", AsyncMock(return_value={
                "content": "I will use the tool", "tool_calls": [],
            })):
                failed = await probe_cloud_tool_call(agent)
            self.assertFalse(failed["tool_call_test_passed"])
        finally:
            await agent.close()

    async def test_agent_provenance_only_after_actual_answer(self):
        agent = CloudAgent(api_key="fixture-secret")
        try:
            async def simulated_parent(_agent, *args, **kwargs):
                response = await _agent.round([{"role": "user", "content": "fixture"}],
                                               [], 25)
                return {"success": True, "answer": response["content"],
                        "rounds": 1, "tool_calls": []}
            with patch.object(Agent, "answer", simulated_parent), \
                 patch.object(agent.cloud, "round", AsyncMock(
                     return_value={"content": "synthetic", "tool_calls": []}
                 )):
                result = await agent.answer("fixture", [], None, 90)
            self.assertEqual(result["model_route"]["provider"], "cloud")
            self.assertEqual(result["model_route"]["mode"], "free")
            self.assertEqual(result["model_route"]["status"], "completed_model_round")
            self.assertEqual(result["model_route"]["attempted_provider"], "openrouter")
        finally:
            await agent.close()


class AddonCloudConfigTests(unittest.TestCase):
    def test_legacy_model_options_ignored_and_new_key_required(self):
        import app as addon
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp:
            options_file = Path(temp) / "options.json"
            options_file.write_text(json.dumps({
                "model_base_url": "http://192.168.1.2:11434",
                "model_name": "qwen3.5:4b",
                "model_api_key": "legacy-secret",
                "cloud_fallback_api_key": "legacy-cloud-secret",
            }), encoding="utf-8")
            settings = addon.config(options_file)
        for obsolete in ("model_base_url", "model_name", "model_api_key",
                         "cloud_fallback_api_key", "local_ollama_think"):
            self.assertNotIn(obsolete, settings)
        self.assertEqual(settings["cloud_mode"], "free")
        self.assertEqual(settings["cloud_api_key"], "")
        self.assertFalse(settings["cloud_paid_consent"])

    def test_schema_has_no_local_and_free_paid_requires_explicit_consent(self):
        config = (Path(__file__).resolve().parents[1] / "config.yaml").read_text()
        self.assertIn("version: \"2.0.0-alpha.139\"", config)
        self.assertNotIn("model_base_url:", config)
        self.assertNotIn("local_ollama_num_ctx:", config)
        self.assertIn("cloud_mode: list(free|paid)", config)
        self.assertIn("cloud_api_key: password?", config)
        defaults = config.split("options:", 1)[1].split("\nschema:", 1)[0]
        self.assertNotIn("cloud_api_key:", defaults)
        self.assertIn("cloud_paid_consent: false", defaults)


if __name__ == "__main__":
    unittest.main()

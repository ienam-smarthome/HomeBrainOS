"""Fictional local-first/cloud-free routing tests. No network, Hubitat or paid AI."""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent, ModelEndpointUnavailable
from model_routing import RoutedAgent, OpenRouterFree, free_model_name, openai_messages


class ModelNameAndMessagesTests(unittest.TestCase):
    def test_only_explicit_free_cloud_names_are_accepted(self):
        self.assertEqual(free_model_name("openrouter/free"), "openrouter/free")
        self.assertEqual(free_model_name("fictional/logic:free"), "fictional/logic:free")
        for model in ("", "openrouter/auto", "paid/gemini", "bad :free"):
            with self.subTest(model=model), self.assertRaises(ValueError):
                free_model_name(model)

    def test_convert_multiple_ollama_tool_receipts_without_changing_source(self):
        original = [
            {"role": "system", "content": "test system"},
            {"role": "user", "content": "What happened?"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "hub_list_devices",
                              "arguments": {"labelFilter": "fictional"}}},
                {"function": {"name": "hub_list_device_events",
                              "arguments": '{"deviceId":"LAB-1"}'}},
            ]},
            {"role": "tool", "tool_name": "hub_list_devices",
             "content": '{"count":1}'},
            {"role": "tool", "tool_name": "hub_list_device_events",
             "content": '{"events":[]}'},
            {"role": "assistant", "content": "Only bounded reads were checked."},
        ]
        before = json.dumps(original, sort_keys=True)
        converted = openai_messages(original)
        self.assertEqual(json.dumps(original, sort_keys=True), before)
        calls = converted[2]["tool_calls"]
        self.assertEqual(len(calls), 2)
        self.assertEqual([c["id"] for c in calls], [
            converted[3]["tool_call_id"], converted[4]["tool_call_id"],
        ])
        self.assertEqual(json.loads(calls[0]["function"]["arguments"]),
                         {"labelFilter": "fictional"})
        self.assertEqual(json.loads(calls[1]["function"]["arguments"]),
                         {"deviceId": "LAB-1"})
        self.assertEqual(converted[-1]["content"], original[-1]["content"])

    def test_unpaired_tool_result_is_refused(self):
        with self.assertRaisesRegex(ValueError, "Unpaired"):
            openai_messages([{"role": "tool", "tool_name": "x", "content": "a"}])
        with self.assertRaisesRegex(ValueError, "lack matching"):
            openai_messages([{"role": "assistant", "tool_calls": [
                {"function": {"name": "x", "arguments": {}}},
            ]}])


class RouterRequestIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.router = RoutedAgent(
            "http://192.0.2.5:11434", "fictional:4b", "", 30,
            cloud_fallback_enabled=True,
            cloud_fallback_model="openrouter/free",
            cloud_fallback_api_key="fictional-test-key",
        )

    async def asyncTearDown(self):
        await self.router.close()

    async def test_local_connection_failure_uses_free_cloud_once_then_pins(self):
        local = AsyncMock(side_effect=ModelEndpointUnavailable("offline"))
        cloud = AsyncMock(side_effect=[
            {"content": "Cloud tool plan", "tool_calls": []},
            {"content": "Cloud final", "tool_calls": []},
        ])
        with patch.object(Agent, "round", local), patch.object(self.router.cloud, "round", cloud):
            state = {"provider": None}
            token = self.router._route.set(state)
            try:
                first = await self.router.round([{"role": "user", "content": "hi"}], [], 25)
                second = await self.router.round([{"role": "user", "content": "again"}], [], 25)
            finally:
                self.router._route.reset(token)
        self.assertEqual(first["content"], "Cloud tool plan")
        self.assertEqual(second["content"], "Cloud final")
        self.assertEqual(state["provider"], "cloud")
        self.assertEqual(local.await_count, 1)
        self.assertEqual(cloud.await_count, 2)
        self.assertEqual(self.router.last_attempt["reason"], "local_connect_failed")
        self.assertNotIn("fictional-test-key", json.dumps(self.router.route_status()))

    async def test_successful_local_round_cannot_switch_mid_request(self):
        local = AsyncMock(side_effect=[
            {"content": "Local tool plan"}, ModelEndpointUnavailable("off"),
        ])
        cloud = AsyncMock()
        with patch.object(Agent, "round", local), patch.object(self.router.cloud, "round", cloud):
            state = {"provider": None}
            token = self.router._route.set(state)
            try:
                self.assertEqual(
                    (await self.router.round([], [], 25))["content"],
                    "Local tool plan",
                )
                with self.assertRaisesRegex(ModelEndpointUnavailable, "mid-request"):
                    await self.router.round([], [], 25)
            finally:
                self.router._route.reset(token)
        self.assertEqual(state["provider"], "local")
        cloud.assert_not_awaited()

    async def test_timeout_rate_limit_and_http_failures_do_not_use_cloud(self):
        cloud = AsyncMock()
        with patch.object(self.router.cloud, "round", cloud):
            for failure in (
                RuntimeError("Model request timed out"),
                RuntimeError("Model API returned HTTP 429"),
                RuntimeError("Model API returned HTTP 500"),
            ):
                with self.subTest(failure=str(failure)):
                    with patch.object(Agent, "round", AsyncMock(side_effect=failure)):
                        with self.assertRaises(RuntimeError):
                            await self.router.round([], [], 25)
        cloud.assert_not_awaited()

    async def test_fallback_disabled_and_broken_configuration(self):
        with self.assertRaisesRegex(ValueError, "API key"):
            RoutedAgent("http://192.0.2.5:11434", "fictional", "", 30,
                        cloud_fallback_enabled=True)
        with self.assertRaisesRegex(ValueError, "free"):
            RoutedAgent("http://192.0.2.5:11434", "fictional", "", 30,
                        cloud_fallback_enabled=True,
                        cloud_fallback_model="premium/large",
                        cloud_fallback_api_key="test")
        disabled = RoutedAgent("http://192.0.2.5:11434", "fictional", "", 30)
        try:
            with patch.object(Agent, "round",
                              AsyncMock(side_effect=ModelEndpointUnavailable("offline"))):
                with self.assertRaises(ModelEndpointUnavailable):
                    await disabled.round([], [], 25)
            self.assertFalse(disabled.route_status()["fallback_enabled"])
        finally:
            await disabled.close()

    async def test_request_scope_is_reset_even_if_answer_fails(self):
        async def parent_answer(_self, *args, **kwargs):
            await _self.round([{"role": "user", "content": "fictional"}], [], 25)
            return {"success": True, "answer": "fictional", "tool_calls": []}
        local = AsyncMock(side_effect=[
            ModelEndpointUnavailable("offline"), {"content": "Local", "tool_calls": []},
        ])
        cloud = AsyncMock(return_value={"content": "Cloud", "tool_calls": []})
        with patch.object(Agent, "round", local), \
             patch.object(Agent, "answer", parent_answer), \
             patch.object(self.router.cloud, "round", cloud):
            a = await self.router.answer("one", [], None, 30)
            b = await self.router.answer("two", [], None, 30)
        self.assertEqual(a["model_route"]["provider"], "cloud")
        self.assertEqual(b["model_route"]["provider"], "local")
        self.assertEqual(local.await_count, 2)
        self.assertEqual(cloud.await_count, 1)


class FreeCloudTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_openai_compatible_tools_and_api_key_are_server_side(self):
        cloud = OpenRouterFree(model="openrouter/free", api_key="fixture-secret", timeout=20)
        data = {
            "choices": [{"message": {
                "content": None,
                "tool_calls": [{
                    "id": "call1", "type": "function",
                    "function": {"name": "hub_list_devices",
                                 "arguments": '{"labelFilter":"test"}'},
                }],
            }}],
        }
        class FakeResponse:
            def raise_for_status(self):
                return None
            def json(self):
                return data
        try:
            with patch.object(cloud.client, "post",
                              AsyncMock(return_value=FakeResponse())) as post:
                out = await cloud.round(
                    [{"role": "user", "content": "hello"}],
                    [{"type": "function", "function": {"name": "hub_list_devices",
                       "description": "List", "parameters": {"type": "object"}}}], 20,
                )
            self.assertEqual(out["tool_calls"][0]["function"]["name"],
                             "hub_list_devices")
            self.assertEqual(out["tool_calls"][0]["function"]["arguments"],
                             '{"labelFilter":"test"}')
            self.assertEqual(post.call_args.args[0],
                             "https://openrouter.ai/api/v1/chat/completions")
            body = post.call_args.kwargs["json"]
            self.assertEqual(body["model"], "openrouter/free")
            self.assertEqual(body["tools"][0]["function"]["name"], "hub_list_devices")
            self.assertNotIn("fixture-secret", json.dumps(body))
            self.assertTrue(post.call_args.kwargs["json"]["stream"] is False)
        finally:
            await cloud.close()


if __name__ == "__main__":
    unittest.main()

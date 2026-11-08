"""Generic native MCP leaf schema discovery, caching, and safe preflight.

All payloads are synthetic. This test never connects to a real hub or cloud model.
"""
import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent, model_tools
from mcp import MCPClient, MCPContractError


READ_SCHEMA = {
    "type": "object",
    "properties": {
        "mode": {"type": "string", "enum": ["table", "hubEvents"],
                 "description": "Choose one live log mode."},
        "sortBy": {"type": "string", "enum": ["name", "count"],
                   "description": "For table mode only."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
    },
    "additionalProperties": False,
}
ACTION_SCHEMA = {
    "type": "object",
    "properties": {"target": {"type": "string"},
                   "confirm": {"type": "boolean"}},
    "required": ["target", "confirm"],
    "additionalProperties": False,
}
GATEWAY = {
    "name": "gateway_alpha",
    "description": "Native server-advertised tool gateway.",
    "inputSchema": {"type": "object", "properties": {
        "tool": {"type": "string", "enum": ["read_log_rows", "perform_action"]},
        "args": {"type": "object"},
    }},
}


class FakeServer:
    def __init__(self):
        self.calls = []
        self.catalog_calls = 0
        self.domain_calls = 0
        self.tools = [copy.deepcopy(GATEWAY)]
        self.client = MCPClient("http://192.0.2.1/mcp")
        self.client._initialized = True
        self.client._tools = {GATEWAY["name"]: copy.deepcopy(GATEWAY)}
        self.client._client = httpx.AsyncClient(transport=httpx.MockTransport(self.reply))

    def reply(self, request):
        body = json.loads(request.content)
        if body["method"] == "tools/list":
            result = {"tools": self.tools}
        elif body["method"] == "tools/call":
            name = body["params"]["name"]
            args = body["params"]["arguments"]
            self.calls.append((name, args))
            if args == {}:
                self.catalog_calls += 1
                result = {"content": [{"type": "text", "text": json.dumps({
                    "gateway": name, "mode": "catalog",
                    "tools": [
                        {"name": "read_log_rows", "description": "Read log rows",
                         "inputSchema": READ_SCHEMA},
                        {"name": "perform_action",
                         "description": "Potentially mutating tool; permission enforced upstream",
                         "inputSchema": ACTION_SCHEMA},
                    ]})}]}
            else:
                self.domain_calls += 1
                result = {"content": [{"type": "text",
                                       "text": '{"events":[{"date":"2026-11-08T10:00:00Z"}]}'}]}
        else:
            return httpx.Response(400, json={"error": "unexpected"})
        return httpx.Response(200, json={"jsonrpc": "2.0",
                                         "id": body.get("id"),
                                         "result": result})

    async def close(self):
        await self.client.close()


class LiveLeafContractTests(unittest.TestCase):
    def test_discovery_once_per_gateway_and_cache_only_selected_leaf(self):
        async def run():
            server = FakeServer()
            try:
                self.assertEqual(server.client.cached_leaf_schemas(), {})
                spec, fetched = await server.client.gateway_leaf_schema(
                    "gateway_alpha", "read_log_rows")
                self.assertTrue(fetched)
                self.assertEqual(spec["inputSchema"], READ_SCHEMA)
                self.assertEqual(server.catalog_calls, 1)
                cached = server.client.cached_leaf_schemas()
                self.assertEqual(list(cached), ["gateway_alpha"])
                self.assertEqual(list(cached["gateway_alpha"]), ["read_log_rows"])
                second, fetched = await server.client.gateway_leaf_schema(
                    "gateway_alpha", "read_log_rows")
                self.assertFalse(fetched)
                self.assertEqual(second, spec)
                self.assertEqual(server.catalog_calls, 1)
                self.assertEqual(server.domain_calls, 0)
                self.assertEqual(server.calls, [("gateway_alpha", {})])
                # A new native catalog generation clears old client leaf cache.
                changed = copy.deepcopy(GATEWAY)
                changed["description"] = "Upstream server changed its catalog"
                server.tools = [changed]
                await server.client.list_tools(refresh=True)
                self.assertEqual(server.client.cached_leaf_schemas(), {})
            finally:
                await server.close()
        asyncio.run(run())

    def test_model_sees_original_upstream_mode_specific_description(self):
        leaves = {"gateway_alpha": {"read_log_rows": {
            "name": "read_log_rows", "inputSchema": READ_SCHEMA}}}
        catalog = [copy.deepcopy(GATEWAY)]
        original = copy.deepcopy(catalog)
        decorated = model_tools(catalog, leaves)[0]["function"]
        self.assertIn("NATIVE LEAF CONTRACT", decorated["description"])
        self.assertIn("For table mode only.", decorated["description"])
        self.assertIn('"sortBy"', decorated["description"])
        self.assertEqual(catalog, original)
        self.assertIn("hubEvents", decorated["description"])
        self.assertNotIn("NATIVE LEAF CONTRACT",
                         model_tools(catalog)[0]["function"]["description"])

    def test_leaf_structural_validation_rejects_wrong_type_without_remote_action(self):
        async def run():
            server = FakeServer()
            try:
                definition, _ = await server.client.gateway_leaf_schema(
                    "gateway_alpha", "read_log_rows")
                for bad in ({"limit": "fifty"}, {"unknown": 1}, {"limit": 500}):
                    with self.subTest(bad=bad):
                        with self.assertRaisesRegex(MCPContractError, "Leaf arguments"):
                            server.client.validate_leaf_arguments(definition, bad)
                self.assertEqual(server.domain_calls, 0)
                self.assertEqual(server.catalog_calls, 1)
                # Prose-only mode restrictions are NOT invented as a local rule.
                server.client.validate_leaf_arguments(definition, {
                    "mode": "hubEvents", "sortBy": "name",
                })
            finally:
                await server.close()
        asyncio.run(run())

    def test_first_invalid_leaf_call_is_not_executed_and_model_can_correct(self):
        class ScriptedAgent(Agent):
            def __init__(self):
                super().__init__("http://127.0.0.1:11434", "fixture", "", 20)
                self.round_count = 0
            async def round(self, messages, tools, remaining):
                self.round_count += 1
                definition = next(t["function"] for t in tools
                                  if t["function"]["name"] == "gateway_alpha")
                if self.round_count == 1:
                    self.assertion1 = "NATIVE LEAF CONTRACT" not in definition["description"]
                    return {"content": "", "tool_calls": [{
                        "function": {"name": "gateway_alpha",
                                     "arguments": {"tool": "read_log_rows",
                                                   "args": {"limit": "fifty"}}}
                    }]}
                self.assertion2 = ("NATIVE LEAF CONTRACT" in definition["description"]
                                   and "For table mode only." in definition["description"])
                if self.round_count == 2:
                    self.assertEqual([x["role"] for x in messages[-2:]], ["assistant", "tool"])
                    self.assertIn("Leaf arguments violate", messages[-1]["content"])
                    return {"content": "", "tool_calls": [{
                        "function": {"name": "gateway_alpha",
                                     "arguments": {"tool": "read_log_rows",
                                                   "args": {"mode": "hubEvents", "limit": 50}}}
                    }]}
                return {"content": "The available event rows do not prove a cause.",
                        "tool_calls": []}

        async def run():
            server = FakeServer()
            agent = ScriptedAgent()
            try:
                result = await agent.answer("Read system events", [], server.client, 60)
                self.assertTrue(result["success"])
                self.assertTrue(agent.assertion1)
                self.assertTrue(agent.assertion2)
                self.assertEqual(result["leaf_schema_discoveries"], 1)
                self.assertEqual(result["rounds"], 3)
                self.assertEqual(server.catalog_calls, 1)
                self.assertEqual(server.domain_calls, 1)
                self.assertEqual([x["result_kind"] for x in result["tool_calls"]],
                                 ["contract_error", "tool_result"])
                self.assertFalse(result["tool_calls"][0]["operation_executed"])
                self.assertEqual(server.calls[1], ("gateway_alpha",
                               {"tool": "read_log_rows",
                                "args": {"mode": "hubEvents", "limit": 50}}))
            finally:
                await agent.close()
                await server.close()
        asyncio.run(run())

    def test_unrelated_direct_tool_keeps_local_data_tool_key(self):
        flat = {"name": "flat_provider", "inputSchema": {"type": "object",
                "properties": {"args": {"type": "object", "properties": {
                    "tool": {"type": "string"}}}}}}
        presentation = model_tools([flat])
        self.assertEqual(presentation[0]["function"]["parameters"], flat["inputSchema"])
        self.assertNotIn("NATIVE LEAF CONTRACT",
                         presentation[0]["function"]["description"])


if __name__ == "__main__":
    unittest.main()

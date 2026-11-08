"""Compare existing v2 gateway and native flat MCP shapes without changing runtime.

Synthetic server catalog and events only. These tests neither change Hubitat's
useGateways setting nor prove Gemma first-attempt accuracy or live latency.
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
from interaction import Interaction
from mcp import MCPClient, MCPError


LEAF_SCHEMA = {
    "type": "object",
    "properties": {
        "mode": {"type": "string", "enum": ["hubEvents", "past"],
                 "description": "hubEvents includes restart events"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
    },
    "required": ["mode"],
    "additionalProperties": False,
}
FLAT_LOG = {
    "name": "hub_get_logs",
    "description": "Native log history, schema present on tools/list",
    "inputSchema": LEAF_SCHEMA,
}
GATEWAY = {
    "name": "hub_read_diagnostics",
    "description": "Category gateway containing hub_get_logs",
    "inputSchema": {
        "type": "object",
        "properties": {
            "tool": {"type": "string", "enum": ["hub_get_logs"]},
            "args": {"type": "object"},
        },
    },
}
WRITE = {
    "name": "hub_reboot",
    "description": "Requires explicit confirmation and upstream write access",
    "inputSchema": {
        "type": "object",
        "properties": {"confirm": {"type": "boolean", "const": True}},
        "required": ["confirm"],
    },
}


class ModeServer:
    def __init__(self, *, flat=False, allow_write=False):
        self.flat = flat
        self.allow_write = allow_write
        self.requests = []
        self.client = MCPClient("http://192.0.2.1/mcp")
        self.client._initialized = True
        self.client._client = httpx.AsyncClient(transport=httpx.MockTransport(self.respond))

    def advertised(self):
        catalog = [copy.deepcopy(FLAT_LOG if self.flat else GATEWAY)]
        if self.allow_write:
            catalog.append(copy.deepcopy(WRITE))
        return catalog

    def respond(self, request):
        body = json.loads(request.content)
        method = body["method"]
        if method == "tools/list":
            return httpx.Response(200, json={
                "jsonrpc": "2.0", "id": body["id"],
                "result": {"tools": self.advertised()},
            })
        if method != "tools/call":
            return httpx.Response(400, json={"error": "Unexpected method"})
        name = body["params"]["name"]
        args = body["params"]["arguments"]
        self.requests.append((name, copy.deepcopy(args)))
        if name == "hub_read_diagnostics" and args == {} and not self.flat:
            text = json.dumps({
                "gateway": name, "mode": "catalog",
                "tools": [copy.deepcopy(FLAT_LOG)],
            })
        elif ((not self.flat and name == "hub_read_diagnostics"
               and args == {"tool": "hub_get_logs", "args": {"mode": "hubEvents"}})
              or (self.flat and name == "hub_get_logs" and args == {"mode": "hubEvents"})):
            text = json.dumps({
                "mode": "hubEvents", "entries": [
                    {"name": "update", "date": "2026-11-07T14:40:56Z"},
                    {"name": "systemStart", "date": "2026-11-07T14:45:54Z"},
                ],
            })
        elif name == "hub_reboot":
            text = '{"error":"A simulated write should never execute in this test"}'
            return httpx.Response(200, json={
                "jsonrpc": "2.0", "id": body["id"],
                "result": {"isError": True, "content": [{"type": "text", "text": text}]},
            })
        else:
            return httpx.Response(400, json={"error": "Unexpected tool/argument shape"})
        return httpx.Response(200, json={
            "jsonrpc": "2.0", "id": body["id"],
            "result": {"content": [{"type": "text", "text": text}]},
        })

    async def close(self):
        await self.client.close()


class ScriptedComparisonAgent(Agent):
    """A scripted transport test, deliberately NOT real Gemma inference."""
    def __init__(self):
        super().__init__("http://127.0.0.1:11434", "stub", "", 20)
        self.first_tools = None

    async def round(self, messages, tools, remaining):
        if not any(m.get("role") == "tool" for m in messages):
            self.first_tools = copy.deepcopy(tools)
            names = [item["function"]["name"] for item in tools]
            if "hub_get_logs" in names:
                name = "hub_get_logs"
                arguments = {"mode": "hubEvents"}
            else:
                name = "hub_read_diagnostics"
                arguments = {"tool": "hub_get_logs", "args": {"mode": "hubEvents"}}
            return {"content": "", "tool_calls": [{
                "function": {"name": name, "arguments": arguments}
            }]}
        return {"content": "Latest startup follows a firmware update; corroboration is partial.",
                "tool_calls": []}


class FlatVsGatewayCompatibilityTests(unittest.TestCase):
    def test_read_equivalence_and_flat_tool_name_is_direct(self):
        async def trial(flat):
            server = ModeServer(flat=flat)
            agent = ScriptedComparisonAgent()
            try:
                result = await agent.answer("Investigate the latest reboot. Read only.",
                                            [], server.client, 45)
                self.assertTrue(result["success"])
                self.assertEqual(result["rounds"], 2)
                self.assertEqual(len(result["tool_calls"]), 1)
                self.assertTrue(result["tool_calls"][0]["success"])
                payload = json.loads(result["tool_calls"][0]["response"])
                rows = json.loads(payload["content"][0]["text"])
                self.assertEqual([x["name"] for x in rows["entries"]],
                                 ["update", "systemStart"])
                if flat:
                    self.assertEqual(result["leaf_schema_discoveries"], 0)
                    self.assertEqual(server.requests, [
                        ("hub_get_logs", {"mode": "hubEvents"})
                    ])
                    tool = agent.first_tools[0]["function"]
                    self.assertEqual(tool["name"], "hub_get_logs")
                    self.assertEqual(tool["parameters"], LEAF_SCHEMA)
                    self.assertNotIn("MCP GATEWAY CALL SHAPE", tool["description"])
                else:
                    self.assertEqual(result["leaf_schema_discoveries"], 1)
                    self.assertEqual(server.requests, [
                        ("hub_read_diagnostics", {}),
                        ("hub_read_diagnostics", {
                            "tool": "hub_get_logs",
                            "args": {"mode": "hubEvents"},
                        }),
                    ])
                    self.assertIn("MCP GATEWAY CALL SHAPE",
                                  agent.first_tools[0]["function"]["description"])
                return rows
            finally:
                await agent.close()
                await server.close()
        async def run():
            gateway_rows = await trial(False)
            flat_rows = await trial(True)
            self.assertEqual(flat_rows, gateway_rows)
        asyncio.run(run())

    def test_direct_flat_tool_is_not_mutated_into_a_gateway(self):
        catalog = [copy.deepcopy(FLAT_LOG), copy.deepcopy(WRITE)]
        before = copy.deepcopy(catalog)
        tools = model_tools(catalog)
        self.assertEqual([x["function"]["name"] for x in tools],
                         ["hub_get_logs", "hub_reboot"])
        self.assertEqual(tools[0]["function"]["parameters"], LEAF_SCHEMA)
        self.assertEqual(catalog, before)

    def test_flat_read_only_catalog_hides_write_and_rejects_stale_name(self):
        async def run():
            server = ModeServer(flat=True, allow_write=False)
            try:
                names = [x["name"] for x in await server.client.list_tools(refresh=True)]
                self.assertEqual(names, ["hub_get_logs"])
                with self.assertRaisesRegex(MCPError, "not in the connected server catalog"):
                    await server.client.call("hub_reboot", {"confirm": True})
                self.assertEqual(server.requests, [])
            finally:
                await server.close()
        asyncio.run(run())

    def test_mode_switch_reloads_authoritative_server_catalog_without_client_rewrite(self):
        async def run():
            server = ModeServer(flat=False)
            try:
                first = await server.client.list_tools(refresh=True)
                self.assertEqual([x["name"] for x in first], ["hub_read_diagnostics"])
                server.flat = True
                changed = await server.client.list_tools(refresh=True)
                self.assertEqual([x["name"] for x in changed], ["hub_get_logs"])
                with self.assertRaisesRegex(MCPError, "not in the connected server catalog"):
                    await server.client.call("hub_read_diagnostics", {})
                await server.client.call("hub_get_logs", {"mode": "hubEvents"})
                self.assertEqual(server.requests, [
                    ("hub_get_logs", {"mode": "hubEvents"})
                ])
            finally:
                await server.close()
        asyncio.run(run())

    def test_flat_write_confirmation_still_blocks_until_explicit_decision(self):
        async def run():
            server = ModeServer(flat=True, allow_write=True)
            interaction = Interaction()
            try:
                await server.client.list_tools(refresh=True)
                pending = asyncio.create_task(interaction.before_call(
                    "hub_reboot", {"confirm": True},
                    "Simulated write confirmation; no Hubitat write authorised."
                ))
                await asyncio.sleep(0)
                self.assertIsNotNone(interaction.pending)
                self.assertEqual(server.requests, [])
                interaction.decide(interaction.pending["id"], False)
                with self.assertRaisesRegex(MCPError, "declined"):
                    await pending
                self.assertEqual(server.requests, [])
            finally:
                await server.close()
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

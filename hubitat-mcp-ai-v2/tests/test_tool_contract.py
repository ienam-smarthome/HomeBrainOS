"""Synthetic regression for nested gateway selectors and schema-safe redaction.

No household records, device-specific routing, or live model/hub access.
"""
import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from mcp import MCPClient, MCPError, MCPContractError, redact
from agent import Agent, compact_tool_result


GATEWAY_SCHEMA = {
    "type": "object",
    "properties": {
        "tool": {"type": "string", "enum": ["hub_list_devices", "hub_list_device_events"]},
        "args": {"type": "object"},
    },
}
LEAF_SCHEMA = {
    "type": "object",
    "properties": {
        "include_token": {"type": "boolean", "default": False},
        "access_token": {"type": "string", "description": "Optional credential"},
        "labelFilter": {"type": "string"},
    },
    "required": ["include_token"],
    "additionalProperties": False,
}


def catalog_result():
    return {"content": [{"type": "text", "text": json.dumps({
        "gateway": "hub_read_devices", "mode": "catalog",
        "message": "Call again with tool='<name>' and args={...} to execute a tool.",
        "tools": [{"name": "hub_list_devices", "inputSchema": LEAF_SCHEMA}],
    })}]}


class LiveClient:
    def __init__(self):
        self.calls = []
        self.client = MCPClient("http://192.168.1.10/mcp")
        self.client._initialized = True
        self.client._tools = {"hub_read_devices": {
            "name": "hub_read_devices", "inputSchema": GATEWAY_SCHEMA}}
        self.client._client = httpx.AsyncClient(transport=httpx.MockTransport(self.reply))

    def reply(self, request):
        data = json.loads(request.content)
        if data["method"] == "tools/list":
            result = {"tools": list(self.client._tools.values())}
        else:
            arguments = data["params"]["arguments"]
            self.calls.append(copy.deepcopy(arguments))
            if not arguments.get("tool"):
                result = catalog_result()
            elif arguments["tool"] == "hub_list_devices":
                result = {"content": [{"type": "text", "text": json.dumps({
                    "devices": [{"id": "17", "label": "Sample Sensor"}], "count": 1})}]}
            else:
                result = {"content": [{"type": "text", "text": json.dumps({
                    "events": [{"date": "2026-01-01T10:00:00Z", "value": "active"}]})}]}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": data["id"], "result": result})

    async def close(self):
        await self.client.close()


class GatewayContractRegressions(unittest.TestCase):
    def test_seven_nested_selector_variations_do_not_execute_discovery(self):
        # Same seven request shapes as the supplied trace, with synthetic filters.
        variants = [
            {"tool": "hub_list_devices"},
            {"format": "context", "tool": "hub_list_devices"},
            {"format": "summary", "tool": "hub_list_devices"},
            {"labelFilter": "Sample", "tool": "hub_list_devices"},
            {"format": "summary", "labelFilter": "Sample", "tool": "hub_list_devices"},
            {"format": "detailed", "labelFilter": "Sample", "tool": "hub_list_devices"},
            {"format": "context", "tool": "hub_list_devices"},
        ]
        async def run():
            transport = LiveClient()
            try:
                for nested in variants:
                    with self.subTest(nested=nested):
                        with self.assertRaisesRegex(MCPError, "top.level"):
                            await transport.client.call("hub_read_devices", {"args": nested})
                self.assertEqual(transport.calls, [])
                discovered = await transport.client.call("hub_read_devices", {})
                self.assertEqual(json.loads(discovered["content"][0]["text"])["mode"], "catalog")
                await transport.client.call("hub_read_devices", {
                    "tool": "hub_list_devices", "args": {"include_token": False}})
                self.assertEqual(transport.calls[-1], {
                    "tool": "hub_list_devices", "args": {"include_token": False}})
            finally:
                await transport.close()
        asyncio.run(run())

    def test_live_schema_validates_types_and_does_not_rewrite_flat_payloads(self):
        async def run():
            transport = LiveClient()
            try:
                with self.assertRaisesRegex(MCPContractError, "input schema"):
                    await transport.client.call("hub_read_devices", {
                        "tool": "hub_list_devices", "args": "not an object"})
                with self.assertRaises(MCPContractError):
                    await transport.client.call("hub_read_devices", {
                        "tool": "not_in_live_enum", "args": {}})
                with self.assertRaisesRegex(MCPContractError, "inside 'args'"):
                    await transport.client.call("hub_read_devices", {
                        "tool": "hub_list_devices", "labelFilter": "Sample"})
                self.assertEqual(transport.calls, [])
                transport.client._tools = {"new_flat_tool": {
                    "name": "new_flat_tool",
                    "inputSchema": {"type": "object", "properties": {"args": {"type": "object"}}}}}
                payload = {"args": {"tool": "literal user data"}}
                await transport.client.call("new_flat_tool", payload)
                self.assertEqual(transport.calls, [payload])
            finally:
                await transport.close()
        asyncio.run(run())

    def test_remote_schema_refs_are_not_fetched(self):
        async def run():
            transport = LiveClient()
            transport.client._tools["hub_read_devices"]["inputSchema"] = {
                "$ref": "https://example.invalid/private-schema"}
            try:
                with self.assertRaises(MCPContractError):
                    await transport.client.call("hub_read_devices", {})
                self.assertEqual(transport.calls, [])
            finally:
                await transport.close()
        asyncio.run(run())

    def test_catalog_receipt_is_not_reported_as_a_domain_query(self):
        class DiscoveryAgent(Agent):
            async def round(self, messages, tools, remaining):
                if messages[-1]["role"] == "tool":
                    payload = json.loads(messages[-1]["content"])
                    self.seen = payload
                    return {"content": "Schemas discovered; data not yet queried"}
                return {"tool_calls": [{"function": {"name": "hub_read_devices", "arguments": {}}}]}
        async def run():
            transport = LiveClient()
            agent = DiscoveryAgent("http://localhost:11434", "mock", "", 20)
            try:
                result = await agent.answer("Discover available tools", [], transport.client, 60)
                self.assertFalse(agent.seen["client_receipt"]["operation_executed"])
                source = json.loads(agent.seen["mcp_result"]["content"][0]["text"])
                self.assertEqual(source["tools"][0]["inputSchema"], LEAF_SCHEMA)
                receipt = result["tool_calls"][0]
                self.assertEqual(receipt["result_kind"], "tool_catalog")
                self.assertFalse(receipt["operation_executed"])
                self.assertEqual(json.loads(receipt["response"]), agent.seen)
            finally:
                await agent.close()
                await transport.close()
        asyncio.run(run())

    def test_model_receives_contract_error_then_corrects_and_reads_history(self):
        class ScriptedAgent(Agent):
            async def round(self, messages, tools, remaining):
                outputs = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
                if not outputs:
                    args = {"args": {"tool": "hub_list_devices", "format": "context"}}
                elif "error" in outputs[-1]:
                    args = {"tool": "hub_list_devices", "args": {"include_token": False}}
                elif "devices" in outputs[-1]["content"][0]["text"]:
                    args = {"tool": "hub_list_device_events", "args": {"deviceId": "17"}}
                else:
                    return {"content": "Discovery failed" if len(outputs) < 3 else "Source event retrieved"}
                return {"content": "", "tool_calls": [{"function": {
                    "name": "hub_read_devices", "arguments": args}}]}
        async def run():
            transport = LiveClient()
            agent = ScriptedAgent("http://localhost:11434", "mock", "", 20)
            try:
                result = await agent.answer("Read the latest sensor event", [], transport.client, 60)
                self.assertEqual(result["answer"], "Source event retrieved")
                self.assertFalse(result["tool_calls"][0]["success"])
                self.assertIn("top-level", result["tool_calls"][0]["error"])
                self.assertEqual(len(transport.calls), 2)
                self.assertEqual([a["tool"] for a in transport.calls],
                                 ["hub_list_devices", "hub_list_device_events"])
            finally:
                await agent.close()
                await transport.close()
        asyncio.run(run())


class SchemaPreservationRegressions(unittest.TestCase):
    def test_catalog_json_and_secret_named_schema_properties_survive(self):
        original = catalog_result()
        before = copy.deepcopy(original)
        result = redact(original)
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["tools"][0]["inputSchema"], LEAF_SCHEMA)
        self.assertEqual(original, before)
        model_view = compact_tool_result(original)
        payload_again = json.loads(json.loads(model_view)["content"][0]["text"])
        self.assertEqual(payload_again["tools"][0]["inputSchema"], LEAF_SCHEMA)

    def test_structured_schema_is_preserved_but_actual_credentials_are_removed(self):
        source = {"inputSchema": LEAF_SCHEMA, "outputSchema": LEAF_SCHEMA,
                  "result": {"access_token": "actual-private-token", "password": "actual-password"}}
        result = redact(source)
        self.assertEqual(result["inputSchema"], LEAF_SCHEMA)
        self.assertEqual(result["outputSchema"], LEAF_SCHEMA)
        self.assertNotIn("actual-private-token", json.dumps(result))
        self.assertNotIn("actual-password", json.dumps(result))

    def test_schema_samples_and_plain_text_credentials_are_redacted_without_syntax_damage(self):
        schema = copy.deepcopy(LEAF_SCHEMA)
        schema["properties"]["access_token"]["default"] = "sample-private-key"
        schema["properties"]["access_token"]["examples"] = ["sample-other-key"]
        schema["properties"]["access_token"]["enum"] = ["none", "provided"]
        result = redact({"inputSchema": schema})
        field = result["inputSchema"]["properties"]["access_token"]
        self.assertEqual(field["type"], "string")
        self.assertEqual(field["enum"], ["none", "provided"])
        self.assertEqual(field["default"], "[REDACTED]")
        self.assertEqual(field["examples"], ["[REDACTED]"])
        fragment = '"include_token":{"type":"boolean"}'
        text = redact(fragment + ' password="private value with spaces" Authorization: Bearer private-bearer')
        self.assertIn(fragment, text)
        self.assertNotIn("private value", text)
        self.assertNotIn("private-bearer", text)

    def test_embedded_json_credentials_remain_valid_and_redacted(self):
        result = redact({"content": [{"type": "text", "text": json.dumps({
            "access_token": "actual-private-token",
            "nested": {"api_key": "actual-api-key", "authorization": "Bearer actual-bearer"},
            "devices": [{"name": "Sample Sensor", "state": False}],
        })}]})
        text = result["content"][0]["text"]
        parsed = json.loads(text)
        for secret in ("actual-private-token", "actual-api-key", "actual-bearer"):
            self.assertNotIn(secret, text)
        self.assertEqual(parsed["devices"], [{"name": "Sample Sensor", "state": False}])


if __name__ == "__main__":
    unittest.main()

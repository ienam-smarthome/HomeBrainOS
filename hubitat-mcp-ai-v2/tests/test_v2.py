"""Safety and model-led reasoning contract smoke tests for isolated v2."""
import asyncio
import json
import sys
import tempfile
import unittest

import httpx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from agent import Agent, arguments_of, compact_tool_result, model_tools
from external_hub_diagnostics import ExternalHubDiagnostics, validate_hub_url
from mcp import MCPError, ReadOnlyMCP, is_read_tool, redact


class ToolSafetyTests(unittest.TestCase):
    def test_only_native_reads(self):
        for name in (
            "hub_search_tools", "hub_get_tool_guide", "hub_list_devices",
            "hub_get_device", "hub_read_devices", "hub_read_rules",
        ):
            self.assertTrue(is_read_tool(name), name)
        for name in (
            "hub_manage_rule_machine", "hub_call_device_command",
            "hub_create_backup", "hub_reboot", "hub_shutdown",
            "hub_report_issue", "hub_test_rule", "hub_delete_device",
            "hub_get_unknown_action", "hub_read_unknown", "hub_read_rule_machine",
        ):
            self.assertFalse(is_read_tool(name), name)

    def test_restricted_tool_call_denied_before_network(self):
        async def run():
            mcp = ReadOnlyMCP("http://192.168.1.239/mcp", timeout=5)
            mcp._tools = {"hub_get_device": {"name": "hub_get_device"}}
            try:
                with self.assertRaises(MCPError):
                    await mcp.call("hub_call_device_command", {"deviceId": 1})
            finally:
                await mcp.close()
        asyncio.run(run())


    def test_streamable_http_catalog_session_and_read(self):
        calls = []
        def reply(request: httpx.Request):
            data = json.loads(request.content)
            calls.append((data.get("method"), request.headers.get("mcp-session-id")))
            name = data.get("method")
            if name == "initialize":
                return httpx.Response(200, json={
                    "jsonrpc": "2.0", "id": data["id"], "result": {
                        "protocolVersion": "2025-03-26", "capabilities": {}
                    }
                }, headers={"Mcp-Session-Id": "test-session"})
            if name == "notifications/initialized":
                return httpx.Response(202)
            if name == "tools/list":
                return httpx.Response(200, json={
                    "jsonrpc": "2.0", "id": data["id"], "result": {
                        "tools": [
                            {"name": "hub_get_info", "description": "Info",
                             "inputSchema": {"type": "object", "properties": {}}},
                            {"name": "hub_call_device_command", "description": "Control"}
                        ]
                    }
                })
            if name == "tools/call":
                body = json.dumps({
                    "jsonrpc": "2.0", "id": data["id"], "result": {
                        "content": [{"type": "text", "text": '{"password":"private-value"}'}]
                    }
                })
                return httpx.Response(200, content="\n".join(["event: message", "data: "+body, "", ""]),
                                      headers={"Content-Type": "text/event-stream"})
            raise AssertionError("Unexpected HTTP method")
        async def run():
            mcp = ReadOnlyMCP("http://192.168.1.239/mcp")
            await mcp._client.aclose()
            mcp._client = httpx.AsyncClient(transport=httpx.MockTransport(reply))
            try:
                catalog = await mcp.list_tools()
                self.assertEqual([item["name"] for item in catalog], ["hub_get_info"])
                result = await mcp.call("hub_get_info", {})
                self.assertNotIn("private-value", json.dumps(result))
                with self.assertRaises(MCPError):
                    await mcp.call("hub_call_device_command", {"deviceId": "7828"})
                self.assertEqual([v[0] for v in calls],
                                 ["initialize", "notifications/initialized", "tools/list",
                                  "tools/call"])
                self.assertEqual(calls[2][1], "test-session")
            finally:
                await mcp.close()
        asyncio.run(run())

    def test_gateway_rejects_write_and_unknown_leaf_before_network(self):
        async def run():
            mcp = ReadOnlyMCP("http://192.168.1.239/mcp")
            mcp._initialized = True
            mcp._tools = {"hub_read_devices": {"name": "hub_read_devices"}}
            try:
                for leaf in ("hub_call_device_command", "hub_get_unknown_action",
                             "hub_list_files", None):
                    with self.assertRaises(MCPError):
                        await mcp.call("hub_read_devices", {"tool": leaf, "args": {}})
            finally:
                await mcp.close()
        asyncio.run(run())

    def test_schemas_not_derived_from_name(self):
        tools = model_tools([{
            "name": "hub_read_devices", "description": "Gateway",
            "inputSchema": {
                "type": "object", "properties": {"tool": {"type": "string"}}
            },
        }])
        self.assertEqual(tools[0]["function"]["parameters"]["properties"],
                         {"tool": {"type": "string"}})

    def test_bad_arguments_are_invalid_not_executed(self):
        self.assertIn("_invalid_arguments", arguments_of({
            "function": {"name": "hub_get_device", "arguments": "{broken"}
        }))

    def test_recorder_validates_lan(self):
        self.assertEqual(validate_hub_url("http://192.168.1.239"),
                         "http://192.168.1.239")
        for bad in ("http://example.com", "https://192.168.1.239",
                    "http://127.0.0.1", "http://192.168.1.239/private"):
            with self.assertRaises(ValueError):
                validate_hub_url(bad)

    def test_redact_token_value_nested_and_text(self):
        item = {"output": [{"api_key": "example-key", "password": "example-password"}],
                "authorization": "Bearer something-secret",
                "plain": "access_token=example-token"}
        result = redact(item)
        self.assertNotIn("example-key", json.dumps(result))
        self.assertNotIn("example-password", json.dumps(result))
        self.assertNotIn("example-token", json.dumps(result))
        self.assertIn("[REDACTED]", json.dumps(result))

    def test_large_result_explicitly_truncated(self):
        result = compact_tool_result({"content": "x" * 1000}, max_chars=40)
        self.assertTrue(json.loads(result)["truncated"])


class AgentContractTests(unittest.TestCase):
    def test_model_selects_real_tools_and_answers_without_preplan(self):
        class FakeMCP:
            def __init__(self):
                self.calls = []
            async def list_tools(self):
                return [{"name": "hub_get_device", "description": "Read device",
                         "inputSchema": {"type": "object", "properties": {
                             "deviceId": {"type": "integer"}}}}]
            async def call(self, name, args):
                self.calls.append((name, args))
                return {"content": [{"type": "text", "text": '{"state":"off"}'}]}
        class FakeAgent(Agent):
            async def round(self, messages, tools, remaining):
                if not any(item.get("role") == "tool" for item in messages):
                    return {"role": "assistant", "content": "",
                            "tool_calls": [{"function": {
                                "name": "hub_get_device", "arguments": {"deviceId": 7828}
                            }}]}
                return {"role": "assistant",
                        "content": "Device 7828 reported off; cause not established."}
        async def run():
            mcp = FakeMCP()
            agent = FakeAgent("http://localhost:11434", "mock", "", 20)
            try:
                answer = await agent.answer("What happened?", [], mcp, 60)
                self.assertTrue(answer["success"])
                self.assertEqual(answer["rounds"], 2)
                self.assertEqual(mcp.calls, [("hub_get_device", {"deviceId": 7828})])
                self.assertEqual(len(answer["tool_calls"]), 1)
                self.assertEqual(answer["tool_calls"][0]["arguments"], {"deviceId": 7828})
                self.assertIn("cause not established", answer["answer"])
                self.assertEqual(json.loads(answer["tool_calls"][0]["response"]),
                                 {"content": [{"type": "text", "text": '{"state":"off"}'}]})
                async def fail_round(messages, tools, remaining):
                    if any(item.get("role") == "tool" for item in messages):
                        raise RuntimeError("Model API returned HTTP 503")
                    return {"tool_calls": [{"function": {
                        "name": "hub_get_device", "arguments": {"deviceId": 7828}}}]}
                agent.round = fail_round
                failed = await agent.answer("What happened?", [], mcp, 60)
                self.assertFalse(failed["success"])
                self.assertEqual(failed["error"], "model")
                self.assertEqual(failed["tool_calls"][0]["response"],
                                 answer["tool_calls"][0]["response"])
            finally:
                await agent.close()
        asyncio.run(run())

    def test_diagnostics_sqlite_is_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ExternalHubDiagnostics(
                enabled=True, hub_url="http://192.168.1.239",
                path=Path(tmp) / "diag.sqlite3",
            )
            recorder._initialize()
            self.assertTrue((Path(tmp) / "diag.sqlite3").exists())
            self.assertEqual(recorder.history(1)["source_sample_count"], 0)


if __name__ == "__main__":
    unittest.main()

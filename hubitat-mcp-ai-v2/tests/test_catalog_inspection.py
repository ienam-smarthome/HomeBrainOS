"""Fictional live-catalog recovery tests; no real Hubitat or device operations."""
import asyncio
import json
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent, inspect_native_catalog, validate_catalog_inspection_args
from investigation_review import is_read_only_review_tool, read_only_review_catalog
from mcp import MCPClient, MCPContractError


def gateway(name, names):
    return {
        "name": name,
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "enum": names},
                "args": {"type": "object"},
            },
            "additionalProperties": False,
        },
    }


class CatalogInspectionTests(unittest.TestCase):
    def test_flat_schema_is_exact_and_mcp_call_not_required(self):
        schema = {
            "type": "object",
            "properties": {
                "deviceId": {"type": "integer"},
                "command": {"type": "string"},
                "parameters": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["deviceId", "command"],
        }
        catalog = [
            {"name": "hub_call_device_command", "inputSchema": schema,
             "description": "Native device command", "annotations": {"readOnlyHint": False}},
            {"name": "hub_get_info", "inputSchema": {"type": "object"}},
        ]
        item = inspect_native_catalog(catalog, "hub_call_device_command")
        self.assertTrue(item["direct_top_level_exposed"])
        self.assertEqual(item["direct_definition"]["inputSchema"], schema)
        self.assertEqual(item["gateway_candidates_from_live_schema"], [])
        self.assertFalse(item["write_authorization_verified"])
        self.assertEqual(item["effective_client_write_permission"], "unverified")
        self.assertEqual(inspect_native_catalog(catalog)["top_level_tools"],
                         ["hub_call_device_command", "hub_get_info"])
        # The separate search helper is absent: it does not prove command absence.
        missing = inspect_native_catalog(catalog, "hub_search_tools")
        self.assertFalse(missing["direct_top_level_exposed"])
        self.assertFalse(missing["gateway_candidates_from_live_schema"])
        self.assertTrue(inspect_native_catalog(catalog, "hub_call_device_command")[
            "direct_top_level_exposed"])

    def test_gateway_leaf_is_only_a_candidate_until_gateway_catalog_read(self):
        catalog = [gateway("hub_manage_devices", ["hub_call_device_command"]),
                   gateway("hub_read_devices", ["hub_get_device"])]
        item = inspect_native_catalog(catalog, "hub_call_device_command")
        self.assertFalse(item["direct_top_level_exposed"])
        self.assertEqual([g["name"] for g in item["gateway_candidates_from_live_schema"]],
                         ["hub_manage_devices"])
        self.assertFalse(item["gateway_candidates_from_live_schema"][0][
            "full_leaf_schema_retrieved"])
        self.assertEqual(item["effective_client_write_permission"], "unverified")
        self.assertFalse(inspect_native_catalog(catalog, "some_other_tool")[
            "gateway_candidates_from_live_schema"])

    def test_local_tool_is_read_only_and_rejects_invalid_args(self):
        self.assertTrue(is_read_only_review_tool("homebrain_inspect_mcp_catalog"))
        self.assertEqual(validate_catalog_inspection_args({}), "")
        self.assertEqual(validate_catalog_inspection_args({"name": " hub_get_info "}),
                         "hub_get_info")
        for invalid in ({"extra": 1}, {"name": 9}, {"name": "x" * 129}):
            with self.assertRaises(MCPContractError):
                validate_catalog_inspection_args(invalid)
        catalog = [{
            "type": "function",
            "function": {"name": "homebrain_inspect_mcp_catalog"},
        }]
        self.assertEqual(len(read_only_review_catalog(catalog)), 1)

    def test_model_recovers_from_absent_search_helper_without_any_write(self):
        calls = []
        catalog = [
            gateway("hub_read_devices", ["hub_get_device"]),
            gateway("hub_manage_devices", ["hub_call_device_command"]),
            {"name": "hub_get_tool_guide", "inputSchema": {"type": "object"}},
        ]
        schema = {
            "type": "object",
            "properties": {
                "deviceId": {"type": "integer"},
                "command": {"type": "string"},
                "parameters": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["deviceId", "command"],
            "additionalProperties": False,
        }

        def reply(request):
            data = json.loads(request.content)
            if data["method"] == "tools/list":
                return httpx.Response(200, json={
                    "jsonrpc": "2.0", "id": data["id"],
                    "result": {"tools": catalog},
                })
            self.assertEqual(data["method"], "tools/call")
            calls.append(data["params"])
            # The only native tools/call is explicit read-only gateway discovery.
            self.assertEqual(data["params"]["name"], "hub_manage_devices")
            self.assertEqual(data["params"]["arguments"], {})
            payload = {
                "mode": "catalog",
                "gateway": "hub_manage_devices",
                "tools": [{"name": "hub_call_device_command", "inputSchema": schema}],
            }
            return httpx.Response(200, json={
                "jsonrpc": "2.0", "id": data["id"],
                "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
            })

        class Model(Agent):
            def __init__(self):
                super().__init__("http://localhost:11434", "mock", "", 20)
                self.turn = 0

            async def round(self, messages, tools, remaining):
                self.turn += 1
                if self.turn == 1:
                    return {"tool_calls": [{"function": {
                        "name": "hub_search_tools",
                        "arguments": {"query": "device management"},
                    }}]}
                if self.turn == 2:
                    missing = json.loads(messages[-1]["content"])
                    testcase.assertEqual(missing["result_kind"], "unavailable_tool")
                    testcase.assertFalse(missing["operation_executed"])
                    testcase.assertEqual(missing["client_catalog_scope"][
                        "queried_name"], "hub_search_tools")
                    return {"tool_calls": [{"function": {
                        "name": "homebrain_inspect_mcp_catalog",
                        "arguments": {"name": "hub_call_device_command"},
                    }}]}
                if self.turn == 3:
                    inspected = json.loads(messages[-1]["content"])["local_mcp_catalog"]
                    testcase.assertFalse(inspected["direct_top_level_exposed"])
                    testcase.assertEqual(
                        inspected["gateway_candidates_from_live_schema"][0]["name"],
                        "hub_manage_devices")
                    return {"tool_calls": [{"function": {
                        "name": "hub_manage_devices", "arguments": {},
                    }}]}
                decoded = json.loads(messages[-1]["content"])
                testcase.assertFalse(decoded["client_receipt"]["operation_executed"])
                leafs = json.loads(decoded["mcp_result"]["content"][0]["text"])["tools"]
                testcase.assertEqual(leafs[0]["inputSchema"], schema)
                return {"content": "Gateway advertises a command; actual write permission is unknown."}

        testcase = self

        async def run():
            remote = MCPClient("http://192.168.1.10/mcp")
            remote._initialized = True
            await remote._client.aclose()
            remote._client = httpx.AsyncClient(transport=httpx.MockTransport(reply))
            model = Model()
            try:
                response = await model.answer(
                    "Inspect native tool catalog; do not change anything.",
                    [], remote, 60, enable_source_review=False,
                    enable_final_claim_audit=False,
                )
                self.assertTrue(response["success"])
                self.assertEqual(response["rounds"], 4)
                self.assertEqual(len(response["tool_calls"]), 3)
                self.assertEqual(response["tool_calls"][0]["result_kind"], "unavailable_tool")
                self.assertEqual(response["tool_calls"][1]["result_kind"], "local_catalog_read")
                self.assertFalse(response["tool_calls"][1]["operation_executed"])
                self.assertEqual(response["tool_calls"][2]["result_kind"], "tool_catalog")
                self.assertFalse(response["tool_calls"][2]["operation_executed"])
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0]["arguments"], {})
            finally:
                await model.close()
                await remote.close()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

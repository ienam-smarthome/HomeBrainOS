"""Contract recovery: live schemas are returned without any automatic retry.

Synthetic cases intentionally contain no household targets, credentials or
live MCP requests. They test the existing model-led call path, not model IQ.
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent, _SKILL, live_contract_error_context
from mcp import MCPContractError, _validate_arguments


class ContractRecoveryTests(unittest.TestCase):
    def test_direct_read_contract_recovery_is_selected_by_model(self):
        name = "synthetic_read_history"
        schema = {
            "type": "object",
            "properties": {"sourceId": {"type": "string", "description": "Exact source ID"}},
            "required": ["sourceId"],
            "additionalProperties": False,
        }

        class SyntheticMCP:
            def __init__(self):
                self.attempts = []
                self.executed = []
            async def list_tools(self, refresh=False):
                return [{"name": name, "inputSchema": schema, "description": "Read-only history"}]
            async def call(self, tool, args):
                self.attempts.append((tool, args.copy()))
                _validate_arguments(args, schema)
                self.executed.append(args.copy())
                return {"content": [{"type": "text",
                                    "text": json.dumps({"events": [{"value": "idle"}]})}]}

        class SyntheticModel(Agent):
            def __init__(self):
                self.received = []
            async def round(self, messages, tools, remaining):
                self.received.append(messages)
                if len(self.received) == 1:
                    return {"tool_calls": [{"function": {"name": name,
                           "arguments": {"sourceId": 19}}}]}
                if len(self.received) == 2:
                    error = json.loads(messages[-1]["content"])
                    assert error["result_kind"] == "contract_error"
                    assert error["operation_executed"] is False
                    assert error["live_input_contract"]["inputSchema"]["properties"]["sourceId"]["type"] == "string"
                    return {"tool_calls": [{"function": {"name": name,
                           "arguments": {"sourceId": "19"}}}]}
                return {"content": "A synthetic idle event was returned; the earlier read failed."}

        async def scenario():
            mcp, model = SyntheticMCP(), SyntheticModel()
            response = await model.answer("Inspect a fictional source", [], mcp, 30)
            self.assertTrue(response["success"])
            self.assertEqual(response["rounds"], 3)
            self.assertEqual(len(response["tool_calls"]), 2)
            failed, successful = response["tool_calls"]
            self.assertFalse(failed["success"])
            self.assertEqual(failed["result_kind"], "contract_error")
            self.assertIs(failed["operation_executed"], False)
            self.assertEqual(json.loads(failed["response"])["live_input_contract"]["tool"], name)
            self.assertTrue(successful["success"])
            self.assertEqual(mcp.executed, [{"sourceId": "19"}])
            self.assertEqual(len(mcp.attempts), 2)
            self.assertIn("the earlier read failed", response["answer"])
            self.assertIn("Recover from read-only tool contract errors",
                          model.received[0][0]["content"])
        asyncio.run(scenario())

    def test_gateway_leaf_error_includes_selected_live_leaf_contract(self):
        gateway = "synthetic_gateway"
        gateway_schema = {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "enum": ["read_history"]},
                "args": {"type": "object"},
            },
            "required": ["tool", "args"],
            "additionalProperties": False,
        }
        leaf = {"name": "read_history", "description": "Synthetic read",
                "inputSchema": {"type": "object",
                    "properties": {"recordId": {"type": "string"}},
                    "required": ["recordId"], "additionalProperties": False}}

        class GatewayMCP:
            def __init__(self):
                self.executed = []
            async def list_tools(self, refresh=False):
                return [{"name": gateway, "inputSchema": gateway_schema,
                         "description": "Synthetic catalogue"}]
            async def gateway_leaf_schema(self, tool, subtool):
                assert (tool, subtool) == (gateway, "read_history")
                return leaf, False
            @staticmethod
            def validate_leaf_arguments(definition, args):
                try:
                    _validate_arguments(args, definition["inputSchema"])
                except MCPContractError as exc:
                    raise MCPContractError(
                        "Leaf arguments violate their live input schema: " + str(exc)
                    ) from None
            async def call(self, name, args):
                self.executed.append((name, args))
                return {"content": [{"type": "text", "text": '{"checked":true}'}]}

        class GatewayModel(Agent):
            def __init__(self):
                self.round_index = 0
            async def round(self, messages, tools, remaining):
                self.round_index += 1
                if self.round_index == 1:
                    return {"tool_calls": [{"function": {"name": gateway,
                         "arguments": {"tool": "read_history",
                                       "args": {"recordId": 19}}}}]}
                if self.round_index == 2:
                    result = json.loads(messages[-1]["content"])
                    assert result["live_input_contract"]["schema_scope"] == "leaf"
                    assert result["live_input_contract"]["leaf"] == "read_history"
                    assert result["live_input_contract"]["inputSchema"]["properties"]["recordId"]["type"] == "string"
                    return {"tool_calls": [{"function": {"name": gateway,
                         "arguments": {"tool": "read_history",
                                       "args": {"recordId": "19"}}}}]}
                return {"content": "The fictional history was read."}

        async def scenario():
            model, mcp = GatewayModel(), GatewayMCP()
            result = await model.answer("Read fictional history", [], mcp, 30)
            self.assertTrue(result["success"])
            self.assertEqual(result["rounds"], 3)
            self.assertEqual(len(result["tool_calls"]), 2)
            self.assertFalse(result["tool_calls"][0]["success"])
            self.assertTrue(result["tool_calls"][1]["success"])
            self.assertEqual(mcp.executed, [(gateway, {
                "tool": "read_history", "args": {"recordId": "19"}})])
        asyncio.run(scenario())

    def test_failure_does_not_trigger_automatic_write_retry_or_claim_success(self):
        name = "synthetic_write"
        schema = {"type": "object",
                  "properties": {"ruleId": {"type": "string"}},
                  "required": ["ruleId"], "additionalProperties": False}

        class WriteMCP:
            def __init__(self):
                self.executed = 0
            async def list_tools(self, refresh=False):
                return [{"name": name, "inputSchema": schema}]
            async def call(self, name, args):
                _validate_arguments(args, schema)
                self.executed += 1
                return {"content": [{"type": "text", "text": "write executed"}]}

        class Model(Agent):
            def __init__(self):
                self.count = 0
            async def round(self, messages, tools, remaining):
                self.count += 1
                if self.count == 1:
                    return {"tool_calls": [{"function": {"name": name,
                            "arguments": {"ruleId": 19}}}]}
                return {"content": "The modification was not performed. The argument contract failed."}

        async def scenario():
            mcp = WriteMCP()
            result = await Model().answer("Propose fictional update", [], mcp, 30)
            self.assertEqual(mcp.executed, 0)
            self.assertEqual(result["rounds"], 2)
            self.assertEqual(len(result["tool_calls"]), 1)
            self.assertFalse(result["tool_calls"][0]["success"])
            self.assertFalse(result["tool_calls"][0]["operation_executed"])
            self.assertIn("not performed", result["answer"])
        asyncio.run(scenario())

    def test_contract_excerpt_from_original_catalog_is_bounded_and_redacted(self):
        source_schema = {
            "type": "object",
            "properties": {
                "recordId": {"type": "string"},
                "api_token": {"type": "string", "default": "synthetic-secret-ABC"},
                "verbose": {"type": "string", "description": "x" * 12000},
            },
            "required": ["recordId"],
        }
        catalog = [{"name": "synthetic_read", "inputSchema": source_schema}]
        before = json.dumps(catalog)
        context = live_contract_error_context(
            catalog, "synthetic_read",
            "Arguments violate the live input schema at recordId (type); inspect inputSchema",
        )
        self.assertEqual(context["schema_scope"], "direct")
        self.assertEqual(context["inputSchema"]["properties"]["recordId"]["type"], "string")
        self.assertIn("_excerpt", context["inputSchema"])
        self.assertLess(len(json.dumps(context)), 5500)
        self.assertNotIn("synthetic-secret-ABC", json.dumps(context))
        self.assertEqual(json.dumps(catalog), before)
        self.assertIsNone(live_contract_error_context(catalog, "unknown", "irrelevant"))
        small = live_contract_error_context(catalog, "synthetic_read",
                      "Arguments violate the live input schema at recordId (type)")
        self.assertEqual(small["tool"], "synthetic_read")

    def test_readable_live_contract_does_not_prove_a_failed_read(self):
        self.assertIn("Do not treat a failed configuration/history read as checked", _SKILL)
        self.assertIn("never automatically or", _SKILL.lower())
        self.assertIn("execution was prevented", _SKILL)


if __name__ == "__main__":
    unittest.main()

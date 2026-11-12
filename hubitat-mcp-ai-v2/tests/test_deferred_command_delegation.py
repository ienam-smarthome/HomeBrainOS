"""Native deferred device command delegation: synthetic MCP contract acceptance.

This only proves v2 can send an *advertised* driver command and read a
separate pending-state receipt. It does not establish cloud-model tool choice,
live write permission, timer durability, or router enforcement.
No household names, identifiers or network endpoints.
"""
import asyncio
import json
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from agent import Agent
from mcp import MCPClient


DEVICE_ID = 17
PENDING_AT = "2026-11-12T21:15:00Z"  # fictional source time


class NativeDeferredCommandTests(unittest.TestCase):
    def test_model_selected_driver_timer_uses_one_write_and_fresh_readback(self):
        sent = []
        gateway_schema = lambda leaves: {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "enum": leaves},
                "args": {"type": "object"},
            },
            "additionalProperties": False,
        }
        leaf_defs = {
            "hub_get_device": {
                "type": "object", "properties": {"deviceId": {"type": "integer"}},
                "required": ["deviceId"], "additionalProperties": False,
            },
            "hub_get_device_attribute": {
                "type": "object",
                "properties": {
                    "deviceId": {"type": "integer"},
                    "attribute": {"type": "string"},
                },
                "required": ["deviceId", "attribute"], "additionalProperties": False,
            },
            "hub_call_device_command": {
                "type": "object",
                "properties": {
                    "deviceId": {"type": "integer"},
                    "command": {"type": "string"},
                    "parameters": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["deviceId", "command"], "additionalProperties": False,
            },
        }
        gateways = {
            "hub_read_devices": ["hub_get_device", "hub_get_device_attribute"],
            "hub_manage_devices": ["hub_call_device_command"],
        }
        catalog = [
            {
                "name": gateway, "inputSchema": gateway_schema(leaves),
                "annotations": {"readOnlyHint": gateway == "hub_read_devices"},
            }
            for gateway, leaves in gateways.items()
        ]

        def reply(request):
            rpc = json.loads(request.content)
            if rpc["method"] == "tools/list":
                return httpx.Response(200, json={
                    "jsonrpc": "2.0", "id": rpc["id"],
                    "result": {"tools": catalog},
                })
            self.assertEqual(rpc["method"], "tools/call")
            gateway = rpc["params"]["name"]
            args = rpc["params"]["arguments"]
            sent.append((gateway, args))
            if not args:
                payload = {
                    "mode": "catalog", "gateway": gateway,
                    "tools": [
                        {"name": leaf, "inputSchema": leaf_defs[leaf]}
                        for leaf in gateways[gateway]
                    ],
                }
            elif gateway == "hub_read_devices" and args["tool"] == "hub_get_device":
                payload = {
                    "id": DEVICE_ID, "label": "Test Network Gate",
                    "supportedCommands": [
                        {"name": "deferDisconnect", "parameters": ["minutes"]}
                    ],
                    "currentStates": {"pendingUntil": "none"},
                }
            elif gateway == "hub_manage_devices" and args["tool"] == "hub_call_device_command":
                self.assertEqual(args["args"], {
                    "deviceId": DEVICE_ID,
                    "command": "deferDisconnect",
                    "parameters": ["5"],
                })
                payload = {"success": True, "dispatched": True}
            elif gateway == "hub_read_devices" and args["tool"] == "hub_get_device_attribute":
                self.assertEqual(args["args"], {
                    "deviceId": DEVICE_ID, "attribute": "pendingUntil"
                })
                payload = {"deviceId": DEVICE_ID, "attribute": "pendingUntil",
                           "value": PENDING_AT}
            else:
                self.fail(f"Unexpected synthetic MCP request: {gateway} {args}")
            return httpx.Response(200, json={
                "jsonrpc": "2.0", "id": rpc["id"],
                "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
            })

        class ScriptedModel(Agent):
            def __init__(self):
                super().__init__("http://localhost:11434", "scripted", "", 20)
                self.round_count = 0

            async def round(self, messages, tools, remaining):
                self.round_count += 1
                if self.round_count == 1:
                    gateway, leaf, args = "hub_read_devices", "hub_get_device", {
                        "deviceId": DEVICE_ID}
                elif self.round_count == 2:
                    self_test.assertIn("deferDisconnect", messages[-1]["content"])
                    gateway, leaf, args = "hub_manage_devices", "hub_call_device_command", {
                        "deviceId": DEVICE_ID, "command": "deferDisconnect",
                        "parameters": ["5"]}
                elif self.round_count == 3:
                    self_test.assertIn('"dispatched"', messages[-1]["content"])
                    gateway, leaf, args = "hub_read_devices", "hub_get_device_attribute", {
                        "deviceId": DEVICE_ID, "attribute": "pendingUntil"}
                else:
                    self_test.assertIn(PENDING_AT, messages[-1]["content"])
                    return {"content": "Device accepted the command; pending deadline verified.",
                            "tool_calls": []}
                return {"content": "Inspecting the advertised native device capability.",
                        "tool_calls": [{"function": {"name": gateway, "arguments": {
                            "tool": leaf, "args": args,
                        }}}]}

        self_test = self

        async def run():
            remote = MCPClient("http://192.168.1.10/mcp")
            remote._initialized = True
            await remote._client.aclose()
            remote._client = httpx.AsyncClient(transport=httpx.MockTransport(reply))
            model = ScriptedModel()
            decisions = []

            async def before_call(name, args, explanation):
                decisions.append((name, args))

            try:
                result = await model.answer(
                    "Schedule Test Network Gate to disconnect after five minutes",
                    [], remote, 60, before_call=before_call,
                    enable_source_review=False, enable_final_claim_audit=False,
                )
                self.assertTrue(result["success"])
                self.assertEqual(model.round_count, 4)
                self.assertEqual(len(result["tool_calls"]), 3)
                self.assertTrue(all(r["success"] for r in result["tool_calls"]))
                domain_calls = [(g, a) for g, a in sent if a.get("tool")]
                self.assertEqual([a["tool"] for _, a in domain_calls], [
                    "hub_get_device", "hub_call_device_command", "hub_get_device_attribute"
                ])
                self.assertEqual(sum(a["tool"] == "hub_call_device_command"
                                     for _, a in domain_calls), 1)
                self.assertFalse(any("rule" in g.lower() for g, _ in sent))
                self.assertEqual(len(decisions), 3)
                self.assertEqual(
                    json.loads(result["tool_calls"][-1]["response"])["content"][0]["text"],
                    json.dumps({"deviceId": DEVICE_ID, "attribute": "pendingUntil",
                                "value": PENDING_AT}),
                )
            finally:
                await model.close()
                await remote.close()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

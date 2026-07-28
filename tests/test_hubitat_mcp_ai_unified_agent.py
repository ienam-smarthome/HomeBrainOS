from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return [
            MCPTool(
                "set_switch",
                "Set a switch",
                {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string"},
                        "state": {"type": "string"},
                    },
                    "required": ["device_id", "state"],
                },
            )
        ]

    async def get_cached_devices(self):
        return [
            {
                "id": "42",
                "label": "Couch Lamp",
                "room": "Lounge",
                "capabilities": ["Switch"],
            }
        ]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return MCPToolResult(name, arguments, {}, "ok", {"state": "on"})


def test_live_manifest_contains_exact_device_context():
    agent = UnifiedMCPAgent(FakeMCP(), "key", "model")
    instruction = asyncio.run(agent._build_system_instruction())
    asyncio.run(agent.close())
    assert "'Couch Lamp' | ID: 42 | Room: Lounge" in instruction


def test_native_function_call_executes_and_returns_final_text():
    mcp = FakeMCP()
    agent = UnifiedMCPAgent(mcp, "key", "model")
    responses = iter(
        [
            {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "set_switch",
                                        "args": {"device_id": "42", "state": "on"},
                                    }
                                }
                            ],
                        }
                    }
                ]
            },
            {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": "The couch lamp is on."}],
                        }
                    }
                ]
            },
        ]
    )

    async def fake_generate(_payload):
        return next(responses)

    agent._generate = fake_generate
    answer = asyncio.run(agent.process_user_request("Turn on the couch lamp"))
    asyncio.run(agent.close())

    assert answer == "The couch lamp is on."
    assert mcp.calls == [("set_switch", {"device_id": "42", "state": "on"})]

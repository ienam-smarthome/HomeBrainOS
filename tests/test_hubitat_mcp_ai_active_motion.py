from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_routine import FastFallbackRouter  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


class FakeMCP:
    async def call_tool(self, name, arguments):
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={
                "devices": [
                    {"id": "1", "label": "Kitchen Motion", "currentStates": {"motion": "active"}},
                    {"id": "2", "label": "Hall Motion", "currentStates": {"motion": "inactive"}},
                ]
            },
            is_error=False,
        )

    async def get_tool(self, name):
        return None

    async def supported_arguments(self, name, desired):
        return desired


def test_active_motion_question_gets_verified_evidence():
    result = asyncio.run(FastFallbackRouter(FakeMCP()).answer("Which motion sensors are active?"))
    assert result["intent"] == "fallback-active-motion"
    assert result["success"] is True
    assert "Kitchen Motion" in result["message"]
    assert "Hall Motion" not in result["message"]

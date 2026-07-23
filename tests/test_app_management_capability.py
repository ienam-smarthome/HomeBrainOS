from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from app_management_capability import (  # noqa: E402
    inspect_app_management_capability,
    install_app_management_capability,
    is_app_capability_query,
)
from mcp_client import MCPTool  # noqa: E402


class FakeMCP:
    def __init__(self, names):
        self.names = names

    async def list_tools(self, refresh=False):
        return [MCPTool(name, "", {}) for name in self.names]

    async def gateway_map(self, refresh=False):
        return {}


def test_query_matching():
    assert is_app_capability_query("Can you disable Hubitat apps?")
    assert is_app_capability_query("Check app management capability")
    assert not is_app_capability_query("List automation rules")


def test_detects_complete_app_contract():
    result = asyncio.run(
        inspect_app_management_capability(
            FakeMCP(["hub_list_apps", "hub_set_app_disabled"])
        )
    )
    assert result["inventory_supported"] is True
    assert result["write_supported"] is True
    assert result["full_control_supported"] is True


def test_reports_missing_write_without_guessing():
    result = asyncio.run(inspect_app_management_capability(FakeMCP(["hub_list_apps"])))
    assert result["inventory_supported"] is True
    assert result["write_supported"] is False
    assert "app enable/disable write operation" in result["missing"]


def test_terminal_diagnostic_does_not_call_a_write():
    client = FakeMCP(["hub_list_apps"])

    async def fallback(_request):
        return {"route": "fallback"}

    app = SimpleNamespace(mcp=client, ask=fallback)
    install_app_management_capability(app)
    answer = asyncio.run(app.ask(SimpleNamespace(query="Can you disable Hubitat apps?")))
    assert answer["route"] == "mcp-app-capability"
    assert answer["success"] is True
    assert "no app enable/disable write operation" in answer["message"]

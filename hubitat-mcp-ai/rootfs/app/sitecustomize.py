"""Runtime compatibility fix for MCP servers returning text plus structuredContent.

Python imports ``sitecustomize`` automatically during interpreter startup.  Install the
patch before HomeBrain constructs its MCP client so every tool consumer receives the
server's authoritative structured payload in ``MCPToolResult.data`` while preserving the
human-readable text in ``MCPToolResult.text``.
"""

from __future__ import annotations

from typing import Any

from mcp_client import HubitatMCPClient, MCPToolResult


_ORIGINAL_CALL_TOOL = HubitatMCPClient.call_tool


async def _call_tool_with_structured_data(
    self: HubitatMCPClient,
    name: str,
    arguments: dict[str, Any] | None = None,
) -> MCPToolResult:
    result = await _ORIGINAL_CALL_TOOL(self, name, arguments)
    raw = result.raw if isinstance(result.raw, dict) else {}
    structured = raw.get("structuredContent")
    if structured is None:
        return result
    return MCPToolResult(
        name=result.name,
        arguments=result.arguments,
        raw=result.raw,
        text=result.text,
        data=structured,
        is_error=result.is_error,
    )


if not getattr(HubitatMCPClient.call_tool, "_homebrain_structured_result_patch", False):
    _call_tool_with_structured_data._homebrain_structured_result_patch = True  # type: ignore[attr-defined]
    HubitatMCPClient.call_tool = _call_tool_with_structured_data

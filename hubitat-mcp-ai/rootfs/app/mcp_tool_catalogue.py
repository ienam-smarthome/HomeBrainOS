from __future__ import annotations

from typing import Any

from app_management_capability import install_app_management_capability


async def build_mcp_tool_catalogue(
    client: Any,
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    """Build a user-facing view of core and gateway-contained MCP tools."""
    tools = await client.list_tools(refresh=refresh)
    visible_by_name = {tool.name: tool for tool in tools}
    gateway_map = (
        await client.gateway_map(refresh=refresh)
        if hasattr(client, "gateway_map")
        else {}
    )

    gateways: dict[str, list[str]] = {}
    for hidden, gateway in gateway_map.items():
        gateways.setdefault(gateway, []).append(hidden)

    gateway_rows: list[dict[str, Any]] = []
    for gateway in sorted(gateways):
        tool = visible_by_name.get(gateway)
        names = sorted(set(gateways[gateway]))
        gateway_rows.append(
            {
                "gateway": gateway,
                "count": len(names),
                "tools": names,
                "description": str(getattr(tool, "description", "") or ""),
                "read_only": gateway.startswith("hub_read_"),
            }
        )

    core = sorted(
        tool.name
        for tool in tools
        if not tool.name.startswith(("hub_read_", "hub_manage_"))
    )
    hidden = sorted(gateway_map)
    underlying = sorted(set(core) | set(hidden))

    return {
        "success": True,
        "server": dict(getattr(client, "server_info", {}) or {}),
        "visible_count": len(tools),
        "core_count": len(core),
        "gateway_count": len(gateway_rows),
        "hidden_count": len(hidden),
        "underlying_count": len(underlying),
        "core_tools": core,
        "gateways": gateway_rows,
        "all_underlying_tools": underlying,
        "note": (
            "Gateway mode keeps the model prompt compact. Hidden tools remain callable "
            "through their category gateway and are translated automatically by HomeBrain."
        ),
    }


def install_mcp_tool_catalogue(application: Any, client: Any) -> None:
    """Expose a readable catalogue and app-management capability diagnostic."""

    @application.app.get("/api/mcp-tool-catalogue")
    async def mcp_tool_catalogue(refresh: bool = False) -> dict[str, Any]:
        return await build_mcp_tool_catalogue(client, refresh=refresh)

    install_app_management_capability(application)

    # Keep the runtime UI version aligned with the Home Assistant manifest for this
    # diagnostic-only release. This runs after entrypoint composition is complete.
    @application.app.on_event("startup")
    async def apply_app_capability_release_version() -> None:
        application.VERSION = "0.10.56"
        application.app.version = "0.10.56"


__all__ = ["build_mcp_tool_catalogue", "install_mcp_tool_catalogue"]

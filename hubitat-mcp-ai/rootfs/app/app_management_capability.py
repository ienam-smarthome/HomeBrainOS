from __future__ import annotations

import re
import time
from typing import Any, Awaitable, Callable

from presenter import display_payload, safe_debug

AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]
_QUERY_RE = re.compile(
    r"\b(?:check|show|test|diagnose|what(?:'s| is)|can you|does (?:the )?mcp)\b.*\b(?:app|apps|application|applications)\b.*\b(?:capabilit|support|manage|management|enable|disable|control)|\bcan (?:you|homebrain) (?:enable|disable|manage|control) (?:hubitat )?apps?\b",
    re.IGNORECASE,
)

INVENTORY_TOOLS = {
    "hub_list_apps", "hub_read_apps", "hub_get_apps",
    "hub_list_applications", "hub_read_applications",
}
DETAIL_TOOLS = {
    "hub_get_app", "hub_read_app", "hub_get_application", "hub_read_application",
}
WRITE_TOOLS = {
    "hub_set_app_disabled", "hub_set_app_enabled", "hub_enable_app",
    "hub_disable_app", "hub_update_app", "hub_set_application_disabled",
    "hub_set_application_enabled",
}


def is_app_capability_query(query: str) -> bool:
    return bool(_QUERY_RE.search(str(query or "")))


async def inspect_app_management_capability(client: Any, *, refresh: bool = True) -> dict[str, Any]:
    tools = await client.list_tools(refresh=refresh)
    visible = {str(tool.name) for tool in tools}
    descriptions = {str(tool.name): str(getattr(tool, "description", "") or "") for tool in tools}
    gateway_map = await client.gateway_map(refresh=refresh) if hasattr(client, "gateway_map") else {}
    hidden = {str(name) for name in gateway_map}
    available = visible | hidden
    for description in descriptions.values():
        available.update(re.findall(r"\bhub_[a-z0-9_]+\b", description.lower()))

    inventory = sorted(available & INVENTORY_TOOLS)
    detail = sorted(available & DETAIL_TOOLS)
    write = sorted(available & WRITE_TOOLS)
    app_named = sorted(name for name in available if "app" in name or "application" in name)

    inventory_supported = bool(inventory)
    state_readback_supported = bool(inventory or detail)
    write_supported = bool(write)
    missing: list[str] = []
    if not inventory_supported:
        missing.append("app inventory/read operation")
    if not write_supported:
        missing.append("app enable/disable write operation")

    return {
        "success": True,
        "inventory_supported": inventory_supported,
        "state_readback_supported": state_readback_supported,
        "write_supported": write_supported,
        "full_control_supported": inventory_supported and write_supported,
        "inventory_tools": inventory,
        "detail_tools": detail,
        "write_tools": write,
        "all_app_related_tools": app_named,
        "missing": missing,
        "suggested_mcp_contract": {
            "read": "hub_list_apps -> apps[{id,label,name,disabled,status,type}]",
            "write": "hub_set_app_disabled({appId, disabled}) -> {success, appId, disabled}",
        },
    }


def install_app_management_capability(application: Any) -> None:
    original_ask: AskHandler = application.ask

    async def ask(request: Any) -> dict[str, Any]:
        if not is_app_capability_query(getattr(request, "query", "")):
            return await original_ask(request)

        started = time.perf_counter()
        try:
            capability = await inspect_app_management_capability(application.mcp, refresh=True)
        except Exception as exc:
            return {
                "success": False,
                "route": "mcp-app-capability-error",
                "intent": "app-management-capability",
                "message": f"I could not inspect the live MCP tool catalogue: {exc}",
                "display": display_payload("diagnostic", "App management capability unavailable", subtitle="No app command was attempted"),
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "technical": safe_debug({"error": str(exc)}),
            }

        if capability["full_control_supported"]:
            message = "The connected MCP server exposes both Hubitat app inventory and app enable/disable control. HomeBrain can now add a guarded deterministic app controller."
            title = "App management supported"
        elif capability["inventory_supported"]:
            message = "The connected MCP server can read Hubitat apps, but no app enable/disable write operation was found. Ask the MCP developer to expose the suggested write contract shown in Technical details."
            title = "App control write missing"
        else:
            message = "The connected MCP server does not currently expose a recognised Hubitat app inventory or app enable/disable operation. Ask the MCP developer to add the suggested read and write contracts shown in Technical details."
            title = "App management not exposed"

        items = [
            {"icon": "📋" if capability["inventory_supported"] else "❌", "title": "App inventory", "value": "Available" if capability["inventory_supported"] else "Missing", "subtitle": ", ".join(capability["inventory_tools"]) or "Suggested: hub_list_apps", "tone": "success" if capability["inventory_supported"] else "warning"},
            {"icon": "🔎" if capability["state_readback_supported"] else "❌", "title": "App state read-back", "value": "Available" if capability["state_readback_supported"] else "Missing", "subtitle": ", ".join(capability["detail_tools"] or capability["inventory_tools"]) or "Inventory must include disabled/status", "tone": "success" if capability["state_readback_supported"] else "warning"},
            {"icon": "🛡️" if capability["write_supported"] else "❌", "title": "Enable/disable write", "value": "Available" if capability["write_supported"] else "Missing", "subtitle": ", ".join(capability["write_tools"]) or "Suggested: hub_set_app_disabled", "tone": "success" if capability["write_supported"] else "warning"},
        ]
        return {
            "success": True,
            "route": "mcp-app-capability",
            "intent": "app-management-capability",
            "message": message,
            "answered_by": "Hubitat MCP capability diagnostic",
            "display": display_payload(
                "diagnostic", title,
                subtitle="Live MCP tool catalogue inspection; no write was attempted",
                metrics=[
                    {"label": "Inventory", "value": "Yes" if capability["inventory_supported"] else "No", "icon": "📋"},
                    {"label": "Read-back", "value": "Yes" if capability["state_readback_supported"] else "No", "icon": "🔎"},
                    {"label": "App writes", "value": "Yes" if capability["write_supported"] else "No", "icon": "🛡️"},
                ],
                items=items,
                note="This diagnostic only reports MCP capability. It never enables or disables an app.",
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug(capability),
        }

    application.ask = ask


__all__ = ["inspect_app_management_capability", "install_app_management_capability", "is_app_capability_query"]

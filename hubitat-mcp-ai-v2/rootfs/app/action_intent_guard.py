"""Tool-structured authorization and source-grounded native rule outcomes.

A chat 'yes' or model-generated prose is not permission for a persistent
automation write. Only the actual selected MCP writer / leaf determines
whether a separate operation-specific UI approval is mandatory.
"""
from __future__ import annotations
from typing import Any

_NATIVE_AUTOMATION_WRITERS = frozenset({
    "hub_set_visual_rule", "hub_set_rule", "hub_create_custom_rule",
    "hub_update_custom_rule", "hub_set_native_app",
})

def native_automation_writer(name: str, arguments: dict[str, Any] | None) -> str | None:
    """Return a real selected writer, without reading the user question."""
    if name in _NATIVE_AUTOMATION_WRITERS:
        return name
    leaf = (arguments or {}).get("tool")
    if isinstance(leaf, str) and leaf in _NATIVE_AUTOMATION_WRITERS:
        return leaf
    return None

def automation_write_requires_confirmation(name: str, arguments: dict[str, Any] | None) -> bool:
    return native_automation_writer(name, arguments) is not None

def rule_activation_outcome(result: Any) -> dict[str, Any] | None:
    """Parse original native storage/activation flags, not rule execution."""
    import json
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (TypeError, ValueError):
            return None
    if not isinstance(result, dict):
        return None
    if isinstance(result.get("content"), list):
        for item in result["content"]:
            if isinstance(item, dict) and item.get("type") == "text":
                parsed = rule_activation_outcome(item.get("text"))
                if parsed:
                    return parsed
    if isinstance(result.get("mcp_result"), dict):
        return rule_activation_outcome(result["mcp_result"])
    if any(k in result for k in ("activated", "activatedSuccessfully", "validationErrors")):
        return {
            "stored": result.get("storedSuccessfully"),
            "activated": result.get("activatedSuccessfully", result.get("activated")),
            "validation_errors": result.get("validationErrors") or [],
            "app_id": result.get("appId"),
        }
    return None

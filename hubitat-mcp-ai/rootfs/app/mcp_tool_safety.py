from __future__ import annotations

import json
import re
from typing import Any, Literal


ToolSafetyClass = Literal["read", "mutate", "destructive"]

_DESTRUCTIVE_TOOLS = {
    "hub_reboot",
    "hub_shutdown",
    "hub_delete_device",
    "hub_call_destructive_ops",
    "hub_update_firmware",
    "hub_update_package",
    "hub_install_bundle",
    "hub_delete_bundle",
    "hub_delete_file",
    "hub_write_file",
    "hub_delete_visual_rule",
    "hub_set_visual_rule",
    "hub_delete_dashboard",
    "hub_call_device_swap",
    "hub_call_device_replace",
}
_READ_VERBS = ("hub_get_", "hub_list_", "hub_read_", "hub_search_", "hub_test_")
_FLAT_MANAGE_TOOLS = {"hub_manage_mode", "hub_manage_virtual_device"}
_MUTATION_VERBS = (
    "hub_call_",
    "hub_clone_",
    "hub_create_",
    "hub_delete_",
    "hub_export_",
    "hub_import_",
    "hub_manage_",
    "hub_reboot",
    "hub_restore_",
    "hub_set_",
    "hub_shutdown",
    "hub_update_",
    "hub_write_",
)


def effective_tool_name(name: str, arguments: dict[str, Any] | None = None) -> str:
    """Return the leaf tool selected through a gateway, when present."""

    tool_name = str(name or "").strip()
    args = arguments if isinstance(arguments, dict) else {}
    if tool_name.startswith(("hub_read_", "hub_manage_")):
        nested = str(args.get("tool") or "").strip()
        if nested.startswith("hub_"):
            return nested
    return tool_name


def classify_tool_safety(
    name: str,
    arguments: dict[str, Any] | None = None,
    *,
    annotations: dict[str, Any] | None = None,
) -> ToolSafetyClass:
    """Classify an MCP call using server annotations, then conservative fallbacks."""

    args = arguments if isinstance(arguments, dict) else {}
    leaf = effective_tool_name(name, args)
    hints = annotations if isinstance(annotations, dict) else {}

    if hints.get("destructiveHint") is True:
        return "destructive"
    if leaf in _DESTRUCTIVE_TOOLS:
        return "destructive"
    if leaf.startswith("hub_delete_"):
        return "destructive"

    # These nominal reads become writes only when their opt-in mutation flag is set.
    if leaf == "hub_get_metrics" and args.get("recordSnapshot") is True:
        return "mutate"

    if hints.get("readOnlyHint") is True:
        return "read"
    if hints.get("readOnlyHint") is False:
        return "mutate"
    if leaf in _FLAT_MANAGE_TOOLS:
        return "mutate"

    # A gateway catalogue call with no selected leaf only discovers schemas.
    if leaf == str(name or "").strip() and leaf.startswith(
        ("hub_read_", "hub_manage_")
    ):
        return "read" if not args.get("tool") else "mutate"
    if leaf.startswith(_READ_VERBS):
        return "read"
    if leaf.startswith(_MUTATION_VERBS):
        return "mutate"
    return "read"


def requires_explicit_confirmation(
    name: str,
    arguments: dict[str, Any] | None,
    latest_query: str,
    *,
    annotations: dict[str, Any] | None = None,
) -> bool:
    """Return whether this proposed call still needs explicit user confirmation."""

    args = arguments if isinstance(arguments, dict) else {}
    safety = classify_tool_safety(
        name,
        args,
        annotations=annotations,
    )
    query = str(latest_query or "").strip().lower()
    combined = (
        f"{effective_tool_name(name, args)} "
        f"{json.dumps(args, ensure_ascii=False, default=str)} {query}"
    ).lower()

    critical_mutation = any(
        marker in combined
        for marker in (
            "unlock",
            "open garage",
            "disarm",
            "disable cloud",
            "disconnect_ethernet",
            "disconnect_wifi",
            "factory reset",
            "reset radio",
            "wipe",
        )
    )
    if safety != "destructive" and not critical_mutation:
        return False

    confirmed = bool(
        re.search(
            r"\b(?:i\s+confirm|confirm(?:ed)?|yes[, ]+(?:do\s+it|proceed)|"
            r"proceed(?:\s+with\s+it)?|approved)\b",
            query,
            flags=re.IGNORECASE,
        )
    )
    if not confirmed:
        return True

    # Destructive MCP schemas use confirm=true as an independent server-side
    # guard. Do not let a model infer or omit that field after a verbal approval.
    if safety == "destructive" and args.get("confirm") is not True:
        return True
    return False


__all__ = [
    "ToolSafetyClass",
    "classify_tool_safety",
    "effective_tool_name",
    "requires_explicit_confirmation",
]

"""Bounded native Rule Machine document source, never a writer.

A management *gateway* is not safe to expose wholesale in a read-only model
catalog. For an explicitly named existing rule, the host may instead call the
single verified native `operation=read` envelope, source-match its returned
document and supply a small typed evidence packet. Unknown operations and
partial/mismatched documents cannot satisfy completion.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from mcp_client import MCPTool, tool_succeeded
from tool_registry import ToolEffect, classify_tool_effect

_GATEWAYS = ("hub_manage_native_rules_and_apps", "hub_manage_rule_machine")
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.#-]{0,75}$")
_REDACT = re.compile(r"(?i)(?:password|secret|token|api.?key|credential|pin|authorization)")


def _simple_setting(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    name = row.get("name")
    kind = row.get("type")
    if not isinstance(name, str) or not _NAME.fullmatch(name) or _REDACT.search(name):
        return None
    if not isinstance(kind, str) or not _NAME.fullmatch(kind):
        return None
    result: dict[str, Any] = {"name": name, "type": kind}
    ids = row.get("device_ids")
    if isinstance(ids, list) and len(ids) <= 24 and all(
        isinstance(i, (str, int)) and re.fullmatch(r"[1-9]\d{0,8}", str(i))
        for i in ids
    ):
        result["device_ids"] = [str(i) for i in ids]
    v = row.get("value")
    if type(v) in (bool, int, float):
        result["value"] = v
    elif isinstance(v, str) and len(v) <= 100 and not _REDACT.search(v):
        result["value"] = v
    return result


def project_native_document(data: Any, app_id: str) -> dict[str, Any] | None:
    """Project typed, target-matched document structure, not editor execution.

    This proves persisted native configuration fields/action ordering, never
    the physical runtime effect or any one-time time semantics.
    """
    if not isinstance(data, dict) or str(data.get("rule_id") or "") != app_id:
        return None
    if any(k not in data for k in ("settings", "actions", "triggers", "conditions")):
        return None
    settings, actions, triggers, conditions = (
        data["settings"], data["actions"], data["triggers"], data["conditions"]
    )
    if not (isinstance(settings, list) and len(settings) <= 256
            and isinstance(actions, list) and len(actions) <= 100
            and isinstance(triggers, dict) and len(triggers) <= 100
            and isinstance(conditions, dict)):
        return None
    if (data.get("nextCursor") is not None
            or data.get("truncated") is True
            or any(not isinstance(row, dict) or "id" not in row
                   or not isinstance(row.get("value"), dict) for row in actions)):
        return None
    typed = [_simple_setting(item) for item in settings]
    if any(item is None for item in typed):
        # A sensitive/unsupported native setting must not be exported as
        # a fully verified contract. Fall back to a partial configuration.
        return None
    order = []
    for item in actions:
        method = item["value"].get("method")
        if not (isinstance(method, str) and _NAME.fullmatch(method)):
            return None
        order.append({"id": str(item["id"])[:16], "method": method})
    if len({r["id"] for r in order}) != len(order):
        return None
    safe_triggers = {}
    for key, value in triggers.items():
        if not (isinstance(key, str) and key.isdigit()
                and isinstance(value, str) and len(value) <= 160
                and not _REDACT.search(value)):
            return None
        safe_triggers[key] = value
    health = data.get("nativeHealth")
    health = health if isinstance(health, dict) else {}
    return {
        "appId": app_id,
        "source": "hub_set_rule:read",
        "triggerCount": len(triggers),
        "actionCount": len(actions),
        "conditionCount": len(conditions),
        "triggers": safe_triggers,
        "orderedActions": order,
        "settings": typed,
        "verifiedHealth": {
            key: health[key] for key in ("paused", "stopped", "broken")
            if type(health.get(key)) is bool
        },
        "semanticFieldsValidated": True,
        "orderedActionsValidated": True,
        "conditionsValidated": True,
        "nativeEditorChecked": (
            data.get("validation", {}).get("uiChecked") is True
            if isinstance(data.get("validation"), dict) else False
        ),
    }


async def prefetch_native_rule_document(
    mcp: Any, evidence: Any, *,
    app_id: str, available_names: set[str] | frozenset[str],
    messages: list[dict[str, Any]],
) -> bool:
    """One host-owned read, no form open, no confirmation or repeat on failure."""
    if not isinstance(app_id, str) or not re.fullmatch(r"[1-9]\d{0,8}", app_id):
        return False
    gateway = next((g for g in _GATEWAYS if g in available_names), None)
    if gateway is None:
        return False
    args = {"tool": "hub_set_rule", "args": {
        "operation": "read", "rule_id": int(app_id),
    }}
    if classify_tool_effect(MCPTool(gateway, gateway, {}), args) is not ToolEffect.READ:
        return False
    start = time.monotonic()
    try:
        reply = await mcp.call_tool(gateway, args)
        valid = tool_succeeded(reply)
        projected = project_native_document(getattr(reply, "data", None), app_id) if valid else None
    except Exception:
        projected = None
    elapsed = round((time.monotonic() - start) * 1000)
    evidence.record(
        gateway, args, success=projected is not None,
        elapsed_ms=elapsed, summary=(
            "Source-matched complete native rule document read"
            if projected else "Native rule document unreadable or incomplete"
        ),
        evidence_kind="typed_native_rule_document",
        supports_live_claim=projected is not None,
        effect="read", mutates=False,
        details=projected if projected is not None else {"appId": app_id, "source": "hub_set_rule:read"},
    )
    if projected is None:
        return False
    messages.append({
        "role": "user",
        "content": "HOST-VERIFIED NATIVE RULE DOCUMENT (READ-ONLY)\n"
            + json.dumps(projected, ensure_ascii=False)
            + "\nThese fields are stored native configuration, not proof "
              "the rule ran or devices operated. No parent ID or one-time "
              "date semantics may be inferred from an absent field."
    })
    return True

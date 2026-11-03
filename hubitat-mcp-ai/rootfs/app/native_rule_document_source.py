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
    elif isinstance(v, str):
        if len(v) > 100 or _REDACT.search(v):
            return None
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
    # Nested IF/ELSE and expression graphs require their own validated
    # native semantics. Never certify a partial projection of those as a
    # complete action tree merely because the source document was returned.
    if conditions or data.get("expressions") not in (None, {}):
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
        value = item["value"]
        if set(value) - {"method", "quick", "indent"}:
            return None
        if value.get("indent") not in (None, ""):
            return None
        method = value.get("method")
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


# An explicitly requested native document read is different from a *complete*
# rule-logic audit. A failed all-sections projection must not swallow the raw
# source error or substitute irrelevant default review obligations.
_EXPLICIT_ID = re.compile(
    r"\brule[_\s-]*id\s*[:=#]?\s*['\"]?([1-9]\d{1,8})\b", re.I
)
_EXPLICIT_OPERATION = re.compile(
    r"\boperation\s*['\"]?\s*[:=]\s*['\"]?read\b", re.I
)
_EXPLICIT_SECTIONS = re.compile(
    r"\bsections['\"]?\s*[:=]\s*\[([^\]]+)\]", re.I
)
_NATIVE_SECTIONS = frozenset({
    "actions", "conditions", "triggers", "expressions", "variables", "settings",
})
_ERROR_SECRET = re.compile(
    r"(?i)\b(?:password|secret|token|api[_-]?key|authorization|"
    r"credential|bearer)\b\s*[:=]\s*['\"]?[^,\s;}\]]+"
)


def parse_explicit_native_read(
    prompt: str,
) -> tuple[str, tuple[str, ...]] | None:
    """Recognise a specific caller-authored read envelope, not a vague intent."""
    prompt = str(prompt or "")
    if "hub_set_rule" not in prompt.casefold() or not _EXPLICIT_OPERATION.search(prompt):
        return None
    ids = set(_EXPLICIT_ID.findall(prompt))
    section_match = _EXPLICIT_SECTIONS.search(prompt)
    if len(ids) != 1 or section_match is None:
        return None
    sections = tuple(re.findall(
        r"['\"]([a-z]+)['\"]", section_match.group(1), re.I
    ))
    if (not sections or len(set(sections)) != len(sections)
            or set(sections) - _NATIVE_SECTIONS):
        return None
    return next(iter(ids)), sections


def _error_text(value: Any) -> str:
    raw = " ".join(str(value or "").split())
    return _ERROR_SECRET.sub("[credential redacted]", raw)[:360] or (
        "The MCP response did not expose an error message."
    )


def _exact_source_error(reply: Any) -> tuple[str, str]:
    data = getattr(reply, "data", None)
    if isinstance(data, dict):
        code = data.get("code") or data.get("errorCode")
        error = data.get("error")
        if isinstance(error, dict):
            code = code or error.get("code")
            error = error.get("message") or error.get("error")
        message = error or data.get("message")
        if message is not None:
            return _error_text(code or "mcp_tool_error"), _error_text(message)
    return (
        "mcp_tool_error" if getattr(reply, "is_error", False) else "mcp_read_unverified",
        _error_text(getattr(reply, "text", "")),
    )


async def read_explicit_native_rule_document(
    mcp: Any, evidence: Any, *,
    prompt: str, available_names: set[str] | frozenset[str],
) -> str | None:
    """Read only requested native sections; never perform writes or retries.

    Publish bounded, whitelisted fields instead of a raw native document
    (which can contain private user settings). A real tool error and a valid
    response rejected by the verifier are distinguished in the receipt.
    """
    parsed = parse_explicit_native_read(prompt)
    if parsed is None:
        return None
    app_id, sections = parsed
    gateway = next((g for g in _GATEWAYS if g in available_names), None)
    if gateway is None:
        return (
            f"Native rule {app_id} read unavailable: the installed MCP catalog "
            "has no approved native rule-document gateway. No changes made."
        )
    request = {"tool": "hub_set_rule", "args": {
        "operation": "read", "rule_id": int(app_id),
        "args": {"sections": list(sections)},
    }}
    if classify_tool_effect(MCPTool(gateway, gateway, {}), request) is not ToolEffect.READ:
        return "Native rule read blocked by the read-only gate. No changes made."
    started = time.monotonic()
    reply = None
    try:
        reply = await mcp.call_tool(gateway, request)
        source_ok = tool_succeeded(reply)
        error = None if source_ok else _exact_source_error(reply)
    except Exception as exc:
        source_ok = False
        error = ("mcp_call_exception", _error_text(
            f"{type(exc).__name__}: {exc}"
        ))
    data = getattr(reply, "data", None)
    if source_ok and (
        not isinstance(data, dict)
        or str(data.get("rule_id") or "") != app_id
    ):
        error = ("target_document_unverified",
                 "Returned native document was not linked to the requested rule ID.")
    if source_ok and error is None and any(s not in data for s in sections):
        error = ("requested_section_missing",
                 "MCP returned a document without the requested section.")
    if source_ok and error is None and (
        data.get("nextCursor") is not None or data.get("truncated") is True
    ):
        error = ("native_section_incomplete",
                 "MCP returned a partial page; no complete-section claim.")
    methods: list[tuple[str, str]] = []
    if source_ok and error is None and "actions" in sections:
        rows = data["actions"]
        if not isinstance(rows, list) or len(rows) > 100:
            error = ("native_actions_invalid", "Actions are not a bounded ordered list.")
        else:
            seen: set[str] = set()
            for row in rows:
                if not isinstance(row, dict):
                    error = ("native_actions_invalid", "A native action row was malformed.")
                    break
                aid = str(row.get("id") or "")
                val = row.get("value")
                method = val.get("method") if isinstance(val, dict) else None
                if (not re.fullmatch(r"[1-9]\d{0,8}", aid)
                        or aid in seen or not isinstance(method, str)
                        or not _NAME.fullmatch(method)):
                    error = ("native_actions_invalid",
                             "A native action has no unique ID or value.method.")
                    break
                seen.add(aid)
                methods.append((aid, method))
    elapsed = round((time.monotonic() - started) * 1000)
    verified = source_ok and error is None
    details: dict[str, Any] = {
        "appId": app_id, "gateway": gateway, "operation": "read",
        "requestedSections": list(sections), "sourceSuccess": source_ok,
        "projectionVerified": verified,
    }
    if error is not None:
        details["errorCode"], details["errorMessage"] = error
    elif methods:
        details["orderedActions"] = [
            {"id": aid, "method": method} for aid, method in methods
        ]
    evidence.record(
        gateway, request, success=verified, elapsed_ms=elapsed,
        summary=("Verified explicit native section read" if verified
                 else f"Native read not verified: {error[0] if error else 'unknown'}"),
        evidence_kind="typed_native_rule_section",
        supports_live_claim=verified, mutates=False, effect="read",
        details=details,
    )
    header = (
        f"Native Rule Machine read for rule {app_id}. "
        f"Gateway: {gateway}. Operation: read. "
        f"Requested sections: {', '.join(sections)}."
    )
    if error is not None:
        return (
            header + "\n\nSource read NOT VERIFIED. "
            f"Error code: {error[0]}. Error detail: {error[1]}\n\n"
            "This does not prove the rule is missing or incorrectly configured. "
            "No modifying calls were made."
        )
    output = [header]
    if "actions" in sections:
        output.append("Native ordered action entries:")
        output.extend(
            f"{position}. id={aid}; value.method={method}"
            for position, (aid, method) in enumerate(methods, 1)
        )
        if not methods:
            output.append("No native action rows returned.")
        output.append(
            "Action order and methods are reported by the native document; "
            "they do not prove execution or device effects."
        )
    if "settings" in sections:
        rows = data["settings"]
        if isinstance(rows, list) and len(rows) <= 256:
            safe = [_simple_setting(row) for row in rows]
            output.append(
                f"Settings: {len(rows)} returned; "
                f"{sum(v is None for v in safe)} redacted or unsupported."
            )
            for row in safe:
                if row is not None:
                    output.append(
                        f"name={row['name']}; type={row['type']}; "
                        f"value={str(row.get('value', 'unavailable'))[:100]}; "
                        f"device_ids={row.get('device_ids', [])}"
                    )
        else:
            output.append("Settings shape unverified; no settings exported.")
    for section in sections:
        if section not in {"actions", "settings"}:
            value = data[section]
            output.append(
                f"{section}: {len(value)} returned entries; "
                "nested meaning not independently verified."
                if isinstance(value, (dict, list)) else
                f"{section}: unexpected source shape (unverified)."
            )
    output.append("No modifying Hubitat calls were made.")
    return "\n\n".join(output)

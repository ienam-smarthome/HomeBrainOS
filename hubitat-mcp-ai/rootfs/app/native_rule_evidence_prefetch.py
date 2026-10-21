"""Bounded, read-only native Rule Machine health and variable prefetch.

Purpose: establish actual status/variable evidence BEFORE a model may confuse
hub_get_rule_health with a modifying gateway or rely on app-identity text.

No tool search, no write or management gateway, no rule creation. Returns
only documented fields with direct observation of missing/failed readers.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from mcp_client import tool_succeeded

_SENSITIVE_NAME = re.compile(r"(?i)(?:password|secret|token|api[_-]?key|pin|credential|auth[_-]?code)")


def _reliable_data(reply: Any) -> dict[str, Any] | None:
    if reply is None or not tool_succeeded(reply):
        return None
    data = getattr(reply, "data", None)
    if not isinstance(data, dict) or data.get("ok") is False:
        return None
    return data


def _verified_health(data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("paused", "stopped", "broken"):
        value = data.get(key)
        if isinstance(value, bool):
            result[key] = value
    return result


def _variables(data: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    """Extract only typed, bounded variable facts; no raw settings/secrets."""
    rows = data.get("localVariables")
    if not isinstance(rows, list):
        return [], False
    result = []
    for raw in rows[:25]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "")[:80]
        if not name:
            continue
        row: dict[str, Any] = {"name": name}
        typ = raw.get("type")
        if isinstance(typ, str):
            row["type"] = typ[:32]
        value = raw.get("value")
        # Numeric values are especially useful for usage counters. No
        # arbitrary string values (possibly secrets) enter the model packet.
        if (not _SENSITIVE_NAME.search(name)
                and isinstance(value, (int, float)) and not isinstance(value, bool)):
            row["value"] = value
        elif (not _SENSITIVE_NAME.search(name)
              and isinstance(value, str) and len(value) <= 18):
            try:
                row["value"] = float(value) if "." in value else int(value)
            except ValueError:
                pass
        result.append(row)
    return result, True


async def prefetch_native_rule_evidence(
    mcp: Any,
    evidence: Any,
    *,
    app_id: str,
    available_names: set[str] | frozenset[str],
    messages: list[dict[str, str]],
) -> bool:
    """Read compiled-rule health and local variable metadata for a named ID.

    Only hub_read_rules gateway with known, read-only suboperations is called.
    Failures are recorded as failures, not evidence of a broken rule.
    Local variables of app X MUST NOT be assumed writeable by separate app Y.
    """
    if not app_id.isdigit() or "hub_read_rules" not in available_names:
        return False
    facts: dict[str, Any] = {"appId": app_id}
    attempted = False
    checks = [
        ("hub_get_rule_health", "health"),
        ("hub_list_rule_local_variables", "localVariables"),
    ]
    for leaf, key in checks:
        args = {"tool": leaf, "args": {"appId": app_id}}
        started = time.monotonic()
        try:
            raw = await mcp.call_tool("hub_read_rules", args)
            data = _reliable_data(raw)
        except Exception:
            data = None
        if isinstance(data, dict):
            actual_id = data.get("appId")
            if actual_id is None and isinstance(data.get("app"), dict):
                actual_id = data["app"].get("id")
            if actual_id is not None and str(actual_id) != app_id:
                data = None
        success = data is not None
        details: dict[str, Any] = {"appId": app_id, "source": leaf}
        if success and key == "health":
            confirmed = _verified_health(data)
            facts["health"] = confirmed
            facts["healthFieldsReadable"] = bool(confirmed)
            details["verifiedHealth"] = confirmed
        elif success and key == "localVariables":
            variables, parsed = _variables(data)
            facts["localVariables"] = variables
            facts["localVariablesReadable"] = parsed
            details["returnedVariableCount"] = len(variables)
            details["numericVariables"] = [
                item for item in variables if "value" in item
            ][:12]
        else:
            facts[key + "ReadFailed"] = True
        evidence.record(
            "hub_read_rules", args, success=success,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=leaf + (" read" if success else " unavailable"),
            supports_live_claim=bool(
                success and (
                    facts.get("healthFieldsReadable") if key == "health"
                    else facts.get("localVariablesReadable")
                )
            ),
            evidence_kind="native_rule_evidence",
            effect="read", mutates=False,
            details=details,
        )
        attempted = True

    if attempted:
        # This is a source packet, not a verified outcome/conclusion.
        messages.append({
            "role": "user",
            "content": (
                "HOST-VERIFIED READ-ONLY NATIVE RULE EVIDENCE\n"
                + json.dumps(facts, ensure_ascii=False, sort_keys=True)
                + "\nHealth booleans and numeric local-variable values "
                  "are evidence only when explicitly present. "
                  "An unreadable field remains unknown. "
                  "Local variables belong to their owning app; never assert "
                  "that another Rule Machine app can reset a local variable "
                  "just because the two use the same variable name. "
                  "Inspect global Hub Variable versus local-variable scope "
                  "before accepting any cross-rule reset mechanism. "
                  "This packet does NOT prove a 60-minute execution, "
                  "network reachability or the complete action sequence."
            ),
        })
    return attempted

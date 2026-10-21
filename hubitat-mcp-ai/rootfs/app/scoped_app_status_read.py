"""Deterministic read-only execution for explicitly scoped app-status questions.

This path never invents a 'failed config read' if only discovery ran.
It requires the actual named MCP capability, checks tool success, and returns
a truthful partial result when configuration cannot be read.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re
from typing import Any

from mcp_client import HubitatMCPClient, tool_succeeded
from rule_machine_analysis import requires_rule_logic_inspection

_SCOPED_STATUS = re.compile(
    r"(?i)\b(?:status|enabled|disabled|readiness|lockout|current\s+state)\b"
)
_APP_ID = re.compile(r"(?i)\bapp\s*(?:id\s*)?#?\s*(\d{3,7})\b")
_HISTORY = re.compile(r"(?i)\b(?:historical|history|recent\s+executions?|logs?|why|investigat|diagnos)\b")
_SOURCE_ANALYSIS = re.compile(
    r"(?i)\b(?:groovy|source(?:[- ]code)?|implementation|defaultvalue|"
    r"state\.motionlockout|code\s+path|getter\s+(?:fallback|logic))\b"
)


# The early status shortcut must only consume *simple status questions*.
# A complex multi-part instruction may mention "enabled/paused status" as one
# small part of a Rule Machine logic review; it must never be swallowed here.
_QUICK_STATUS_START = re.compile(
    r"(?i)^\s*(?:(?:please|can you|could you|would you)\s+)?"
    r"(?:what(?:'s| is| was)|is|are|does|has|show|check|verify|report|"
    r"tell me|give me|display|get|read|current)\b"
)
_COMPLEX_STATUS_REQUEST = re.compile(
    r"(?i)\b(?:actual\s+(?:actions?|triggers?)|actions?\b|"
    r"conditions?|variable|counter|reset|cumulative|"
    r"after\s+\d+\s*(?:min|hour|hr)|"
    r"logic|behaviou?r|run\s+history|execution\s+evidence|"
    r"rule\s+machine\s+capabilities|unreadable\s+sections)\b"
)


def scoped_status_app_id(question: str) -> int | None:
    text = str(question or "")
    m = _APP_ID.search(text)
    if (not m or not _SCOPED_STATUS.search(text) or _HISTORY.search(text)
            or _SOURCE_ANALYSIS.search(text)
            or requires_rule_logic_inspection(text)
            or not _QUICK_STATUS_START.search(text)
            or _COMPLEX_STATUS_REQUEST.search(text)
            or len(text.split()) > 26):
        return None
    return int(m.group(1))


@dataclass(slots=True)
class ScopedAppStatusOutcome:
    message: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    request_class: str = "live-read"
    choices: list[str] = field(default_factory=list)
    confirmation_required: bool = False
    confirmation_count: int = 0
    route: str = "scoped-app-status"
    investigation_coverage: dict[str, Any] | None = None
    complete: bool = False


async def read_scoped_app_status(mcp: HubitatMCPClient, app_id: int) -> ScopedAppStatusOutcome:
    # Checking the exact catalog is read-only and avoids guessing tool names.
    try:
        tools = await mcp.list_tools()
    except Exception:
        return ScopedAppStatusOutcome(
            f"Unable to verify app {app_id} status: MCP tool discovery failed. No app configuration was read."
        )
    tool_names = {tool.name for tool in tools}
    if "hub_read_apps_code" not in tool_names:
        return ScopedAppStatusOutcome(
            f"Unable to verify app {app_id} status: hub_read_apps_code is not available in the current MCP catalog."
        )

    args = {"appId": str(app_id), "includeSettings": False}
    try:
        response = await mcp.call_tool("hub_read_apps_code", {"tool": "hub_get_app_config", "args": args})
    except Exception:
        return ScopedAppStatusOutcome(
            f"Unable to verify app {app_id} status: the configuration read was attempted but failed.",
            evidence=[{"tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
                       "arguments": {"tool": "hub_get_app_config", "args": args},
                       "success": False, "mutates": False, "effect": "read",
                       "summary": "Configuration read failed"}],
        )
    ok = tool_succeeded(response)
    data = response.data if isinstance(response.data, dict) else {}
    evidence = [{"tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
                 "arguments": {"tool": "hub_get_app_config", "args": args},
                 "success": ok, "mutates": False, "effect": "read",
                 "supports_live_claim": ok,
                 "summary": "App configuration read" if ok else "App configuration read returned an error"}]
    if not ok:
        return ScopedAppStatusOutcome(
            f"App {app_id} configuration was requested, but the MCP server returned an error. Current status is unverified.",
            evidence=evidence,
        )
    # Never infer enabled state / countdown from the mere existence of an app.
    from causal_rule_decision_context import configuration_text
    excerpts, _ = configuration_text(data)
    snippets = [str(line).strip()[:240] for line in excerpts if str(line).strip()][:6]
    if snippets:
        message = (
            f"App {app_id} configuration was retrieved successfully. "
            "These are current configuration excerpts, not verified execution history:\n\n"
            + "\n".join("- " + line for line in snippets)
        )
    else:
        # The installed app page is not a status reader. Native Rule Machine
        # exposes a separate read-only compiled-rule health endpoint. When
        # available, use it to answer status-only requests; do not infer a
        # status from the app label or a page with no matching fields.
        if "hub_read_rules" in tool_names:
            health_args = {"tool": "hub_get_rule_health", "args": {"appId": str(app_id)}}
            try:
                health_response = await mcp.call_tool("hub_read_rules", health_args)
                health_ok = tool_succeeded(health_response)
                health = (health_response.data
                          if isinstance(health_response.data, dict) else {})
            except Exception:
                health_ok = False
                health = {}
            evidence.append({
                "tool": "hub_read_rules",
                "sub_tool": "hub_get_rule_health",
                "arguments": health_args,
                "success": health_ok,
                "mutates": False,
                "effect": "read",
                "supports_live_claim": health_ok,
                "summary": "Native rule health read" if health_ok else "Native rule health unavailable",
            })
            if health_ok:
                # Distinguish observed booleans from null/unknown. A false
                # paused value is not a blanket proof of full readiness.
                fields = [
                    f"{key}={str(health[key]).lower()}"
                    for key in ("paused", "stopped", "broken")
                    if isinstance(health.get(key), bool)
                ]
                if fields:
                    return ScopedAppStatusOutcome(
                        f"App {app_id}: verified native Rule Machine health fields: "
                        + ", ".join(fields)
                        + ". The configuration page supplied no additional status "
                        "details. Actual trigger/action logic and runtime execution "
                        "are not verified by this status snapshot.",
                        evidence=evidence, complete=True,
                    )
        message = (f"App {app_id} configuration was retrieved, but neither that page "
                   "nor the available Rule Machine health evidence exposed verified "
                   "enabled, paused or status fields. A configuration identity read "
                   "alone cannot establish runtime behaviour or rule execution.")
    return ScopedAppStatusOutcome(message, evidence=evidence, complete=bool(snippets))

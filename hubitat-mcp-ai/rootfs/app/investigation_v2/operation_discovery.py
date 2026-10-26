"""V2's independent, bounded proof of live MCP read-operation availability.

The upstream skill documents gateway discovery; it is guidance, not authority.
Positive current-session hub_search_tools mappings are accepted only for
read-only gateways already in tools/list. Explicit gateway enums win over
search results. No source payload, credentials or model text is retained.
"""
from __future__ import annotations

import asyncio
from typing import Any, Iterable

from mcp_client import MCPTool, tool_succeeded
from tool_executor import ToolExecutor
from tool_registry import ToolEffect, classify_tool_effect


def advertised_operation(tool: MCPTool, operation: str) -> bool:
    props = tool.input_schema.get("properties", {}) if isinstance(tool.input_schema, dict) else {}
    field = props.get("tool", {}) if isinstance(props, dict) else {}
    allowed = field.get("enum") if isinstance(field, dict) else None
    return isinstance(allowed, list) and operation in allowed


def _query_args(tool: MCPTool, operation: str) -> dict[str, Any] | None:
    schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
    fields = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(fields, dict) or not isinstance(required, list):
        return None
    query = fields.get("query")
    if not isinstance(query, dict) or query.get("type") not in ("string", None):
        return None
    if any(key != "query" for key in required):
        return None
    return {"query": operation}


def _valid_read(tool: MCPTool | None) -> bool:
    if tool is None or classify_tool_effect(tool, {}) is not ToolEffect.READ:
        return False
    annotations = tool.annotations if isinstance(tool.annotations, dict) else {}
    return not (annotations.get("readOnlyHint") is False
                or annotations.get("mutates") is True
                or annotations.get("destructiveHint") is True)


async def discover_device_operations(
    tools: Iterable[MCPTool], executor: ToolExecutor, *,
    deadline_remaining: float = 12.0,
) -> tuple[dict[str, set[str]], list[dict[str, Any]]]:
    """Discover, but NEVER execute, only two predetermined read suboperations.

    The caller still authorises every resulting proposal against the exact
    live gateway tool declaration, verified device ID and write-effect gate.
    """
    registry = {t.name: t for t in tools if isinstance(t, MCPTool)}
    gateway = registry.get("hub_read_devices")
    operations = ("hub_get_device", "hub_list_device_events")
    learned: dict[str, set[str]] = {}
    diag: list[dict[str, Any]] = []
    if not _valid_read(gateway):
        return {}, [{"stage": "discovery", "reason": "read_gateway_unavailable"}]
    search = registry.get("hub_search_tools")
    for operation in operations:
        if advertised_operation(gateway, operation):
            diag.append({"stage": operation, "status": "live_enum"})
            continue
        # Authoritative explicit operation lists must not be widened by fuzzy
        # discovery, even if a different gateway claims the operation exists.
        props = gateway.input_schema.get("properties", {})
        op_field = props.get("tool", {}) if isinstance(props, dict) else {}
        enum = op_field.get("enum") if isinstance(op_field, dict) else None
        if isinstance(enum, list):
            diag.append({"stage": operation, "reason": "operation_not_in_live_enum"})
            continue
        if not _valid_read(search):
            diag.append({"stage": operation, "reason": "search_tool_unavailable"})
            continue
        args = _query_args(search, operation)
        if args is None:
            diag.append({"stage": operation, "reason": "search_schema_unsupported"})
            continue
        if deadline_remaining <= 0:
            diag.append({"stage": operation, "reason": "discovery_budget_exhausted"})
            continue
        try:
            execution = await asyncio.wait_for(
                executor.execute(search.name, args, tool=search, record_evidence=False),
                timeout=min(6.0, max(0.1, deadline_remaining)),
            )
            deadline_remaining -= min(6.0, max(0.1, execution.elapsed_ms / 1000))
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            deadline_remaining -= 6.0
            diag.append({"stage": operation, "reason": "search_timeout"})
            continue
        except Exception:
            diag.append({"stage": operation, "reason": "search_execution_failure"})
            continue
        response = execution.result
        if (execution.effect is not ToolEffect.READ or not execution.success
                or response is None or not tool_succeeded(response)):
            diag.append({"stage": operation, "reason": "search_failed"})
            continue
        data = response.data if isinstance(response.data, dict) else {}
        entries = None
        # Only same-session structured tool/gateway pairs authorise a mapping.
        for obj in [data, *[data.get(x) for x in ("result", "data", "output")]]:
            if not isinstance(obj, dict):
                continue
            found = obj.get("results", obj.get("matches"))
            if isinstance(found, list):
                entries = found
                break
        if entries is None:
            diag.append({"stage": operation, "reason": "search_no_structured_results"})
            continue
        gateways = {item.get("gateway") for item in entries
                    if isinstance(item, dict) and item.get("tool") == operation
                    and isinstance(item.get("gateway"), str)}
        # An operation may legally belong to both read and manage gateways.
        # Ignore write gateways rather than rejecting a verified read member.
        eligible_read = {name for name in gateways
                         if name.startswith("hub_read_")
                         and _valid_read(registry.get(name))}
        if eligible_read == {gateway.name}:
            learned.setdefault(gateway.name, set()).add(operation)
            diag.append({"stage": operation, "status": "verified_live_discovery"})
        else:
            diag.append({"stage": operation, "reason": (
                "search_ambiguous" if len(eligible_read) > 1
                else "search_no_exact_mapping"
            )})
    return learned, diag


__all__ = ["discover_device_operations", "advertised_operation"]

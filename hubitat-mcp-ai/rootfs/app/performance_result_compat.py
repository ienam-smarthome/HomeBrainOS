"""Compatibility normalization for known upstream performance-result defects."""

from __future__ import annotations

import re
from typing import Any

from mcp_client import MCPToolResult

_PERFORMANCE_TOOL = "hub_get_performance_stats"
_NUMERIC = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


def _numeric_database_value(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    return isinstance(value, str) and bool(_NUMERIC.fullmatch(value.strip()))


def _normalize_database_size(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_database_size(item) for item in value]
    if not isinstance(value, dict):
        return value
    normalized = {key: _normalize_database_size(item) for key, item in value.items()}
    if "databaseSizeMB" in normalized:
        return normalized
    raw = normalized.get("databaseSizeKB")
    if not _numeric_database_value(raw):
        return normalized
    normalized.pop("databaseSizeKB", None)
    normalized["databaseSizeMB"] = raw
    normalized["databaseSizeRaw"] = {
        "field": "databaseSizeKB",
        "value": raw,
        "note": (
            "Legacy upstream MCP label retained here for provenance. On the affected "
            "server version /hub/advanced/databaseSize supplies the numeric MB value; "
            "HomeBrain preserves that number without multiplying or dividing it."
        ),
    }
    return normalized


def normalize_performance_result(
    name: str, arguments: dict[str, Any], result: MCPToolResult
) -> MCPToolResult:
    """Relabel the affected performance database metric without changing its value."""
    sub_tool = str(arguments.get("tool") or "") if isinstance(arguments, dict) else ""
    if name != _PERFORMANCE_TOOL and sub_tool != _PERFORMANCE_TOOL:
        return result
    if result.is_error or not isinstance(result.data, dict):
        return result
    normalized = _normalize_database_size(result.data)
    if normalized == result.data:
        return result
    return MCPToolResult(
        name=result.name,
        arguments=result.arguments,
        raw=result.raw,
        text=result.text,
        data=normalized,
        is_error=result.is_error,
    )

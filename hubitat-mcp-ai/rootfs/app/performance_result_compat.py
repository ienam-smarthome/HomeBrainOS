"""Compatibility normalization for known upstream performance-result defects."""

from __future__ import annotations

import re
from typing import Any

from mcp_client import MCPToolResult

_PERFORMANCE_TOOLS = {"hub_get_metrics", "hub_get_performance_stats"}
_NUMERIC = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_NUMBER_UNIT = re.compile(
    r"^\s*([+-]?\d+(?:\.\d+)?)\s*(B|KB|MB|GB)\s*$",
    re.IGNORECASE,
)
_FREE_MEMORY_GENERIC_KEYS = {
    "freememory",
    "free_memory",
    "memoryfree",
    "memory_free",
}
_FREE_MEMORY_KB_KEYS = {
    "freememorykb",
    "free_memory_kb",
    "memoryfreekb",
    "memory_free_kb",
}
_FREE_MEMORY_MB_KEYS = {
    "freememorymb",
    "free_memory_mb",
    "memoryfreemb",
    "memory_free_mb",
}
_FREE_MEMORY_UNIT_KEYS = {
    "freememoryunit",
    "free_memory_unit",
    "memoryfreeunit",
    "memory_free_unit",
}


def _numeric_database_value(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    return isinstance(value, str) and bool(_NUMERIC.fullmatch(value.strip()))


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and _NUMERIC.fullmatch(value.strip()):
        return float(value.strip())
    return None


def _to_mb(number: float, unit: str) -> float:
    normalized = unit.upper()
    if normalized == "B":
        return number / (1024.0 * 1024.0)
    if normalized == "KB":
        return number / 1024.0
    if normalized == "GB":
        return number * 1024.0
    return number


def _clean_mb(value: float) -> float | int:
    rounded = round(float(value), 2)
    return int(rounded) if rounded.is_integer() else rounded


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


def _explicit_memory_value(key: str, value: Any, mapping: dict[str, Any]) -> tuple[float, str] | None:
    folded = key.casefold()
    number = _number(value)

    if folded in _FREE_MEMORY_MB_KEYS and number is not None:
        return number, "MB"
    if folded in _FREE_MEMORY_KB_KEYS and number is not None:
        return number, "KB"

    if folded not in _FREE_MEMORY_GENERIC_KEYS:
        return None

    if isinstance(value, str):
        match = _NUMBER_UNIT.fullmatch(value)
        if match:
            return float(match.group(1)), match.group(2).upper()

    # A sibling unit field is also explicit evidence. A bare generic number with
    # no unit is intentionally left alone rather than guessed from magnitude.
    for unit_key, unit_value in mapping.items():
        if str(unit_key).casefold() not in _FREE_MEMORY_UNIT_KEYS:
            continue
        unit = str(unit_value or "").strip().upper()
        if unit in {"B", "KB", "MB", "GB"} and number is not None:
            return number, unit
    return None


def _normalize_free_memory(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_free_memory(item) for item in value]
    if not isinstance(value, dict):
        return value

    original = dict(value)
    normalized = {key: _normalize_free_memory(item) for key, item in value.items()}

    # Do not replace an already-canonical field. This also makes the transform
    # idempotent when a result passes through compatibility normalization twice.
    if any(str(key).casefold() in _FREE_MEMORY_MB_KEYS for key in normalized):
        return normalized

    for key, raw in original.items():
        explicit = _explicit_memory_value(str(key), raw, original)
        if explicit is None:
            continue
        number, unit = explicit
        normalized["freeMemoryMB"] = _clean_mb(_to_mb(number, unit))
        normalized["freeMemoryRaw"] = {
            "field": str(key),
            "value": raw,
            "unit": unit,
            "note": "Canonicalized from an explicit upstream free-memory unit; no unit was inferred from magnitude.",
        }
        break
    return normalized


def normalize_performance_result(
    name: str, arguments: dict[str, Any], result: MCPToolResult
) -> MCPToolResult:
    """Canonicalize known performance fields without inventing missing units."""
    sub_tool = str(arguments.get("tool") or "") if isinstance(arguments, dict) else ""
    if name not in _PERFORMANCE_TOOLS and sub_tool not in _PERFORMANCE_TOOLS:
        return result
    if result.is_error or not isinstance(result.data, dict):
        return result

    normalized = _normalize_database_size(result.data)
    normalized = _normalize_free_memory(normalized)
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

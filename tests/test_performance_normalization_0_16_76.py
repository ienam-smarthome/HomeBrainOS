from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPToolResult  # noqa: E402
from performance_result_compat import normalize_performance_result  # noqa: E402


def _result(data: dict) -> MCPToolResult:
    return MCPToolResult(
        name="hub_read_diagnostics",
        arguments={"tool": "hub_get_metrics"},
        raw={},
        text="",
        data=data,
    )


def _normalize(data: dict) -> dict:
    result = normalize_performance_result(
        "hub_read_diagnostics",
        {"tool": "hub_get_metrics"},
        _result(data),
    )
    assert isinstance(result.data, dict)
    return result.data


def test_01676_explicit_free_memory_kb_string_gets_canonical_mb() -> None:
    data = _normalize({"current": {"freeMemory": "916404 KB"}})
    assert data["current"]["freeMemoryMB"] == 894.93
    assert data["current"]["freeMemoryRaw"]["value"] == "916404 KB"
    assert data["current"]["freeMemoryRaw"]["unit"] == "KB"


def test_01676_free_memory_kb_key_gets_canonical_mb() -> None:
    data = _normalize({"current": {"freeMemoryKB": 916404}})
    assert data["current"]["freeMemoryMB"] == 894.93
    assert data["current"]["freeMemoryRaw"]["field"] == "freeMemoryKB"


def test_01676_generic_free_memory_with_explicit_sibling_unit_gets_canonical_mb() -> None:
    data = _normalize({"current": {"freeMemory": 916404, "freeMemoryUnit": "KB"}})
    assert data["current"]["freeMemoryMB"] == 894.93


def test_01676_existing_mb_value_is_preserved() -> None:
    data = _normalize({"current": {"freeMemoryMB": 894.93}})
    assert data["current"]["freeMemoryMB"] == 894.93
    assert "freeMemoryRaw" not in data["current"]


def test_01676_unlabelled_generic_memory_number_is_not_guessed() -> None:
    original = {"current": {"freeMemory": 916404}}
    data = _normalize(original)
    assert data["current"] == original["current"]
    assert "freeMemoryMB" not in data["current"]


def test_01676_database_compatibility_still_preserves_numeric_mb_value() -> None:
    data = _normalize({"current": {"databaseSizeKB": 188}})
    assert data["current"]["databaseSizeMB"] == 188
    assert data["current"]["databaseSizeRaw"]["value"] == 188

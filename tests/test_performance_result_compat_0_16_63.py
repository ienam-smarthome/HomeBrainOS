from mcp_client import MCPToolResult
from performance_result_compat import normalize_performance_result


def _result(data):
    return MCPToolResult(name="hub_read_diagnostics", arguments={}, raw=None, text="", data=data, is_error=False)


def test_metrics_gateway_relabels_legacy_database_size_without_scaling():
    result = _result({"current": {"databaseSizeKB": "148", "freeMemoryKB": "1048576"}})
    normalized = normalize_performance_result(
        "hub_read_diagnostics", {"tool": "hub_get_metrics"}, result
    )
    assert normalized.data["current"]["databaseSizeMB"] == "148"
    assert normalized.data["current"]["databaseSizeRaw"]["value"] == "148"
    assert "databaseSizeKB" not in normalized.data["current"]


def test_direct_metrics_tool_is_supported_too():
    result = _result({"current": {"databaseSizeKB": 166}})
    normalized = normalize_performance_result("hub_get_metrics", {}, result)
    assert normalized.data["current"]["databaseSizeMB"] == 166

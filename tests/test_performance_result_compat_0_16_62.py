from mcp_client import MCPToolResult
from performance_result_compat import normalize_performance_result


def _result(data):
    return MCPToolResult(name="hub_read_system", arguments={"tool": "hub_get_performance_stats", "args": {}}, raw=None, text="", data=data, is_error=False)


def test_legacy_database_size_label_is_relabelled_without_scaling_and_raw_is_preserved():
    result = _result({"current": {"databaseSizeKB": "166", "freeMemoryKB": 200000}, "trends": [{"databaseSizeKB": "165"}]})
    normalized = normalize_performance_result("hub_read_system", {"tool": "hub_get_performance_stats", "args": {}}, result)
    assert normalized.data["current"]["databaseSizeMB"] == "166"
    assert "databaseSizeKB" not in normalized.data["current"]
    assert normalized.data["current"]["databaseSizeRaw"]["field"] == "databaseSizeKB"
    assert normalized.data["current"]["databaseSizeRaw"]["value"] == "166"
    assert normalized.data["trends"][0]["databaseSizeMB"] == "165"


def test_future_correct_database_size_mb_shape_is_unchanged():
    result = _result({"current": {"databaseSizeMB": "166"}})
    normalized = normalize_performance_result("hub_read_system", {"tool": "hub_get_performance_stats"}, result)
    assert normalized is result


def test_non_numeric_legacy_value_is_left_untouched():
    result = _result({"current": {"databaseSizeKB": "unavailable"}})
    normalized = normalize_performance_result("hub_read_system", {"tool": "hub_get_performance_stats"}, result)
    assert normalized is result
    assert normalized.data["current"]["databaseSizeKB"] == "unavailable"


def test_unrelated_tool_result_is_untouched():
    result = _result({"current": {"databaseSizeKB": "166"}})
    normalized = normalize_performance_result("hub_read_system", {"tool": "hub_get_logs"}, result)
    assert normalized is result

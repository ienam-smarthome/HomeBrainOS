from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_control_service import DeviceControlService  # noqa: E402
from device_query_service import DeviceQueryService  # noqa: E402
from mcp_client import MCPToolResult, tool_succeeded  # noqa: E402


def _result(data: object, *, is_error: bool = False) -> MCPToolResult:
    return MCPToolResult("some_tool", {}, {}, "", data, is_error=is_error)


def test_partial_failure_shape_is_treated_as_failure():
    """Regression test: {"success": true, "error": "..."} used to be
    treated as failure by DeviceControlService._tool_succeeded and as
    success by DeviceQueryService._tool_succeeded -- the identical
    response reported a failed control command as succeeded in one code
    path while a genuinely successful read was flagged as failed in the
    other, depending purely on which class happened to handle the call.
    Both now delegate to the same shared tool_succeeded() and must agree.
    """

    partial_failure = _result({"success": True, "error": "device unreachable"})

    assert tool_succeeded(partial_failure) is False
    assert DeviceControlService._tool_succeeded(partial_failure) is False
    assert DeviceQueryService._tool_succeeded(partial_failure) is False


def test_clean_success_is_still_success_in_both_classes():
    clean_success = _result({"success": True})

    assert tool_succeeded(clean_success) is True
    assert DeviceControlService._tool_succeeded(clean_success) is True
    assert DeviceQueryService._tool_succeeded(clean_success) is True


def test_explicit_failure_flag_is_failure_in_both_classes():
    explicit_failure = _result({"success": False})

    assert tool_succeeded(explicit_failure) is False
    assert DeviceControlService._tool_succeeded(explicit_failure) is False
    assert DeviceQueryService._tool_succeeded(explicit_failure) is False


def test_nested_result_failure_is_caught_in_both_classes():
    """DeviceQueryService's own _tool_succeeded never checked one level
    of nesting (result/data/output) the way DeviceControlService's did --
    now shared, so both catch a nested failure the same way."""

    nested_failure = _result({"result": {"success": False}})

    assert tool_succeeded(nested_failure) is False
    assert DeviceControlService._tool_succeeded(nested_failure) is False
    assert DeviceQueryService._tool_succeeded(nested_failure) is False


def test_transport_level_error_is_failure_regardless_of_payload():
    transport_error = _result({"success": True}, is_error=True)

    assert tool_succeeded(transport_error) is False
    assert DeviceControlService._tool_succeeded(transport_error) is False
    assert DeviceQueryService._tool_succeeded(transport_error) is False


def test_string_false_success_flag_is_treated_as_failure():
    """Regression test: a strict `data.get("success") is False` identity
    check never matches the string "false" -- and Hubitat/this codebase's
    own tool results are documented elsewhere (zbHealthy/zwHealthy,
    update_available, hub_alerts, the "changed" flag) to transmit
    boolean-ish flags as strings rather than JSON booleans. A response
    shaped like {"success": "false"} used to pass straight through this
    check as a successful read.
    """

    string_false = _result({"success": "false"})

    assert tool_succeeded(string_false) is False
    assert DeviceControlService._tool_succeeded(string_false) is False
    assert DeviceQueryService._tool_succeeded(string_false) is False


def test_string_false_success_flag_is_caught_when_nested_too():
    nested_string_false = _result({"result": {"success": "False"}})

    assert tool_succeeded(nested_string_false) is False


def test_string_true_success_flag_is_still_success():
    """A response reporting success as the string "true" (rather than a
    JSON boolean) must not be misread as failure by the new string
    handling -- only "false" (any case, with surrounding whitespace) is
    treated as a failure flag."""

    string_true = _result({"success": "true"})

    assert tool_succeeded(string_true) is True

"""Privacy-preserving V2 MCP read diagnostics.

Only locally classified failure categories are retained. Raw error messages,
exception arguments, URLs, HTTP bodies, headers, tokens and MCP text MUST NOT
enter investigation cases or exported diagnostic reports.
"""
from __future__ import annotations
import asyncio
from typing import Any

# Trust *only* the host-created code enum, not the remote error.message/code.
CODES = frozenset({
    "read_permission_changed", "read_timeout", "transport_timeout",
    "transport_unavailable", "mcp_protocol_error", "upstream_http_error",
    "read_execution_error", "mcp_tool_reported_error",
    "mcp_result_unsuccessful", "no_authoritative_result",
    "response_identity_mismatch", "executor_reported_failure",
    "unexpected_read_exception",
})


def classify_exception(exc: BaseException | None) -> str:
    if exc is None:
        return "read_execution_error"
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return "read_timeout"
    kind = type(exc).__name__
    if kind in ("ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout"):
        return "transport_timeout"
    if kind in ("ConnectError", "ReadError", "WriteError", "NetworkError",
                "RemoteProtocolError", "ConnectionError", "ConnectionResetError"):
        return "transport_unavailable"
    if kind in ("HTTPStatusError", "HTTPError"):
        return "upstream_http_error"
    if kind in ("MCPError", "MCPProtocolError"):
        return "mcp_protocol_error"
    return "read_execution_error"


def classify_execution(execution: Any, expected_name: str) -> str | None:
    """Check a ToolExecution without ever opening its free-form error text."""
    if execution is None:
        return "no_authoritative_result"
    if execution.name != expected_name or (
        execution.result is not None
        and execution.result.name != expected_name
    ):
        return "response_identity_mismatch"
    if execution.error is not None:
        return classify_exception(execution.error)
    if execution.success is not True:
        if execution.result is not None and execution.result.is_error:
            return "mcp_tool_reported_error"
        return "executor_reported_failure"
    if execution.result is None:
        return "no_authoritative_result"
    if execution.result.is_error:
        return "mcp_tool_reported_error"
    # An MCP tool can return a structured success:false without isError.
    # The host's canonical execution.result succeeded check is authoritative,
    # but the wrapper is still free to suppress its success flag above.
    return None


def safe_code(value: Any) -> str | None:
    return value if isinstance(value, str) and value in CODES else None


__all__ = ["CODES", "classify_exception", "classify_execution", "safe_code"]

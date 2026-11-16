"""Native MCP source-size refusal is not a successful source read.

Some upstream read-only tools return transport-success with a JSON payload
`response_too_large=true`: no requested native rows actually arrived.
Recognise this exact envelope without interpreting arbitrary source content.
This never retries, selects a different tool or changes action safety.
"""
from __future__ import annotations

import json


def native_read_size_refusal(result: object, expected_tool: str) -> dict | None:
    """Return a bounded source-error descriptor, or None.

    Only first-level native JSON and a single text-containing MCP result are
    considered. An untrusted nested device field or model message is not a
    native read-size failure. Call only on READ-ONLY selected native tools.
    """
    if not isinstance(result, dict) or result.get("isError"):
        return None
    payload = result
    if "content" in result:
        parts = result.get("content")
        if not isinstance(parts, list) or len(parts) != 1:
            return None
        part = parts[0]
        if (not isinstance(part, dict) or part.get("type") != "text"
                or not isinstance(part.get("text"), str)):
            return None
        try:
            payload = json.loads(part["text"])
        except (TypeError, ValueError):
            return None
    if not isinstance(payload, dict):
        return None
    if payload.get("response_too_large") is not True or payload.get("truncated") is not True:
        return None
    declared_tool = payload.get("tool")
    if declared_tool is not None and declared_tool != expected_tool:
        return None
    detail: dict = {
        "status": "native_response_too_large",
        "requested_tool": expected_tool,
        "usable_native_rows_returned": False,
        "read_not_source_success": True,
        "no_automatic_retry": True,
    }
    for key in ("estimatedBytes", "sizeLimitBytes"):
        value = payload.get(key)
        if type(value) is int and 0 <= value <= 10**9:
            detail[key] = value
    return detail

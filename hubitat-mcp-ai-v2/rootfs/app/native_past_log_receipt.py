"""Source-preserving adapter for the two native Hubitat past-log result shapes.

Both a direct {mode:past, entries:[...]} and a nested
{modes:{past:{entries:[...]}}} come from the ORIGINAL successful MCP reply.
Never flatten the saved receipt, merge pages, infer time-window completeness,
or interpret source 'total' as the count searched by this query.
"""
from __future__ import annotations

import json
from typing import Any


def original_past_log_source(
    receipt: object,
) -> tuple[dict[str, Any], dict[str, Any], str] | None:
    """Return (original MCP envelope, original past payload, variant), or None."""
    if not isinstance(receipt, dict):
        return None
    if (receipt.get("name") != "hub_get_logs"
            or receipt.get("success") is not True
            or receipt.get("operation_executed") is False):
        return None
    args = receipt.get("arguments")
    if not isinstance(args, dict):
        return None
    mode = args.get("mode")
    if mode != "past" and mode != ["past"]:
        return None
    raw = receipt.get("response")
    if not isinstance(raw, str) or len(raw) > 2_000_000:
        return None
    try:
        outer = json.loads(raw)
        if not isinstance(outer, dict) or outer.get("isError") is True:
            return None
        inner = outer
        if isinstance(outer.get("content"), list):
            parts = outer["content"]
            if (len(parts) != 1 or not isinstance(parts[0], dict)
                    or parts[0].get("type") != "text"
                    or not isinstance(parts[0].get("text"), str)):
                return None
            inner = json.loads(parts[0]["text"])
        if not isinstance(inner, dict) or inner.get("isError") is True:
            return None
    except (ValueError, TypeError):
        return None
    nested = inner.get("modes")
    if isinstance(nested, dict):
        past = nested.get("past")
        variant = "modes.past"
    else:
        past = inner
        variant = "mode.past_direct"
        if past.get("mode") not in (None, "past"):
            return None
    if not isinstance(past, dict) or past.get("isError") is True:
        return None
    if not isinstance(past.get("entries"), list):
        return None
    if (outer.get("truncated") is True
            or inner.get("response_too_large") is True
            or past.get("response_too_large") is True):
        # Never assert a successful complete receipt from an upstream refusal.
        return None
    return outer, past, variant

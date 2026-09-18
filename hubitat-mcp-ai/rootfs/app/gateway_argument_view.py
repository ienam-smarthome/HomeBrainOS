"""Canonical read-only view of gateway-style tool arguments.

Some MCP gateway schemas expose the operation selector directly as
{"tool": "...", "args": {...}}, while others wrap that same envelope one level
under {"args": {...}}. Runtime policy must recognise both shapes consistently
without rewriting the provider payload or guessing a gateway.
"""

from __future__ import annotations

from typing import Any


def gateway_operation(arguments: dict[str, Any] | None) -> str | None:
    """Return the selected gateway sub-operation from either supported shape."""

    if not isinstance(arguments, dict):
        return None
    direct = str(arguments.get("tool") or "").strip()
    if direct:
        return direct
    nested = arguments.get("args")
    if isinstance(nested, dict):
        value = str(nested.get("tool") or "").strip()
        if value:
            return value
    return None


def gateway_operation_args(arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Return the operation's argument payload without mutating the call."""

    if not isinstance(arguments, dict):
        return {}
    if str(arguments.get("tool") or "").strip():
        inner = arguments.get("args")
        return inner if isinstance(inner, dict) else {}
    nested = arguments.get("args")
    if isinstance(nested, dict) and str(nested.get("tool") or "").strip():
        inner = nested.get("args")
        return inner if isinstance(inner, dict) else {}
    return {}


__all__ = ["gateway_operation", "gateway_operation_args"]

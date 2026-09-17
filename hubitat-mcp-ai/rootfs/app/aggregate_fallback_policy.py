"""Request-local guard for expensive generic numeric aggregate fallbacks.

Some bridge/community devices expose measurements only as ``value``/``valueStr``.
Those generic fields are a useful fallback *after* a canonical aggregate query
(e.g. ``power``) returns no usable rows. They are not a reason to discard a
complete, non-empty canonical result and force a full detailed inventory read.

The policy is structural rather than prompt-specific: it observes only successful
``homebrain_query_devices`` result shape and later tool arguments in the same
request. RequestMetrics' context identity prevents state crossing concurrent or
sequential production requests.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from mcp_client import MCPToolResult
from request_metrics import active_request_identity


_QUERY_TOOL = "homebrain_query_devices"
_CANONICAL_METER_ATTRIBUTES = frozenset({"power", "energy"})
_GENERIC_FALLBACK_ATTRIBUTES = frozenset({"value", "valuestr"})

# (request identity, canonical attributes with complete non-empty proof)
_STATE: ContextVar[tuple[object | None, frozenset[str]]] = ContextVar(
    "homebrain_aggregate_fallback_state",
    default=(None, frozenset()),
)


def _state() -> tuple[object | None, frozenset[str]]:
    identity = active_request_identity()
    stored_identity, canonical = _STATE.get()
    if identity is None:
        return None, frozenset()
    if stored_identity is not identity:
        canonical = frozenset()
        _STATE.set((identity, canonical))
    return identity, canonical


def reset_aggregate_fallback_policy() -> None:
    """Explicit reset for isolated tests/direct callers."""

    _STATE.set((active_request_identity(), frozenset()))


def observe_aggregate_result(
    tool_name: str,
    arguments: dict[str, Any],
    result: MCPToolResult,
) -> None:
    """Remember complete, non-empty canonical meter aggregate evidence."""

    if tool_name != _QUERY_TOOL or result.is_error:
        return
    attribute = str(arguments.get("attribute") or "").strip().casefold()
    if attribute not in _CANONICAL_METER_ATTRIBUTES:
        return
    data = result.data
    if not isinstance(data, dict) or data.get("complete") is not True:
        return
    try:
        count = int(data.get("count") or 0)
    except (TypeError, ValueError):
        count = 0
    if count <= 0:
        return
    identity, canonical = _state()
    if identity is None:
        return
    _STATE.set((identity, frozenset({*canonical, attribute})))


def blocked_generic_fallback(
    tool_name: str,
    arguments: dict[str, Any],
) -> str | None:
    """Return a reason when generic value/valueStr fallback is now redundant."""

    if tool_name != _QUERY_TOOL:
        return None
    attribute = str(arguments.get("attribute") or "").strip().casefold()
    if attribute not in _GENERIC_FALLBACK_ATTRIBUTES:
        return None
    _identity, canonical = _state()
    if not canonical:
        return None
    proven = ", ".join(sorted(canonical))
    return (
        "Not executed: this request already has a complete, non-empty canonical "
        f"aggregate result for {proven}. Generic value/valueStr fallback is only "
        "appropriate when the canonical measurement returns no usable rows. "
        "Use the canonical result already gathered and answer the request now."
    )


__all__ = [
    "blocked_generic_fallback",
    "observe_aggregate_result",
    "reset_aggregate_fallback_policy",
]

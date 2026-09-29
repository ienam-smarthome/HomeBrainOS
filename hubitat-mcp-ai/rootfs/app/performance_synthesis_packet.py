from __future__ import annotations

from contextvars import ContextVar
from functools import wraps
from typing import Any

from tool_executor import ToolExecutor

_CAPTURED_TOOLS = {
    "hub_get_metrics",
    "hub_get_performance_stats",
    "hub_get_jobs",
    "hub_get_logs",
}
_MAX_ITEM_CHARS = 12000
_MAX_PACKET_CHARS = 32000
_PACKET: ContextVar[tuple[tuple[str, str], ...]] = ContextVar(
    "performance_synthesis_packet",
    default=(),
)


def _sub_tool(name: str, arguments: dict[str, Any]) -> str:
    leaf = str(arguments.get("tool") or "").strip()
    return leaf or str(name or "").strip()


def _append_packet(sub_tool: str, content: str) -> None:
    if sub_tool not in _CAPTURED_TOOLS:
        return
    text = str(content or "").strip()
    if not text:
        return
    text = text[:_MAX_ITEM_CHARS]
    rows = [row for row in _PACKET.get() if row[0] != sub_tool]
    rows.append((sub_tool, text))
    while sum(len(name) + len(value) for name, value in rows) > _MAX_PACKET_CHARS:
        rows.pop(0)
        if not rows:
            break
    _PACKET.set(tuple(rows))


def consume_performance_synthesis_packet() -> list[tuple[str, str]]:
    """Return and clear the current request's captured provider-safe payloads."""

    rows = list(_PACKET.get())
    _PACKET.set(())
    return rows


def install_tool_executor_capture() -> None:
    """Capture selected normalized ToolExecutor payloads on the serving path.

    ToolExecutor.result_payload() has already applied precise-location redaction and
    bounded the provider-visible payload. Wrapping execute() here avoids another MCP
    read while preserving the exact normalized evidence the original model saw.
    ContextVar isolation keeps concurrent FastAPI requests separate.
    """

    current = ToolExecutor.execute
    if getattr(current, "_homebrain_performance_packet_capture", False):
        return

    @wraps(current)
    async def wrapped(self: ToolExecutor, name: str, arguments: dict[str, Any], *args: Any, **kwargs: Any):
        execution = await current(self, name, arguments, *args, **kwargs)
        if getattr(execution, "success", False):
            execution_arguments = getattr(execution, "arguments", None)
            safe_arguments = (
                dict(execution_arguments)
                if isinstance(execution_arguments, dict)
                else dict(arguments or {})
            )
            _append_packet(
                _sub_tool(name, safe_arguments),
                str(getattr(execution, "content", "") or ""),
            )
        return execution

    setattr(wrapped, "_homebrain_performance_packet_capture", True)
    ToolExecutor.execute = wrapped


__all__ = [
    "consume_performance_synthesis_packet",
    "install_tool_executor_capture",
]

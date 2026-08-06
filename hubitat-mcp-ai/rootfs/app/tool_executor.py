"""Structured tool execution mechanics for the Hubitat MCP agent."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from evidence_recorder import EvidenceRecorder
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult
from request_metrics import add_active_metric_ms, increment_active_metric
from tool_registry import ToolEffect, classify_tool_effect


logger = logging.getLogger("HomeBrainOS.ToolExecutor")
ToolHandler = Callable[[dict[str, Any]], Awaitable[MCPToolResult]]
_SEARCH_TOOL = "hub_search_tools"


@dataclass(slots=True)
class ToolExecution:
    name: str
    arguments: dict[str, Any]
    effect: ToolEffect
    success: bool
    elapsed_ms: int
    content: str
    result: MCPToolResult | None = None
    error: Exception | None = None


class ToolExecutor:
    """Execute declared or local tools and emit one evidence receipt."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        evidence: EvidenceRecorder,
        *,
        local_handlers: dict[str, ToolHandler] | None = None,
        max_tool_result_chars: int = 24000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.mcp = mcp_client
        self.evidence = evidence
        self.local_handlers = dict(local_handlers or {})
        self.max_tool_result_chars = max(2000, int(max_tool_result_chars))
        self._clock = clock

    @staticmethod
    def succeeded(result: MCPToolResult) -> bool:
        if result.is_error:
            return False
        data = result.data
        if isinstance(data, dict):
            if data.get("success") is False or data.get("error"):
                return False
            for key in ("result", "data", "output"):
                nested = data.get(key)
                if isinstance(nested, dict) and (
                    nested.get("success") is False or nested.get("error")
                ):
                    return False
        return True

    @staticmethod
    def result_summary(result: MCPToolResult) -> str:
        data = result.data
        if isinstance(data, dict):
            keys = ", ".join(map(str, list(data)[:10]))
            return f"object fields: {keys}" if keys else "empty object"
        if isinstance(data, list):
            return f"{len(data)} result items"
        text = str(result.text or data or "").strip()
        return (text[:157] + "...") if len(text) > 160 else (text or "empty result")

    def result_payload(self, result: MCPToolResult) -> str:
        payload = (
            {"error": result.text or "MCP tool failed"}
            if result.is_error
            else {"result": result.data if result.data is not None else result.text}
        )
        serialized = json.dumps(payload, ensure_ascii=False, default=str)
        if len(serialized) <= self.max_tool_result_chars:
            return serialized
        return json.dumps({
            "result_excerpt": serialized[: self.max_tool_result_chars],
            "truncated": True,
            "original_chars": len(serialized),
            "instruction": "Use pagination or a narrower query for more detail.",
        }, ensure_ascii=False)

    @staticmethod
    def _record_execution_metrics(
        name: str,
        elapsed_ms: int,
        *,
        remote: bool,
    ) -> None:
        if remote:
            add_active_metric_ms("mcp", elapsed_ms)
        if name == _SEARCH_TOOL:
            increment_active_metric("tool_discovery_calls")
            add_active_metric_ms("tool_discovery", elapsed_ms)

    def _invalidate_live_device_snapshot(self) -> None:
        invalidator = getattr(self.mcp, "invalidate_live_device_snapshot", None)
        if callable(invalidator):
            invalidator()

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        tool: MCPTool | None = None,
        supports_live_claim: bool = True,
        evidence_kind: str = "tool_result",
        mutates: bool | None = None,
        record_evidence: bool = True,
    ) -> ToolExecution:
        safe_arguments = deepcopy(arguments)
        receipt_arguments = deepcopy(arguments)
        declared_tool = tool or MCPTool(name, name, {})
        effect = classify_tool_effect(declared_tool, receipt_arguments)
        handler = self.local_handlers.get(name)
        remote = handler is None
        if effect.mutates:
            self._invalidate_live_device_snapshot()
        started = self._clock()
        try:
            result = (
                await handler(safe_arguments)
                if handler is not None
                else await self.mcp.call_tool(name, safe_arguments)
            )
            elapsed_ms = round((self._clock() - started) * 1000)
            self._record_execution_metrics(name, elapsed_ms, remote=remote)
            success = self.succeeded(result)
            if record_evidence:
                self.evidence.record(
                    name, receipt_arguments, success=success, elapsed_ms=elapsed_ms,
                    summary=self.result_summary(result),
                    supports_live_claim=supports_live_claim,
                    evidence_kind=evidence_kind,
                    mutates=effect.mutates if mutates is None else bool(mutates),
                    effect=effect,
                )
            logger.info("Tool %s completed in %.3fs", name, elapsed_ms / 1000)
            if effect.mutates:
                self._invalidate_live_device_snapshot()
            return ToolExecution(
                name=name, arguments=receipt_arguments, effect=effect,
                success=success, elapsed_ms=elapsed_ms,
                content=self.result_payload(result), result=result,
            )
        except Exception as exc:
            elapsed_ms = round((self._clock() - started) * 1000)
            self._record_execution_metrics(name, elapsed_ms, remote=remote)
            if record_evidence:
                self.evidence.record(
                    name, receipt_arguments, success=False, elapsed_ms=elapsed_ms,
                    summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                    supports_live_claim=supports_live_claim,
                    evidence_kind=evidence_kind,
                    mutates=effect.mutates if mutates is None else bool(mutates),
                    effect=effect,
                )
            logger.exception("Tool %s failed", name)
            if effect.mutates:
                self._invalidate_live_device_snapshot()
            return ToolExecution(
                name=name, arguments=receipt_arguments, effect=effect,
                success=False, elapsed_ms=elapsed_ms,
                content=json.dumps({"error": str(exc)[:1000]}), error=exc,
            )


__all__ = ["ToolExecution", "ToolExecutor", "ToolHandler"]
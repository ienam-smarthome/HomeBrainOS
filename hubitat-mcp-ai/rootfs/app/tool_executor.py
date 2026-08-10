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
from location_privacy import redact_precise_location
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult
from mcp_client import tool_succeeded as _shared_tool_succeeded
from request_metrics import add_active_metric_ms, increment_active_metric
from tool_registry import ToolEffect, classify_tool_effect


logger = logging.getLogger("HomeBrainOS.ToolExecutor")
ToolHandler = Callable[[dict[str, Any]], Awaitable[MCPToolResult]]
_SEARCH_TOOL = "hub_search_tools"

# Some Home-Assistant-bridged / community-driver devices (observed on every
# "Octopus Energy" sensor on the user's real hub) never populate a named
# attribute like "power" -- they only report a bare "value" (frequently
# null at the moment it's read) alongside a human-formatted "valueStr"
# (e.g. "231 W"). When the model calls the raw hub-gateway
# hub_get_device_attribute sub-tool for attribute="value" and gets back
# null, it has no code-level nudge to also check "valueStr" -- unlike the
# local homebrain_* fast path, which already has this fallback baked into
# DeviceQueryService._attribute_value(). Relying on prompt prose alone for
# the raw gateway path proved unreliable in live testing (the model
# sometimes reported "returning a null value" instead of retrying).
# To make this deterministic rather than probabilistic, transparently
# retry with attribute="valueStr" on the same device and merge the result
# in, so the model never has to guess or spend an extra slow round trip.
_DEVICE_ATTRIBUTE_SUB_TOOL = "hub_get_device_attribute"
_GENERIC_VALUE_ATTRIBUTE = "value"
_GENERIC_VALUE_FALLBACK_ATTRIBUTE = "valueStr"


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
        """Delegates to the shared mcp_client.tool_succeeded() rather than
        repeating its own strict `is False` identity check -- this was an
        independent third copy of the exact same check (alongside
        device_control_service.py and device_query_service.py's now-shared
        implementations), and it gates `ToolExecution.success`, which
        `confirmed_action_coordinator.py` and every other consumer of a
        `ToolExecution` treats as authoritative. A strict `is False` check
        never matches a string "false" success flag -- see
        tool_succeeded()'s own docstring for the fuller history of this bug
        class across this codebase.
        """

        return _shared_tool_succeeded(result)

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
        # Precise-location attributes (GPS coordinates, street addresses, map
        # tiles, journey logs) are stripped here -- the single point every
        # provider-bound tool message passes through -- before anything is
        # serialised into the conversation sent to the model. See
        # location_privacy.py for what is redacted and why.
        safe_data = (
            redact_precise_location(result.data) if result.data is not None else None
        )
        payload = (
            {"error": result.text or "MCP tool failed"}
            if result.is_error
            else {"result": safe_data if safe_data is not None else result.text}
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

    @staticmethod
    def _wants_generic_value_backfill(
        arguments: dict[str, Any], result: MCPToolResult
    ) -> bool:
        """True when a raw hub_get_device_attribute(attribute='value') call
        came back null and hasn't already been enriched with valueStr."""

        if result.is_error or arguments.get("tool") != _DEVICE_ATTRIBUTE_SUB_TOOL:
            return False
        inner_args = arguments.get("args")
        if not isinstance(inner_args, dict):
            return False
        if inner_args.get("attribute") != _GENERIC_VALUE_ATTRIBUTE:
            return False
        data = result.data
        if not isinstance(data, dict):
            return False
        if data.get(_GENERIC_VALUE_ATTRIBUTE) is not None:
            return False
        return not data.get(_GENERIC_VALUE_FALLBACK_ATTRIBUTE)

    async def _backfill_null_generic_value(
        self, name: str, arguments: dict[str, Any], result: MCPToolResult
    ) -> MCPToolResult:
        """Transparently retry a null 'value' attribute read with 'valueStr'
        on the same device and merge the reading in. See module docstring
        above for why this must be deterministic, not prompt-only."""

        inner_args = dict(arguments.get("args") or {})
        inner_args["attribute"] = _GENERIC_VALUE_FALLBACK_ATTRIBUTE
        followup_arguments = {**arguments, "args": inner_args}
        try:
            followup = await self.mcp.call_tool(name, followup_arguments)
        except Exception:
            logger.exception("valueStr backfill call failed for %s", name)
            return result
        if followup.is_error or not isinstance(followup.data, dict):
            return result
        value_str = followup.data.get(_GENERIC_VALUE_FALLBACK_ATTRIBUTE)
        if not value_str:
            return result
        merged_data = dict(result.data)
        merged_data[_GENERIC_VALUE_FALLBACK_ATTRIBUTE] = value_str
        merged_data["value_backfill_note"] = (
            "The 'value' attribute was null at read time; 'valueStr' was "
            "fetched automatically and is the reading to report."
        )
        return MCPToolResult(
            name=result.name,
            arguments=result.arguments,
            raw=result.raw,
            text=result.text,
            data=merged_data,
            is_error=result.is_error,
        )

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
            if remote and self._wants_generic_value_backfill(
                safe_arguments, result
            ):
                result = await self._backfill_null_generic_value(
                    name, safe_arguments, result
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
"""Structured tool execution mechanics for the Hubitat MCP agent."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from aggregate_fallback_policy import (
    blocked_generic_fallback,
    observe_aggregate_result,
)
from evidence_recorder import EvidenceRecorder
from history_result_enrichment import enrich_history_result, prepare_history_arguments
from history_temporal_analysis import history_temporal_evidence_details
from location_privacy import redact_precise_location
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult
from mcp_client import tool_succeeded as _shared_tool_succeeded
from reasoning_policy import (
    EVIDENCE_REVIEW_INSTRUCTION,
    FINAL_SYNTHESIS_INSTRUCTION,
    blocked_selected_target,
    claim_model_tool_call,
    register_model_tool_execution,
    should_defer_deterministic_presentation,
)
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
        """Delegate to the shared MCP success normalizer."""

        return _shared_tool_succeeded(result)

    @staticmethod
    def result_details(result: MCPToolResult) -> dict[str, Any] | None:
        """Return bounded structured proof that is useful in technical receipts."""

        return history_temporal_evidence_details(result.data)

    @staticmethod
    def result_summary(result: MCPToolResult) -> str:
        details = ToolExecutor.result_details(result)
        if details is not None:
            temporal = details.get("temporalAnalysis")
            if isinstance(temporal, dict):
                interval_count = temporal.get("intervalCount")
                total_duration = temporal.get("totalActiveDuration")
                total_seconds = temporal.get("totalActiveSeconds")
                longest = temporal.get("longestActiveDuration")
                coverage = temporal.get("coverage")
                reliability = str(temporal.get("durationReliability") or "").strip()
                qualifier = " lower-bound" if temporal.get("totalIsLowerBound") else ""
                reliability_suffix = f", reliability={reliability}" if reliability else ""
                return (
                    "temporal history: "
                    f"intervals={interval_count}, total={total_duration} "
                    f"({total_seconds}s), longest={longest}, coverage={coverage}{qualifier}"
                    f"{reliability_suffix}"
                )
            observed = details.get("observedEvents")
            if isinstance(observed, list):
                attribute = str(details.get("attribute") or "events").strip()
                return (
                    f"event history: attribute={attribute}, "
                    f"observed_rows={len(observed)}, "
                    f"source_rows={details.get('sourceEventCount')}"
                )
        data = result.data
        if isinstance(data, dict):
            keys = ", ".join(map(str, list(data)[:10]))
            return f"object fields: {keys}" if keys else "empty object"
        if isinstance(data, list):
            return f"{len(data)} result items"
        text = str(result.text or data or "").strip()
        return (text[:157] + "...") if len(text) > 160 else (text or "empty result")

    def result_payload(
        self,
        result: MCPToolResult,
        *,
        reasoning_active: bool = False,
    ) -> str:
        # Precise-location attributes (GPS coordinates, street addresses, map
        # tiles, journey logs) are stripped here -- the single point every
        # provider-bound tool message passes through -- before anything is
        # serialised into the conversation sent to the model.
        safe_data = (
            redact_precise_location(result.data) if result.data is not None else None
        )
        payload: dict[str, Any] = (
            {"error": result.text or "MCP tool failed"}
            if result.is_error
            else {"result": safe_data if safe_data is not None else result.text}
        )
        # Only an execution that exactly matches a native model-emitted tool
        # call receives the generic evidence-review contract. Pre-model tool
        # discovery, direct deterministic paths, and resumed confirmations keep
        # their historical payload shape even if they happen in the same async
        # context as an earlier model round.
        if reasoning_active:
            payload["host_instruction"] = EVIDENCE_REVIEW_INSTRUCTION
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
        """Retry a null generic value read with valueStr on the same device."""

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
        # Claim the exact model-emitted signature before applying deterministic
        # execution-time normalization. Otherwise adding a 50-row semantic-history
        # bound would make the call look non-model-authored and bypass the reasoning
        # budget/evidence-review contracts.
        model_arguments = deepcopy(arguments)
        reasoning_round_size = claim_model_tool_call(name, model_arguments)
        safe_arguments = prepare_history_arguments(name, model_arguments)
        receipt_arguments = deepcopy(safe_arguments)
        declared_tool = tool or MCPTool(name, name, {})
        effect = classify_tool_effect(declared_tool, receipt_arguments)
        handler = self.local_handlers.get(name)
        remote = handler is None

        selection_reason = (
            blocked_selected_target(name, safe_arguments)
            if reasoning_round_size > 0 and not effect.mutates
            else None
        )
        if selection_reason is not None:
            logger.info("Skipped read %s that contradicted the selected device", name)
            return ToolExecution(
                name=name,
                arguments=receipt_arguments,
                effect=effect,
                success=True,
                elapsed_ms=0,
                content=json.dumps(
                    {
                        "note": selection_reason,
                        "host_instruction": EVIDENCE_REVIEW_INSTRUCTION,
                    },
                    ensure_ascii=False,
                ),
                result=None,
            )

        # A generic value/valueStr aggregate is an expensive fallback path because
        # those fields are not part of hubitat://context and therefore require the
        # complete detailed inventory. Once this request already has a complete,
        # non-empty canonical power/energy aggregate, do not let the model discard
        # it and pay ~30 seconds to ask the same question through a generic field.
        # The guard is current-request structural state, not prompt wording.
        fallback_reason = (
            blocked_generic_fallback(name, safe_arguments)
            if reasoning_round_size > 0 and not effect.mutates
            else None
        )
        if fallback_reason is not None:
            logger.info("Skipped redundant aggregate fallback %s", name)
            return ToolExecution(
                name=name,
                arguments=receipt_arguments,
                effect=effect,
                success=True,
                elapsed_ms=0,
                content=json.dumps(
                    {
                        "note": fallback_reason,
                        "host_instruction": FINAL_SYNTHESIS_INSTRUCTION,
                    },
                    ensure_ascii=False,
                ),
                result=None,
            )

        # Only exact native model-emitted calls participate in the generic read
        # budget. Pre-model discovery, deterministic direct reads, confirmations,
        # and verification calls have reasoning_round_size == 0 and are unchanged.
        if (
            reasoning_round_size > 0
            and not register_model_tool_execution(
                name=name,
                arguments=safe_arguments,
                mutates=effect.mutates,
            )
        ):
            logger.info("Skipped model read %s because reasoning budget is exhausted", name)
            return ToolExecution(
                name=name,
                arguments=receipt_arguments,
                effect=effect,
                success=True,
                elapsed_ms=0,
                content=json.dumps(
                    {
                        "note": (
                            "Not executed: the host read-reasoning budget for this "
                            "request is exhausted. Synthesize from evidence already "
                            "gathered."
                        ),
                        "host_instruction": FINAL_SYNTHESIS_INSTRUCTION,
                    },
                    ensure_ascii=False,
                ),
                result=None,
            )

        if effect.mutates:
            self._invalidate_live_device_snapshot()
        started = self._clock()
        try:
            result = (
                await handler(safe_arguments)
                if handler is not None
                else await self.mcp.call_tool(name, safe_arguments)
            )
            # Semantic history may be requested without an explicit binary state
            # attribute. Derive one only when the returned rows make exactly one
            # supported state-pair attribute unambiguous, and close an otherwise
            # unknown empty-window boundary from the first later transition when
            # the complete-page invariants prove that inference.
            result = enrich_history_result(name, result)
            if remote and self._wants_generic_value_backfill(
                safe_arguments, result
            ):
                result = await self._backfill_null_generic_value(
                    name, safe_arguments, result
                )
            elapsed_ms = round((self._clock() - started) * 1000)
            self._record_execution_metrics(name, elapsed_ms, remote=remote)
            success = self.succeeded(result)
            if success:
                observe_aggregate_result(name, receipt_arguments, result)
            if record_evidence:
                self.evidence.record(
                    name,
                    receipt_arguments,
                    success=success,
                    elapsed_ms=elapsed_ms,
                    summary=self.result_summary(result),
                    supports_live_claim=supports_live_claim,
                    evidence_kind=evidence_kind,
                    mutates=effect.mutates if mutates is None else bool(mutates),
                    effect=effect,
                    details=self.result_details(result),
                )
            logger.info("Tool %s completed in %.3fs", name, elapsed_ms / 1000)
            if effect.mutates:
                self._invalidate_live_device_snapshot()

            # In a multi-tool model round, selected deterministic presenters
            # would otherwise return from the orchestrator after the first call
            # and silently skip every later call in that same native response.
            presentation_result = (
                None
                if should_defer_deterministic_presentation(
                    name,
                    result.data,
                    round_size=reasoning_round_size,
                )
                else result
            )
            return ToolExecution(
                name=name,
                arguments=receipt_arguments,
                effect=effect,
                success=success,
                elapsed_ms=elapsed_ms,
                content=self.result_payload(
                    result,
                    reasoning_active=reasoning_round_size > 0,
                ),
                result=presentation_result,
            )
        except Exception as exc:
            elapsed_ms = round((self._clock() - started) * 1000)
            self._record_execution_metrics(name, elapsed_ms, remote=remote)
            if record_evidence:
                self.evidence.record(
                    name,
                    receipt_arguments,
                    success=False,
                    elapsed_ms=elapsed_ms,
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
                name=name,
                arguments=receipt_arguments,
                effect=effect,
                success=False,
                elapsed_ms=elapsed_ms,
                content=json.dumps({"error": str(exc)[:1000]}),
                error=exc,
            )


__all__ = ["ToolExecution", "ToolExecutor", "ToolHandler"]

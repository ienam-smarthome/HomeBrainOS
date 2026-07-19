from __future__ import annotations

from typing import Any

from fallback_router import _device_id, _label, _normalise
from mcp_client import MCPError, MCPToolResult
from semantic_metric_comparison import (
    MeasurementSpec,
    SemanticMetricComparisonExecutor,
    measurement_reading,
)


_DETAIL_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "currentStates",
    "states",
    "state",
    "attributes",
    "capabilities",
    "disabled",
    "lastActivity",
]

_SUMMARY_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "currentStates",
    "states",
    "state",
    "disabled",
    "lastActivity",
]


def _state_map(item: dict[str, Any]) -> dict[str, Any]:
    """Flatten every common Hubitat state container without losing units."""

    merged: dict[str, Any] = {}
    for container_key in ("attributes", "state", "states", "currentStates"):
        container = item.get(container_key)
        if isinstance(container, dict):
            merged.update(container)
            continue
        if not isinstance(container, list):
            continue
        for entry in container:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or entry.get("attribute") or entry.get("key")
            if name not in (None, ""):
                merged[str(name)] = dict(entry)
    return merged


def _row_key(item: dict[str, Any]) -> str:
    device_id = _device_id(item)
    if device_id:
        return f"id:{device_id}"
    label = _normalise(_label(item))
    return f"label:{label}" if label else ""


def _merge_rows(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge metadata and compact live rows, preferring the newest state values."""

    ordered: list[str] = []
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for raw in group:
            if not isinstance(raw, dict):
                continue
            key = _row_key(raw)
            if not key:
                continue
            if key not in merged:
                ordered.append(key)
                merged[key] = {}
            combined = merged[key]
            existing_states = _state_map(combined)
            incoming_states = _state_map(raw)
            combined.update(raw)
            if existing_states or incoming_states:
                combined["currentStates"] = {**existing_states, **incoming_states}
    return [merged[key] for key in ordered]


def _synthetic_result(
    capability: str,
    rows: list[dict[str, Any]],
    *,
    sources: list[str],
) -> MCPToolResult:
    data = {
        "devices": rows,
        "count": len(rows),
        "capabilityFilter": capability,
        "source": "semantic-live-state-merge",
        "evidenceSources": sources,
    }
    return MCPToolResult(
        name="hub_list_devices",
        arguments={
            "capabilityFilter": capability,
            "detailed": True,
            "liveStateMerged": True,
        },
        raw=data,
        text="",
        data=data,
        is_error=False,
    )


class LiveStateSemanticMetricComparisonExecutor(SemanticMetricComparisonExecutor):
    """Semantic comparison executor that requires an actual live state value.

    Some MCP Rule Server catalogues return useful capabilities and attribute
    definitions in detailed mode but put the current numeric value only in a compact
    capability-filtered ``currentStates`` response. The base semantic executor was
    accepting the detailed rows as complete evidence and therefore reported zero
    readings. This executor merges both shapes before any ranking is performed.
    """

    async def _fresh_capability_result(self, spec: MeasurementSpec) -> MCPToolResult:
        index = getattr(self.router, "device_index", None)
        client = getattr(index, "client", None) if index is not None else None
        client = client or getattr(self.router, "client", None)
        if client is None or not callable(getattr(client, "call_tool", None)):
            return await super()._fresh_capability_result(spec)

        invalidate = getattr(client, "invalidate", None)
        if callable(invalidate):
            await invalidate("devices")
        elif index is not None:
            await index.invalidate()

        sources: list[str] = []
        collected: list[list[dict[str, Any]]] = []
        errors: list[str] = []

        detailed = await self._call_capability(
            client,
            spec.capability,
            detailed=True,
        )
        if detailed.is_error:
            errors.append(detailed.text or f"Detailed {spec.capability} read failed")
        else:
            sources.append("detailed-currentStates+attributes")
            collected.append(self.router._device_rows(detailed.data))

        merged = _merge_rows(*collected)
        if self._contains_measurement(merged, spec):
            return _synthetic_result(spec.capability, merged, sources=sources)

        summary = await self._call_capability(
            client,
            spec.capability,
            detailed=False,
        )
        if summary.is_error:
            errors.append(summary.text or f"Summary {spec.capability} read failed")
        else:
            sources.append("summary-currentStates")
            collected.append(self.router._device_rows(summary.data))

        merged = _merge_rows(*collected)
        if self._contains_measurement(merged, spec):
            return _synthetic_result(spec.capability, merged, sources=sources)

        compact_capability = spec.capability.replace(" ", "")
        if compact_capability.lower() != spec.capability.lower():
            compact = await self._call_capability(
                client,
                compact_capability,
                detailed=False,
            )
            if compact.is_error:
                errors.append(compact.text or f"Summary {compact_capability} read failed")
            else:
                sources.append(f"summary-currentStates:{compact_capability}")
                collected.append(self.router._device_rows(compact.data))
                merged = _merge_rows(*collected)
                if self._contains_measurement(merged, spec):
                    return _synthetic_result(spec.capability, merged, sources=sources)

        # Keep the catalogue's local capability aliases as the final source. It is
        # valuable for custom drivers even when the exact server filter is empty.
        if index is not None:
            try:
                catalogue = await index.capability_result(
                    spec.capability,
                    detailed=True,
                    force=True,
                )
                if not catalogue.is_error:
                    sources.append("selected-device-capability-catalogue")
                    collected.append(self.router._device_rows(catalogue.data))
            except Exception as exc:
                errors.append(str(exc).strip() or type(exc).__name__)

        merged = _merge_rows(*collected)
        if merged:
            return _synthetic_result(spec.capability, merged, sources=sources)
        raise MCPError("; ".join(item for item in errors if item) or f"No {spec.capability} evidence returned")

    async def _fallback_detailed_result(self) -> MCPToolResult | None:
        index = getattr(self.router, "device_index", None)
        client = getattr(index, "client", None) if index is not None else None
        client = client or getattr(self.router, "client", None)
        if client is None or not callable(getattr(client, "call_tool", None)):
            return await super()._fallback_detailed_result()

        detailed = await client.call_tool(
            "hub_list_devices",
            {
                "detailed": True,
                "format": "detailed",
                "fields": list(_DETAIL_FIELDS),
            },
        )
        summary = await client.call_tool(
            "hub_list_devices",
            {
                "detailed": False,
                "format": "summary",
                "fields": list(_SUMMARY_FIELDS),
            },
        )
        groups: list[list[dict[str, Any]]] = []
        sources: list[str] = []
        if not detailed.is_error:
            groups.append(self.router._device_rows(detailed.data))
            sources.append("all-detailed-currentStates+attributes")
        if not summary.is_error:
            groups.append(self.router._device_rows(summary.data))
            sources.append("all-summary-currentStates")
        rows = _merge_rows(*groups)
        return _synthetic_result("all selected devices", rows, sources=sources) if rows else None

    @staticmethod
    async def _call_capability(
        client: Any,
        capability: str,
        *,
        detailed: bool,
    ) -> MCPToolResult:
        return await client.call_tool(
            "hub_list_devices",
            {
                "detailed": bool(detailed),
                "format": "detailed" if detailed else "summary",
                "capabilityFilter": capability,
                "fields": list(_DETAIL_FIELDS if detailed else _SUMMARY_FIELDS),
            },
        )

    @staticmethod
    def _contains_measurement(
        rows: list[dict[str, Any]],
        spec: MeasurementSpec,
    ) -> bool:
        return any(measurement_reading(item, spec) is not None for item in rows)


SemanticMetricComparisonExecutor = LiveStateSemanticMetricComparisonExecutor


__all__ = [
    "LiveStateSemanticMetricComparisonExecutor",
    "SemanticMetricComparisonExecutor",
]

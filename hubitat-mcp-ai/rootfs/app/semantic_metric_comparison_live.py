from __future__ import annotations

from typing import Any

from fallback_router import _device_id, _label, _normalise
from device_read_shapes import DETAILED_DEVICE_FIELDS, detailed_device_arguments
from mcp_client import MCPError, MCPToolResult
from semantic_metric_comparison import (
    MeasurementSpec,
    SemanticMetricComparisonExecutor,
    measurement_reading,
)


# Keep these request shapes deliberately conservative. They match the field sets
# already used successfully by the shared device index and avoid making a useful
# compact live-state read depend on optional detailed-catalogue fields.
_DETAIL_FIELDS = list(DETAILED_DEVICE_FIELDS)

_SUMMARY_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "currentStates",
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
    """Merge metadata and compact live rows, preferring later state values."""

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
    errors: list[str] | None = None,
) -> MCPToolResult:
    data = {
        "devices": rows,
        "count": len(rows),
        "capabilityFilter": capability,
        "source": "semantic-live-state-merge",
        "evidenceSources": sources,
        "evidenceErrors": list(errors or []),
    }
    return MCPToolResult(
        name="hub_list_devices",
        arguments={
            "capabilityFilter": capability,
            "detailed": False,
            "liveStateMerged": True,
        },
        raw=data,
        text="",
        data=data,
        is_error=False,
    )


class LiveStateSemanticMetricComparisonExecutor(SemanticMetricComparisonExecutor):
    """Semantic comparison executor that requires an actual live state value.

    The compact capability response is the first source because it is the known
    live ``currentStates`` shape. Detailed catalogue data is optional enrichment.
    Every request shape is isolated so one unsupported field list cannot push a
    recognised numeric comparison back to the Cloud planner.
    """

    async def _fresh_capability_result(
        self,
        spec: MeasurementSpec,
    ) -> MCPToolResult:
        index = getattr(self.router, "device_index", None)
        client = getattr(index, "client", None) if index is not None else None
        client = client or getattr(self.router, "client", None)

        errors: list[str] = []
        sources: list[str] = []
        collected: list[list[dict[str, Any]]] = []

        # The live Hubitat gateway exposes the complete Power Meter values in
        # the all-device detailed attribute response. Capability-filtered and
        # compact summary responses on this installation return metadata but
        # not usable power measurements. Use the proven authoritative shape
        # first so a power summary requires one logical MCP read.
        if spec.key == "power" and client is not None and callable(
            getattr(client, "call_tool", None)
        ):
            result = await self._safe_call(
                client,
                detailed_device_arguments(),
                "all-device detailed power evidence",
                errors,
            )
            if result is not None and not result.is_error:
                rows = self.router._device_rows(result.data)
                if rows and self._contains_measurement(rows, spec):
                    return _synthetic_result(
                        spec.capability,
                        rows,
                        sources=["all-device-detailed-attributes"],
                        errors=errors,
                    )

        # Primary path: use the shared compact all-device snapshot. The
        # Hubitat gateway reliably exposes live currentStates in this response,
        # while capability-filtered responses can return metadata without the
        # actual values. Metric extraction and filtering are performed locally.
        if index is not None:
            try:
                summary = await index.summary_result(force=False)
                if summary.is_error:
                    errors.append(
                        summary.text
                        or "shared device summary snapshot failed"
                    )
                else:
                    rows = self.router._device_rows(summary.data)
                    if rows:
                        sources.append("shared-summary-currentStates")
                        collected.append(rows)
                        merged = _merge_rows(*collected)
                        if self._contains_measurement(merged, spec):
                            return _synthetic_result(
                                spec.capability,
                                merged,
                                sources=sources,
                                errors=errors,
                            )
            except Exception as exc:
                errors.append(
                    "shared device summary snapshot: "
                    + (str(exc).strip() or type(exc).__name__)
                )

        if client is None or not callable(
            getattr(client, "call_tool", None)
        ):
            return await super()._fresh_capability_result(spec)

        # Compatibility fallback for installations without a usable shared
        # capability snapshot.
        if not collected:
            await self._collect_capability(
                client,
                spec,
                spec.capability,
                detailed=False,
                source="summary-currentStates",
                sources=sources,
                collected=collected,
                errors=errors,
            )
            merged = _merge_rows(*collected)
            if self._contains_measurement(merged, spec):
                return _synthetic_result(
                    spec.capability,
                    merged,
                    sources=sources,
                    errors=errors,
                )

        # Some custom drivers expose compact capability names without spaces.
        compact_capability = spec.capability.replace(" ", "")
        if compact_capability.lower() != spec.capability.lower():
            await self._collect_capability(
                client,
                spec,
                compact_capability,
                detailed=False,
                source=f"summary-currentStates:{compact_capability}",
                sources=sources,
                collected=collected,
                errors=errors,
            )
            merged = _merge_rows(*collected)
            if self._contains_measurement(merged, spec):
                return _synthetic_result(
                    spec.capability,
                    merged,
                    sources=sources,
                    errors=errors,
                )

        # Detailed metadata is only needed when compact state does not contain
        # a usable measurement.
        await self._collect_capability(
            client,
            spec,
            spec.capability,
            detailed=True,
            source="detailed-attributes",
            sources=sources,
            collected=collected,
            errors=errors,
        )
        merged = _merge_rows(*collected)
        if self._contains_measurement(merged, spec):
            return _synthetic_result(
                spec.capability,
                merged,
                sources=sources,
                errors=errors,
            )

        if merged:
            return _synthetic_result(
                spec.capability,
                merged,
                sources=sources,
                errors=errors,
            )

        raise MCPError(
            "; ".join(item for item in errors if item)
            or f"No {spec.capability} evidence returned"
        )

    async def _fallback_detailed_result(self) -> MCPToolResult | None:
        index = getattr(self.router, "device_index", None)
        client = getattr(index, "client", None) if index is not None else None
        client = client or getattr(self.router, "client", None)
        if client is None or not callable(getattr(client, "call_tool", None)):
            return await super()._fallback_detailed_result()

        groups: list[list[dict[str, Any]]] = []
        sources: list[str] = []
        errors: list[str] = []

        # All-device compact summary is again the primary live-state fallback.
        summary = await self._safe_call(
            client,
            {
                "detailed": False,
                "format": "summary",
                "fields": list(_SUMMARY_FIELDS),
            },
            "all selected-device summary",
            errors,
        )
        if summary is not None and not summary.is_error:
            rows = self.router._device_rows(summary.data)
            if rows:
                groups.append(rows)
                sources.append("all-summary-currentStates")

        detailed = await self._safe_call(
            client,
            {
                "detailed": True,
                "format": "detailed",
                "fields": list(_DETAIL_FIELDS),
            },
            "all selected-device details",
            errors,
        )
        if detailed is not None and not detailed.is_error:
            rows = self.router._device_rows(detailed.data)
            if rows:
                # Put metadata first and compact state last so live values win.
                groups.insert(0, rows)
                sources.insert(0, "all-detailed-attributes")

        rows = _merge_rows(*groups)
        return (
            _synthetic_result(
                "all selected devices",
                rows,
                sources=sources,
                errors=errors,
            )
            if rows
            else None
        )

    async def _collect_capability(
        self,
        client: Any,
        spec: MeasurementSpec,
        capability: str,
        *,
        detailed: bool,
        source: str,
        sources: list[str],
        collected: list[list[dict[str, Any]]],
        errors: list[str],
    ) -> None:
        result = await self._safe_call(
            client,
            {
                "detailed": bool(detailed),
                "format": "detailed" if detailed else "summary",
                "capabilityFilter": capability,
                "fields": list(_DETAIL_FIELDS if detailed else _SUMMARY_FIELDS),
            },
            f"{source} {capability}",
            errors,
        )
        if result is None:
            return
        if result.is_error:
            errors.append(result.text or f"{source} {capability} failed")
            return
        rows = self.router._device_rows(result.data)
        if rows:
            sources.append(source)
            collected.append(rows)

    @staticmethod
    async def _safe_call(
        client: Any,
        arguments: dict[str, Any],
        label: str,
        errors: list[str],
    ) -> MCPToolResult | None:
        try:
            return await client.call_tool("hub_list_devices", arguments)
        except Exception as exc:
            errors.append(f"{label}: {str(exc).strip() or type(exc).__name__}")
            return None

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

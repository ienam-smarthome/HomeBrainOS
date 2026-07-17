from __future__ import annotations

from typing import Any

from fast_fallback_device_types import FastFallbackRouter as DeviceTypeFastFallbackRouter
from mcp_client import MCPError, MCPToolResult


# Kingpanther MCP Rule Server v3.4.1 validates the fields list strictly. These
# are the fields currently accepted by hub_list_devices. Driver/type/category
# metadata must not be requested as fields because the server rejects the whole
# call before returning any devices.
_COMPATIBLE_DEVICE_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "currentStates",
    "attributes",
    "capabilities",
    "commands",
    "deviceNetworkId",
    "disabled",
    "lastActivity",
    "mcpManaged",
    "parentDeviceId",
]

_MINIMAL_DEVICE_FIELDS = [
    "id",
    "name",
    "label",
    "room",
    "currentStates",
    "capabilities",
]

_GENERIC_CAPABILITIES = {
    "actuator",
    "sensor",
    "refresh",
    "configuration",
    "initialize",
    "health check",
    "battery",
}


class FastFallbackRouter(DeviceTypeFastFallbackRouter):
    """Device-type inventory compatible with strict MCP field validation."""

    async def _all_devices_with_type_metadata(self) -> MCPToolResult:
        result = await self._device_inventory_call(_COMPATIBLE_DEVICE_FIELDS)

        # Keep compatibility with older/newer MCP builds whose accepted field set
        # may differ. A strict field error gets one conservative retry rather than
        # surfacing a raw Invalid params response to the user.
        if result.is_error and self._is_unknown_fields_error(result):
            result = await self._device_inventory_call(_MINIMAL_DEVICE_FIELDS)

        if result.is_error:
            raise MCPError(result.text or "Device-type inventory lookup failed")

        self._add_local_type_labels(result.data)
        return result

    async def _device_inventory_call(self, fields: list[str]) -> MCPToolResult:
        return await self._execute_catalog_tool(
            "hub_list_devices",
            "hub_read_devices",
            {
                "detailed": False,
                "format": "summary",
                "fields": list(fields),
            },
        )

    @staticmethod
    def _is_unknown_fields_error(result: MCPToolResult) -> bool:
        text = str(result.text or "").lower()
        return "unknown fields" in text or (
            "invalid params" in text and "valid:" in text and "fields" in text
        )

    def _add_local_type_labels(self, data: Any) -> None:
        """Derive a readable type label from supported capability metadata.

        The base presenter understands a local ``type`` key. Adding it after the
        MCP response preserves useful subtitles without requesting the unsupported
        remote ``type``/``deviceType``/``driverName``/``category`` fields.
        """
        for item in self._device_rows(data):
            if any(item.get(key) for key in ("deviceType", "type", "driverName", "category")):
                continue
            label = self._capability_type_label(item.get("capabilities"))
            if not label:
                label = self._attribute_type_label(item.get("currentStates"))
            if label:
                item["type"] = label

    @staticmethod
    def _capability_type_label(value: Any) -> str | None:
        names: list[str] = []
        if isinstance(value, list):
            entries = value
        elif value in (None, ""):
            entries = []
        else:
            entries = [value]

        for entry in entries:
            if isinstance(entry, dict):
                name = (
                    entry.get("displayName")
                    or entry.get("name")
                    or entry.get("label")
                    or entry.get("id")
                )
            else:
                name = entry
            text = str(name or "").strip()
            if not text or text.lower() in _GENERIC_CAPABILITIES:
                continue
            if text not in names:
                names.append(text)

        if not names:
            return None
        return " / ".join(names[:2])

    @staticmethod
    def _attribute_type_label(value: Any) -> str | None:
        if not isinstance(value, dict):
            return None
        keys = {str(key) for key in value}
        ordered = (
            ("motion", "Motion sensor"),
            ("contact", "Contact sensor"),
            ("temperature", "Temperature sensor"),
            ("humidity", "Humidity sensor"),
            ("presence", "Presence sensor"),
            ("illuminance", "Illuminance sensor"),
            ("thermostatMode", "Thermostat"),
            ("lock", "Lock"),
            ("water", "Water sensor"),
            ("smoke", "Smoke detector"),
            ("power", "Power meter"),
            ("energy", "Energy meter"),
            ("switch", "Switch"),
        )
        for key, label in ordered:
            if key in keys:
                return label
        return None


__all__ = ["FastFallbackRouter"]

from __future__ import annotations

from typing import Any

from device_intelligence_index import DeviceIntelligenceIndex
from fast_fallback_device_types_live import FastFallbackRouter as CapabilityDeviceRouter
from mcp_client import MCPToolResult


class FastFallbackRouter(CapabilityDeviceRouter):
    """Fast fallback router backed by one shared device intelligence index."""

    def __init__(
        self,
        *args: Any,
        device_index: DeviceIntelligenceIndex | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.device_index = device_index

    async def _live_devices(
        self,
        capability_filter: str | None = None,
    ) -> MCPToolResult:
        if self.device_index is None:
            return await super()._live_devices(capability_filter)
        if capability_filter:
            return await self.device_index.capability_result(
                capability_filter,
                detailed=False,
            )
        return await self.device_index.summary_result()

    async def _summary_devices(self) -> MCPToolResult:
        if self.device_index is None:
            return await super()._summary_devices()
        return await self.device_index.summary_result()

    async def _capability_devices(
        self,
        capability: str,
        *,
        detailed: bool,
    ) -> MCPToolResult:
        if self.device_index is None:
            return await super()._capability_devices(capability, detailed=detailed)
        return await self.device_index.capability_result(
            capability,
            detailed=detailed,
        )


__all__ = ["FastFallbackRouter"]

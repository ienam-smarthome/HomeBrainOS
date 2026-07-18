from __future__ import annotations

from typing import Any

from device_intelligence_index import DeviceIntelligenceIndex
from fast_fallback_device_types_live import FastFallbackRouter as CapabilityDeviceRouter
from mcp_client import MCPToolResult


class FastFallbackRouter(CapabilityDeviceRouter):
    """Fast fallback router backed by one shared device intelligence index.

    The final router owns the control-verification timing options because the
    long fallback mixin chain does not expose one consistent ``__init__``
    signature. Keeping the release-specific options here prevents startup
    failures while preserving the verified-control methods inherited below.
    """

    def __init__(
        self,
        *args: Any,
        device_index: DeviceIntelligenceIndex | None = None,
        control_verification_timeout_seconds: float = 7.0,
        control_verification_initial_delay_seconds: float = 0.2,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.device_index = device_index
        self.control_verification_timeout_seconds = max(
            2.0,
            min(20.0, float(control_verification_timeout_seconds)),
        )
        self.control_verification_initial_delay_seconds = max(
            0.05,
            min(2.0, float(control_verification_initial_delay_seconds)),
        )

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

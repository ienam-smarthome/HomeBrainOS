from __future__ import annotations

from typing import Any

from device_intelligence_index import DeviceIntelligenceIndex, _label
from fast_fallback_device_types_live import FastFallbackRouter as CapabilityDeviceRouter
from mcp_client import MCPToolResult


class FastFallbackRouter(CapabilityDeviceRouter):
    """Fast fallback router backed by one shared device intelligence index.

    The final router owns release-specific control settings because the long
    fallback mixin chain does not expose one consistent ``__init__`` signature.
    It also resolves exact spoken aliases through the shared index before fuzzy
    matching and forces fresh state reads throughout an active control request.
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
        self._force_fresh_control_reads = False

    async def _live_devices(
        self,
        capability_filter: str | None = None,
    ) -> MCPToolResult:
        if self.device_index is None:
            return await super()._live_devices(capability_filter)
        force = bool(self._force_fresh_control_reads)
        if capability_filter:
            return await self.device_index.capability_result(
                capability_filter,
                detailed=False,
                force=force,
            )
        return await self.device_index.summary_result(force=force)

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

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        """Resolve exact index aliases first, then run fully fresh control reads.

        This prevents an exact label such as ``Dehumidifier 2`` being downgraded
        to a fuzzy one-candidate confirmation when the capability response uses a
        slightly different label form. Duplicate aliases remain ambiguous because
        ``exact_device`` only returns a device when one ID owns that alias.
        """
        resolved_name = requested_name
        if self.device_index is not None:
            try:
                exact, _ = await self.device_index.exact_device(requested_name)
                exact_label = _label(exact or {})
                if exact_label:
                    resolved_name = exact_label
            except Exception:
                # The live verified control path remains authoritative if the
                # optional identity index cannot resolve the alias.
                pass

        self._force_fresh_control_reads = True
        try:
            answer = await super()._control_device(resolved_name, action)
        finally:
            self._force_fresh_control_reads = False

        if resolved_name != requested_name:
            answer["requested_name"] = requested_name
            answer["resolved_device_name"] = resolved_name
            answer["device_index_exact_match"] = True
        return answer


__all__ = ["FastFallbackRouter"]

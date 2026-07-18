from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from device_intelligence_index import (
    DeviceIntelligenceIndex,
    _DETAILED_FIELDS,
    _SUMMARY_FIELDS,
    _label,
)
from fast_fallback_device_types_live import FastFallbackRouter as CapabilityDeviceRouter
from mcp_client import MCPError, MCPToolResult


_FRESH_CONTROL_READS: ContextVar[bool] = ContextVar(
    "hubitat_mcp_ai_fresh_control_reads",
    default=False,
)


class FastFallbackRouter(CapabilityDeviceRouter):
    """Fast fallback router backed by one shared device intelligence index.

    The final router owns release-specific control settings because the long
    fallback mixin chain does not expose one consistent ``__init__`` signature.
    It also resolves exact spoken aliases through the shared index before fuzzy
    matching and forces fresh state reads throughout each active control request.
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

    @staticmethod
    def _fresh_control_reads_enabled() -> bool:
        """Return the request-local fresh-read state for the current task."""
        return bool(_FRESH_CONTROL_READS.get())

    async def _direct_fresh_devices(
        self,
        capability_filter: str | None = None,
        *,
        detailed: bool = False,
    ) -> MCPToolResult | None:
        """Read Hubitat directly, beyond both index and broker caches.

        ``DeviceIntelligenceIndex(force=True)`` skips its own snapshot, but its
        client is normally the shared MCP broker. That broker may still return a
        cached response or coalesce with a read that began before the command.
        During control verification, use the broker's raw MCP client so every
        poll is a distinct upstream Hubitat read. Non-control reads keep using
        the normal shared caches.
        """
        if self.device_index is None:
            return None

        broker = getattr(self.device_index, "client", None)
        raw_client = getattr(broker, "client", None)
        raw_call = getattr(raw_client, "call_tool", None)
        if not callable(raw_call):
            return None

        arguments: dict[str, Any] = {
            "detailed": bool(detailed),
            "format": "detailed" if detailed else "summary",
            "fields": list(_DETAILED_FIELDS if detailed else _SUMMARY_FIELDS),
        }
        if capability_filter:
            arguments["capabilityFilter"] = capability_filter

        result = await raw_call("hub_list_devices", arguments)
        if result.is_error:
            raise MCPError(result.text or "Fresh Hubitat device lookup failed")
        return result

    async def _live_devices(
        self,
        capability_filter: str | None = None,
    ) -> MCPToolResult:
        if self.device_index is None:
            return await super()._live_devices(capability_filter)

        force = self._fresh_control_reads_enabled()
        if force:
            fresh = await self._direct_fresh_devices(capability_filter, detailed=False)
            if fresh is not None:
                return fresh

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

        force = self._fresh_control_reads_enabled()
        if force:
            fresh = await self._direct_fresh_devices(detailed=False)
            if fresh is not None:
                return fresh
        return await self.device_index.summary_result(force=force)

    async def _capability_devices(
        self,
        capability: str,
        *,
        detailed: bool,
    ) -> MCPToolResult:
        if self.device_index is None:
            return await super()._capability_devices(capability, detailed=detailed)

        force = self._fresh_control_reads_enabled()
        if force:
            fresh = await self._direct_fresh_devices(
                capability,
                detailed=detailed,
            )
            if fresh is not None:
                return fresh
        return await self.device_index.capability_result(
            capability,
            detailed=detailed,
            force=force,
        )

    async def _control_device(self, requested_name: str, action: str) -> dict[str, Any]:
        """Resolve exact index aliases first, then run fully fresh control reads.

        This prevents an exact label such as ``Dehumidifier 2`` being downgraded
        to a fuzzy one-candidate confirmation when the capability response uses a
        slightly different label form. Duplicate aliases remain ambiguous because
        ``exact_device`` only returns a device when one ID owns that alias.

        A ContextVar keeps the fresh-read override local to this asyncio task. Two
        simultaneous controls therefore cannot clear each other's verification
        state while either command is still polling Hubitat.
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

        token = _FRESH_CONTROL_READS.set(True)
        try:
            answer = await super()._control_device(resolved_name, action)
        finally:
            _FRESH_CONTROL_READS.reset(token)

        if resolved_name != requested_name:
            answer["requested_name"] = requested_name
            answer["resolved_device_name"] = resolved_name
            answer["device_index_exact_match"] = True
        return answer


__all__ = ["FastFallbackRouter"]

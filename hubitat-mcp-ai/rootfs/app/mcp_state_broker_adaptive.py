from __future__ import annotations

import json
from typing import Any

from mcp_client import MCPToolResult
from mcp_state_broker import MCPStateBroker


def _gateway_mode_mismatch(result: MCPToolResult) -> bool:
    """Detect the MCP server's explicit gateway/flat-catalog mismatch response."""
    parts = [str(result.text or "")]
    try:
        parts.append(json.dumps(result.data, ensure_ascii=False, default=str))
    except Exception:
        parts.append(str(result.data or ""))
    text = " ".join(parts).lower()
    return bool(
        result.is_error
        and "gateway" in text
        and "disabled" in text
        and (
            "usegateways is off" in text
            or "flat catalog" in text
            or "underlying tool directly" in text
        )
    )


class AdaptiveGatewayMCPStateBroker(MCPStateBroker):
    """Gateway-aware broker that recovers when the server mode changes live.

    Hubitat MCP can expose either category gateways or a flat tool catalogue. Existing
    HomeBrain sessions may still cache the old tools/list response after the setting is
    toggled. When the server explicitly rejects a stale gateway call, refresh tools/list,
    clear the hidden-tool map and retry the originally requested tool once directly.
    """

    async def _upstream_call(
        self,
        requested_name: str,
        arguments: dict[str, Any],
    ) -> tuple[MCPToolResult, str | None]:
        result, gateway = await super()._upstream_call(requested_name, arguments)
        if not gateway or not _gateway_mode_mismatch(result):
            return result, gateway

        try:
            await self.client.list_tools(refresh=True)
        except Exception:
            return result, gateway

        self._gateway_map.clear()
        retry, retry_gateway = await super()._upstream_call(requested_name, arguments)
        if not retry.is_error:
            raw = dict(retry.raw) if isinstance(retry.raw, dict) else {"raw": retry.raw}
            raw.update(
                {
                    "gatewayModeRecovered": True,
                    "rejectedGateway": gateway,
                    "retriedTool": requested_name,
                }
            )
            retry = MCPToolResult(
                name=retry.name,
                arguments=retry.arguments,
                raw=raw,
                text=retry.text,
                data=retry.data,
                is_error=False,
            )
        return retry, retry_gateway


__all__ = ["AdaptiveGatewayMCPStateBroker", "_gateway_mode_mismatch"]

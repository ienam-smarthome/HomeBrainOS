from __future__ import annotations

import re

from ai_evidence_planner import is_ai_evidence_query
from control_agent_intent import is_control_candidate
from device_health_fast_route import is_device_health_query
from mcp_agent_orchestrator import _is_explicit_device_lookup, _requested_device_attribute
from route_registry import RouteDescriptor, RouteRegistry


_ENERGY_QUERY = re.compile(
    r"\b(?:whole[- ]house\s+)?(?:power|energy|consumption|usage)\b",
    re.IGNORECASE,
)
_RESTART_OR_FIRMWARE = re.compile(
    r"\b(?:restart|reboot|firmware\s+update|update\s+(?:the\s+)?hub)\b",
    re.IGNORECASE,
)
_CONFIRMATION_REPLY = re.compile(
    r"^(?:yes|no|confirm|cancel|proceed|do it)[.!?]*$",
    re.IGNORECASE,
)


def _measurement_query(query: str) -> bool:
    return _requested_device_attribute(query) is not None or _is_explicit_device_lookup(query)


def build_route_registry() -> RouteRegistry:
    """Return the canonical route-priority catalogue for diagnostics and migration."""

    return RouteRegistry(
        (
            RouteDescriptor(
                name="pending-confirmation",
                priority=1000,
                terminal=True,
                matcher=lambda query: bool(_CONFIRMATION_REPLY.match(query.strip())),
                reason="confirmation replies must be consumed before generic routing",
            ),
            RouteDescriptor(
                name="hub-administration",
                priority=950,
                terminal=True,
                matcher=lambda query: bool(_RESTART_OR_FIRMWARE.search(query)),
                reason="destructive hub administration requires a dedicated confirmation workflow",
            ),
            RouteDescriptor(
                name="device-control",
                priority=900,
                terminal=True,
                matcher=is_control_candidate,
                reason="device writes use the guarded control agent",
            ),
            RouteDescriptor(
                name="device-measurement",
                priority=850,
                terminal=True,
                matcher=_measurement_query,
                reason="named device identity and live measurements are authoritative deterministic reads",
            ),
            RouteDescriptor(
                name="device-health",
                priority=800,
                terminal=True,
                matcher=is_device_health_query,
                reason="health classifications are live authoritative reads",
            ),
            RouteDescriptor(
                name="energy-summary",
                priority=700,
                terminal=True,
                matcher=lambda query: bool(_ENERGY_QUERY.search(query)),
                reason="energy summaries use authoritative Octopus/device evidence",
            ),
            RouteDescriptor(
                name="ai-evidence",
                priority=500,
                terminal=False,
                matcher=is_ai_evidence_query,
                reason="reasoning questions use bounded authoritative evidence before synthesis",
            ),
            RouteDescriptor(
                name="general-assistant",
                priority=100,
                terminal=False,
                matcher=lambda query: bool(query.strip()),
                reason="fallback conversational assistant route",
            ),
        )
    )


__all__ = ["build_route_registry"]

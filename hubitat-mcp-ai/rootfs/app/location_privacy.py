"""Redaction of precise-location attributes before tool results reach a provider.

Presence/GPS integrations (Life360, OwnTracks, and similar Hubitat driver
families) return device attributes carrying exact coordinates, home
addresses, embedded map links, and minute-by-minute journey logs alongside
the ordinary presence/battery/wifi state. Nothing upstream of
``ToolExecutor.result_payload`` previously stripped this before it was
serialised into the ``tool`` role message appended to the provider
conversation in ``mcp_agent_orchestrator.py``, so a single presence-touching
request sent a household member's exact GPS position, street address, and
travel history to whichever provider is configured -- including Ollama's
cloud API when ``ollama_direct_cloud_enabled`` is set. That directly
contradicts this project's "privacy-preserving local control" positioning.

This module redacts only the attributes that carry precise location or
imagery/PII, not presence, battery, or wifi state, so "is anyone home" style
questions keep working through the normal tool-result path -- only exact
coordinates, street addresses, map tiles, and journey logs are withheld from
provider-bound content.
"""

from __future__ import annotations

from typing import Any

REDACTED_PLACEHOLDER = "[redacted: precise location data withheld from AI provider]"

# Case-insensitive attribute-name matches. Keyed on the bare attribute name
# as Hubitat reports it (see hub_list_devices output), not a substring, so
# unrelated attributes such as "presence" or "resolvedPlace" are untouched.
SENSITIVE_LOCATION_KEYS = {
    "latitude", "longitude", "lat", "lng", "lon",
    "locationurl", "location_url", "gps", "geofence",
    "address", "address1", "address2", "address1prev", "address2prev",
    "road", "roadlabel", "tile", "avatar",
    "currentjourney", "journeystoday", "journeysyesterday",
    "journeyclearlastat", "journeysuppressactive",
    "distance", "accuracy", "speed", "isdriving",
    "resolvedstationary", "resolvedplaceconfidence",
}


def redact_precise_location(value: Any) -> Any:
    """Recursively strip precise-location attribute values from a tool result.

    Walks nested dict/list structures (matching the shape of Hubitat MCP
    tool results, e.g. ``{"devices": [{"attributes": [...]}]}`` as well as
    the flat ``{"name": ..., "value": ...}`` attribute-list shape) and
    replaces the value of any key in ``SENSITIVE_LOCATION_KEYS`` with a
    placeholder. Everything else, including presence/battery/wifi state,
    passes through unchanged.
    """

    if isinstance(value, dict):
        # Flat Hubitat attribute entries look like {"name": "latitude", "value": ...}.
        name = value.get("name")
        if (
            isinstance(name, str)
            and name.casefold() in SENSITIVE_LOCATION_KEYS
            and "value" in value
            and len(value) <= 3
        ):
            return {**value, "value": REDACTED_PLACEHOLDER}
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).casefold() in SENSITIVE_LOCATION_KEYS:
                redacted[key] = REDACTED_PLACEHOLDER
            else:
                redacted[key] = redact_precise_location(item)
        return redacted
    if isinstance(value, list):
        return [redact_precise_location(item) for item in value]
    return value


__all__ = ["REDACTED_PLACEHOLDER", "SENSITIVE_LOCATION_KEYS", "redact_precise_location"]
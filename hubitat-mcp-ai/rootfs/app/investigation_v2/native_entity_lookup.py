"""Model-selected, read-only device-name resolver over verified live identity.

This is a host-local helper tool, not a Hubitat device command. It does not
choose an investigation route from question keywords and it never promotes
an ambiguous or stale entity to a verified target.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Mapping

from .native_source_adapters import safe_string

NAME = "homebrain_find_device"
_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "Look up ONE named Hubitat device in authoritative live identity, "
            "without fetching full device details. Use before hub_get_device "
            "when the user named a device but no verified deviceId is known. "
            "This is not Hub Mesh; Hub Mesh means hub-to-hub sharing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Device label or name to resolve, e.g. Bedroom 3 Mesh"}
            },
            "required": ["name"],
            "additionalProperties": False,
        }
    },
}


def lookup_tool() -> dict[str, Any]:
    return _TOOL_SCHEMA


def _normal(value: Any) -> str:
    return " ".join(re.findall(r"[^\W_]+", str(value or "").casefold(),
                               flags=re.UNICODE))


def choose_device(name: str, identities: Any) -> dict[str, Any]:
    """Exact and uniquely anchored matches only, never guess IDs from prompt."""
    if not isinstance(name, str) or not (3 <= len(name.strip()) <= 120):
        return {"status": "invalid_name", "matches": []}
    query = _normal(name)
    if len(query) < 3 or not isinstance(identities, list):
        return {"status": "identity_unavailable", "matches": []}
    candidates = []
    for raw in identities[:1000]:
        if not isinstance(raw, dict):
            continue
        ident = raw.get("id") if raw.get("id") is not None else raw.get("deviceId")
        if type(ident) not in (str, int) or not str(ident).isdecimal():
            continue
        label = str(raw.get("label") or "")
        canonical = str(raw.get("name") or "")
        matched = query in {_normal(label), _normal(canonical)}
        if matched:
            candidates.append({
                "id": str(ident), "label": safe_string(label, 100),
                "name": safe_string(canonical, 100),
            })
    # Alias collision across two devices must never pick a winner by ranking.
    deduped = list({item["id"]: item for item in candidates}.values())
    if len(deduped) == 1:
        return {"status": "unique", "matches": deduped}
    if deduped:
        return {"status": "ambiguous", "matches": deduped[:8]}
    # Only uniquely *anchored* prefix searches, never interior substring.
    if len(query) >= 8:
        prefixes = []
        for raw in identities[:1000]:
            if not isinstance(raw, dict):
                continue
            ident = raw.get("id") if raw.get("id") is not None else raw.get("deviceId")
            if type(ident) not in (str, int) or not str(ident).isdecimal():
                continue
            label = str(raw.get("label") or "")
            canonical = str(raw.get("name") or "")
            if any(v.startswith(query + " ") for v in
                   (_normal(label), _normal(canonical))):
                prefixes.append({
                    "id": str(ident), "label": safe_string(label, 100),
                    "name": safe_string(canonical, 100),
                })
        unique = list({item["id"]: item for item in prefixes}.values())
        if len(unique) == 1:
            return {"status": "unique", "matches": unique}
        if unique:
            return {"status": "ambiguous", "matches": unique[:8]}
    return {"status": "not_found", "matches": []}


async def resolve_named_device(mcp: Any, name: str,
                               timeout: float = 6.0) -> dict[str, Any]:
    lookup = getattr(mcp, "get_device_identities", None)
    if not callable(lookup):
        return {"status": "identity_unavailable", "matches": []}
    try:
        identities = await asyncio.wait_for(lookup(), timeout=max(0.1, min(6, timeout)))
    except asyncio.CancelledError:
        raise
    except (Exception, asyncio.TimeoutError):
        return {"status": "identity_unavailable", "matches": []}
    return choose_device(name, identities)

__all__ = ["NAME", "lookup_tool", "choose_device", "resolve_named_device"]

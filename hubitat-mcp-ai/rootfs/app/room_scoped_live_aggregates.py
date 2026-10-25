"""Resolve live aggregate room scope from authoritative Hubitat metadata.

This is entity grounding, not an intent/keyword router. The original question
may include a real room even if an AI-selected aggregate tool omits a filter.
Never silently replace an explicitly scoped question with a whole-home result.
"""
from __future__ import annotations

import re
from typing import Any

from device_state_summary import room_name


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def room_scope(
    devices: list[dict[str, Any]],
    *,
    question: str = "",
    tool_room: str = "",
) -> tuple[tuple[str, ...], bool, bool]:
    """Return (resolved room names, scope requested, scope verified).

    Detect names only from Hubitat's authoritative room assignments. Contiguous
    spelling aliases such as livingroom/living room compare identically.
    If the user names a room, that overrides an incompatible AI-supplied tool
    argument. No broadening is allowed for unresolved or conflicting scope.
    """
    rooms: dict[str, str] = {}
    for device in devices:
        if not isinstance(device, dict):
            continue
        name = room_name(device)
        if not name or _key(name) in ("", "unassigned"):
            continue
        rooms.setdefault(_key(name), name)

    question_key = _key(question)
    present = [
        room for normalized, room in rooms.items()
        if normalized and normalized in question_key
    ]
    # An explicitly named full-home scope outranks incidental room mentions
    # only when no exclusion or narrower clause is requested.
    full_home = bool(re.search(
        r"\b(?:whole\s+(?:home|house)|entire\s+(?:home|house)|"
        r"all\s+rooms|every\s+room|across\s+(?:all\s+)?rooms)\b",
        question, re.I
    ))
    if full_home and not re.search(r"\b(?:except|excluding|but\s+not)\b", question, re.I):
        return (), False, True
    # Exclusions need a set-difference plan; never silently answer their inverse.
    if present and re.search(r"\b(?:except|excluding|but\s+not)\b", question, re.I):
        return (), True, False
    if present:
        return tuple(dict.fromkeys(present)), True, True

    if tool_room.strip():
        match = rooms.get(_key(tool_room))
        return ((match,), True, True) if match else ((), True, False)
    return (), False, True


def scoped_active_devices(
    entries: list[dict[str, Any]],
    devices: list[dict[str, Any]],
    *,
    question: str = "",
    tool_room: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply a verified room constraint after the live on/off calculation."""
    selected, requested, verified = room_scope(
        devices, question=question, tool_room=tool_room
    )
    if not requested:
        return entries, {
            "scope": "whole-home", "scopeVerified": True,
            "requestedRoom": None, "matchedRooms": [],
        }
    if not verified:
        return [], {
            "scope": "unresolved-room", "scopeVerified": False,
            "requestedRoom": tool_room.strip() or question[:180],
            "matchedRooms": [], "complete": False,
        }
    allowed = {_key(item) for item in selected}
    return [
        entry for entry in entries
        if _key(entry.get("room")) in allowed
    ], {
        "scope": "room", "scopeVerified": True,
        "requestedRoom": tool_room.strip() or None,
        "matchedRooms": list(selected),
    }

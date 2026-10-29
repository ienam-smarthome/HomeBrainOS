"""Source-attested, read-only room-name catalogue for Native V2.

A room listing establishes available *names*, not device membership. The
full member set can only be attested by an independently matching room
detail response; current device state additionally requires a same-ID read.
This module is generic and contains no user-specific room/name route.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .native_source_adapters import safe_string, unwrapped


def _norm(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def source_room_catalog(source: Any) -> dict[str, Any] | None:
    """Project only bounded, real Hubitat room names from a list READ.

    Never accept IDs, device membership or source narrative from this list
    as device-read authorisation. Duplicate/invalid rows cannot prove a
    complete set. Preserve the count if the source explicitly supplied it.
    """
    data = unwrapped(source)
    rows = data.get("rooms") if isinstance(data, Mapping) else None
    if not isinstance(rows, list):
        return None
    names: list[str] = []
    seen: set[str] = set()
    rejected = 0
    for row in rows[:60]:
        raw = row.get("name") if isinstance(row, Mapping) else row
        if not isinstance(raw, str):
            rejected += 1
            continue
        name = safe_string(raw, 90)
        normalized = _norm(name)
        if (not name or not normalized or normalized in seen
                or len(raw) > 120):
            rejected += 1
            continue
        names.append(name)
        seen.add(normalized)
    if len(rows) > 60:
        rejected += len(rows) - 60
    reported = data.get("count", data.get("roomCount"))
    if type(reported) is not int or reported < 0:
        reported = None
    return {
        "rooms": names,
        "returned_room_count": len(rows),
        "reported_room_count": reported,
        "name_catalog_complete": (
            reported is not None and reported == len(names)
            and rejected == 0),
        "room_membership_verified": False,
        "room_states_verified": False,
        "rejected_room_rows": rejected,
        "source_complete": False,
    }


def question_room_matches(question: str, catalog: Mapping[str, Any]) -> list[str]:
    """Match the user's text to source-provided names, never a vocabulary route.

    Names are supplied ONLY by the independently read Hubitat room list.
    A matched name is a candidate for the model to investigate, never a
    permission to infer membership or current state.
    """
    if not isinstance(question, str):
        return []
    rooms = catalog.get("rooms")
    if not isinstance(rooms, list):
        return []
    matches: list[str] = []
    for room in rooms[:60]:
        if not isinstance(room, str) or not room:
            continue
        if re.search(r"(?<!\w)" + re.escape(room) + r"(?!\w)",
                     question, flags=re.IGNORECASE):
            matches.append(room)
    return sorted(matches, key=len, reverse=True)[:5]


__all__ = ["source_room_catalog", "question_room_matches"]

from __future__ import annotations

import re
from typing import Any


_ACTIVE_ROOMS_QUERY = re.compile(
    r"^(?:please\s+)?(?:"
    r"which|what|show|list|tell\s+me\s+which"
    r")\s+rooms?\s+(?:are\s+)?active"
    r"(?:\s+based\s+on\s+(?:motion|lights|motion\s+or\s+lights|lights\s+or\s+motion))?"
    r"[?.!]*$",
    re.IGNORECASE,
)


def is_active_rooms_query(query: str) -> bool:
    text = re.sub(r"\s+", " ", str(query or "").strip())
    return bool(_ACTIVE_ROOMS_QUERY.match(text))


def _join_names(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def build_active_rooms_terminal_route(application: Any, dashboard_snapshot: Any):
    """Return active rooms from the authoritative cached dashboard snapshot."""

    async def route(request: Any) -> dict[str, Any] | None:
        query = str(getattr(request, "query", "") or "").strip()
        if not is_active_rooms_query(query):
            return None

        snapshot = await dashboard_snapshot.get(force=False)
        if not snapshot.get("success", True):
            return None

        names = [
            str(name).strip()
            for name in list(snapshot.get("active_room_names") or [])
            if str(name).strip()
        ]
        details = [
            dict(item)
            for item in list(snapshot.get("active_room_details") or [])
            if isinstance(item, dict)
        ]
        count = snapshot.get("active_rooms")
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = len(names)

        if names:
            message = f"The active rooms are {_join_names(names)}."
        elif count:
            message = f"{count} rooms are currently active."
        else:
            message = "No rooms are currently active based on motion or lights."

        return {
            "success": True,
            "route": "mcp-dashboard-active-rooms",
            "intent": "active-rooms",
            "message": message,
            "active_rooms": count,
            "active_room_names": names,
            "active_room_details": details,
            "model": None,
            "answered_by": "Deterministic HomeBrain dashboard snapshot",
            "selected_tools": [],
            "display": {
                "summary": message,
                "metrics": [
                    {"label": "Active rooms", "value": count},
                ],
                "items": [
                    {
                        "title": name,
                        "value": "Active",
                        "subtitle": "Motion or light activity",
                    }
                    for name in names
                ],
            },
            "version": getattr(application, "VERSION", None),
        }

    return route


__all__ = [
    "build_active_rooms_terminal_route",
    "is_active_rooms_query",
]

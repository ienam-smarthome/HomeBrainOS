"""Prioritise configured occupancy sources before generic same-room sensors.

Configured relationships are *candidate discovery*, never historical proof.
Every selected candidate still needs a concrete device ID and an exposed
motion/presence attribute before Hubitat history may be requested.
"""
from __future__ import annotations

from typing import Any

from causal_investigation_engine import plan_cross_integration_candidates
from known_automation_topology import (
    prioritize_known_automation_sensor_candidates,
)


def prioritize_focal_sensor_candidates(
    room_candidates: list[dict[str, Any]],
    device_inventory: list[dict[str, Any]],
    known_automations: list[dict[str, Any]] | None,
    *,
    subject: str,
    subject_room: str,
    transition: str,
    limit: int = 2,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Add validated configured triggers from the wider device inventory.

    The first two alphabetical/room candidates are not necessarily the
    sensors configured to trigger the requested light. A verified topology
    relationship outranks generic room proximity. Unknown cross-room
    sensors are not promoted merely for an appealing name.
    """
    limit = max(1, min(int(limit), 4))
    room_rows = [dict(row) for row in room_candidates if isinstance(row, dict)]
    added: list[dict[str, Any]] = []
    if known_automations and device_inventory:
        extra = plan_cross_integration_candidates(
            device_inventory,
            subject=subject,
            subject_room=subject_room,
            transition=transition,
            tried_ids=set(),
            known_automations=known_automations,
            max_candidates=12,
        )
        for spec in extra:
            if not isinstance(spec, dict):
                continue
            candidate = spec.get("candidate") or {}
            if not isinstance(candidate, dict):
                continue
            # This is a verified rule-to-source relation, not a weak label
            # similarity or uncorroborated cross-room guess.
            if candidate.get("matchBasis") == "configured-trigger":
                added.append(dict(spec))
    combined = added + room_rows
    distinct: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spec in combined:
        candidate = spec.get("candidate") or {}
        if not isinstance(candidate, dict):
            continue
        identifier = str(candidate.get("id") or "")
        attribute = str(spec.get("attribute") or "")
        if not identifier.isdecimal() or attribute not in {"motion", "presence"}:
            continue
        if identifier in seen:
            continue
        seen.add(identifier)
        distinct.append(spec)
    selected, topology_used = prioritize_known_automation_sensor_candidates(
        distinct, known_automations, subject=subject,
        transition=transition, limit=limit,
    )
    selected_ids = {
        str((row.get("candidate") or {}).get("id") or "") for row in selected
    }
    missing = [
        {"id": str((spec.get("candidate") or {}).get("id") or ""),
         "label": str(spec.get("name") or "")}
        for spec in added
        if str((spec.get("candidate") or {}).get("id") or "") not in selected_ids
    ]
    return selected, {
        "source": "configured-automation-plus-verified-device-inventory",
        "topologyUsed": bool(topology_used),
        "configuredCandidatesAvailable": len(added),
        "configuredCandidatesSelected": sum(
            1 for row in selected if str((row.get("candidate") or {}).get("id") or "")
            in {str((spec.get("candidate") or {}).get("id") or "") for spec in added}
        ),
        "configuredCandidatesNotSelected": missing,
        "selectedSensorIds": sorted(x for x in selected_ids if x),
        "historicalEventsVerified": False,
    }


__all__ = ["prioritize_focal_sensor_candidates"]

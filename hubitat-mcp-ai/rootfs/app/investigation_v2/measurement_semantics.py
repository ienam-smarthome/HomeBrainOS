"""Typed, provenance-aware measurement scope for Hubitat V2 inventory evidence.

Do not determine meter scope with vendor/brand keyword exclusions. An actual
source annotation (or optional operator-approved mapping) outranks model
interpretation. A model may *suggest* scope for an identity already present in
the live inventory, but inference is disclosed and not promoted to a fact.

Power (W) is instantaneous. Energy (kWh) is accumulated. A site total and its
child meters overlap and must not be summed/ranked as independent loads.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from device_state_summary import capability_names, device_attributes, room_name

ROLES = frozenset({"site_total", "circuit_subtotal", "individual_load", "unknown"})
SOURCE_KEYS = ("measurementScope", "measurementRole", "meterScope", "meterRole")
CANDIDATE_KEYS = ("power", "energy")
MAX_CANDIDATES = 80


@dataclass(frozen=True)
class ScopeEvidence:
    role: str
    provenance: str
    verified: bool

    def as_dict(self) -> dict[str, Any]:
        return {"role": self.role, "provenance": self.provenance,
                "verified": self.verified}


def _accepted_role(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    role = value.strip().casefold().replace("-", "_")
    return role if role in ROLES else None


def candidates(devices: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Small typed catalogue for one semantic planning pass; no raw telemetry."""
    result = []
    for item in devices:
        if not isinstance(item, dict):
            continue
        ident = item.get("id", item.get("deviceId"))
        if type(ident) not in (str, int) or not str(ident).isdecimal():
            continue
        attrs = device_attributes(dict(item))
        if not any(
            any(isinstance(k, str) and k.casefold() == wanted
                and v is not None for k, v in attrs.items())
            or item.get(wanted) is not None
            for wanted in CANDIDATE_KEYS
        ):
            continue
        label = str(item.get("label") or item.get("name") or "").strip()[:110]
        if not label:
            continue
        room = str(room_name(dict(item)) or "")[:90]
        result.append({
            "id": str(ident), "label": label, "room": room,
            "capabilities": sorted(capability_names(dict(item)))[:15],
        })
        if len(result) >= MAX_CANDIDATES:
            break
    return result


def validated_model_hints(
    hints: Any, inventory_candidates: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, str], ...]:
    """Admit a model interpretation only for an exact inventory ID+label pair."""
    if hints is None:
        return ()
    if not isinstance(hints, list) or len(hints) > MAX_CANDIDATES:
        raise ValueError("invalid model measurement hints")
    known = {x["id"]: x["label"] for x in inventory_candidates}
    retained: dict[str, dict[str, str]] = {}
    for item in hints:
        if not isinstance(item, dict) or set(item) != {"id", "label", "role"}:
            raise ValueError("unexpected model measurement hint fields")
        ident, label, role = item["id"], item["label"], _accepted_role(item["role"])
        if (not isinstance(ident, str) or not isinstance(label, str)
                or ident not in known or known[ident] != label or role is None):
            raise ValueError("model measurement hint has unverified identity/role")
        if ident in retained:
            raise ValueError("repeated model measurement role")
        retained[ident] = {"id": ident, "label": label, "role": role}
    return tuple(retained.values())


def measurement_scope(
    device: Mapping[str, Any],
    *,
    hints: Sequence[Mapping[str, str]] = (),
    operator_roles: Mapping[str, str] | None = None,
) -> ScopeEvidence:
    ident = device.get("id", device.get("deviceId"))
    ident = str(ident) if type(ident) in (str, int) else ""
    if operator_roles and ident in operator_roles:
        role = _accepted_role(operator_roles[ident])
        if role is not None:
            return ScopeEvidence(role, "operator_confirmed", True)
    attributes = device_attributes(dict(device))
    for key in SOURCE_KEYS:
        for mapping in (device, attributes):
            supplied = next((v for k,v in mapping.items()
                             if isinstance(k, str) and k.casefold() == key.casefold()), None)
            role = _accepted_role(supplied)
            if role is not None:
                return ScopeEvidence(role, "reported_device_metadata", False)
    label = device.get("label") or device.get("name")
    for hint in hints:
        if hint.get("id") == ident and hint.get("label") == label:
            role = _accepted_role(hint.get("role"))
            if role is not None:
                return ScopeEvidence(role, "model_inference_unverified", False)
    return ScopeEvidence("unknown", "not_classified", False)


def measurement_profile_summary(
    devices: Sequence[Mapping[str, Any]], *, attribute: str,
    hints: Sequence[Mapping[str, str]] = (),
    operator_roles: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Never add overlapping scopes. This is metadata, not energy arithmetic."""
    roles = {key: [] for key in ROLES}
    for device in devices:
        if not isinstance(device, dict):
            continue
        attrs = device_attributes(dict(device))
        if not any(k.casefold() == attribute and v is not None
                   for k,v in attrs.items() if isinstance(k,str)):
            continue
        scope = measurement_scope(device, hints=hints, operator_roles=operator_roles)
        roles[scope.role].append(str(device.get("id", device.get("deviceId", ""))))
    return {role: {"count": len(roles[role]), "device_ids": roles[role]}
            for role in sorted(roles)}



def load_operator_meter_roles(
    raw: Any, devices: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    """Parse opt-in operator-confirmed roles only for current numeric IDs.

    This is a deliberate configuration decision, never a brand-name rule.
    Unknown IDs, invalid roles, non-object JSON, and excessive keys fail
    closed rather than silently changing accounting.
    """
    import json
    if isinstance(raw, str):
        if len(raw) > 12000:
            raise ValueError("measurement role configuration too large")
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid measurement role JSON") from exc
    if not isinstance(raw, dict) or len(raw) > 250:
        raise ValueError("measurement role configuration must be a bounded map")
    known_ids = {
        str(item.get("id", item.get("deviceId")))
        for item in devices if isinstance(item, dict)
        and type(item.get("id", item.get("deviceId"))) in (str, int)
        and str(item.get("id", item.get("deviceId"))).isdecimal()
    }
    approved: dict[str, str] = {}
    for ident, value in raw.items():
        if not isinstance(ident, str) or not ident.isdecimal() or ident not in known_ids:
            raise ValueError("measurement role references a device absent from live inventory")
        role = _accepted_role(value)
        if role is None:
            raise ValueError("invalid measurement role assignment")
        approved[ident] = role
    return approved

__all__ = [
    "ROLES", "ScopeEvidence", "candidates", "validated_model_hints",
    "measurement_scope", "measurement_profile_summary",
    "load_operator_meter_roles",
]

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable


HealthReader = Callable[[], Awaitable[dict[str, Any]]]


def _technical_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _device_id(item: dict[str, Any]) -> str | None:
    value = item.get("id") or item.get("deviceId") or item.get("device_id")
    text = str(value or "").strip()
    return text or None


def _device_name(item: dict[str, Any]) -> str:
    return str(item.get("device") or item.get("title") or item.get("label") or item.get("name") or "").strip()


def _normalise_item(item: dict[str, Any], kind: str) -> dict[str, Any]:
    row = dict(item)
    row["kind"] = kind
    row["id"] = _device_id(row)
    title = _device_name(row)
    if title:
        row.setdefault("title", title)
        row.setdefault("device", title)
    if kind == "offline":
        row.setdefault("value", "Offline")
        row.setdefault("tone", "danger")
    elif kind == "stale":
        row.setdefault("value", "Telemetry stale")
        row.setdefault("tone", "warning")
    else:
        row.setdefault("value", "Quiet, not offline")
        row["tone"] = None
    return row


def _structured_items(answer: dict[str, Any]) -> list[dict[str, Any]]:
    existing = answer.get("health_items")
    if isinstance(existing, list):
        return [dict(item) for item in existing if isinstance(item, dict)]

    technical = _technical_object(answer.get("technical"))
    groups = (
        ("offline", technical.get("offline_devices") or answer.get("offline_devices") or []),
        ("stale", technical.get("stale_telemetry") or answer.get("stale_devices") or []),
        ("quiet", technical.get("quiet_timestamp_devices") or answer.get("quiet_devices") or []),
    )
    items: list[dict[str, Any]] = []
    for kind, values in groups:
        if isinstance(values, dict):
            values = values.get("items") or values.get("devices") or []
        for item in values if isinstance(values, list) else []:
            if isinstance(item, dict):
                items.append(_normalise_item(item, kind))
    return items


def apply_structured_health_contract(answer: dict[str, Any]) -> dict[str, Any]:
    """Expose the device-health enum end-to-end; never reconstruct it from prose."""

    result = dict(answer)
    items = _structured_items(result)
    if not items:
        return result

    by_id = {_device_id(item): item for item in items if _device_id(item)}
    by_name = {_device_name(item).casefold(): item for item in items if _device_name(item)}

    display = result.get("display")
    if isinstance(display, dict):
        updated_display = dict(display)
        display_items: list[dict[str, Any]] = []
        for raw in display.get("items") or []:
            if not isinstance(raw, dict):
                continue
            match = by_id.get(_device_id(raw)) or by_name.get(_device_name(raw).casefold())
            row = dict(raw)
            if match:
                row["kind"] = match.get("kind")
                row["id"] = _device_id(match)
                row["reason"] = match.get("reason")
                if match.get("kind") == "quiet":
                    row["tone"] = None
            display_items.append(row)
        updated_display["items"] = display_items
        result["display"] = updated_display

    result["health_items"] = items
    result["offline_devices"] = [item for item in items if item.get("kind") == "offline"]
    result["stale_devices"] = [item for item in items if item.get("kind") == "stale"]
    result["quiet_devices"] = [item for item in items if item.get("kind") == "quiet"]
    return result


def project_health_attention_items(answer: Any) -> list[dict[str, Any]]:
    if not isinstance(answer, dict):
        return []
    structured = apply_structured_health_contract(answer)
    projected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in structured.get("health_items") or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        if kind not in {"offline", "stale"}:
            continue
        identity = _device_id(item) or _device_name(item).casefold()
        if not identity or identity in seen:
            continue
        seen.add(identity)
        projected.append(
            {
                "id": _device_id(item),
                "title": _device_name(item),
                "device": _device_name(item),
                "room": item.get("room"),
                "value": "Offline" if kind == "offline" else "Stale",
                "subtitle": item.get("subtitle") or item.get("detail") or item.get("reason"),
                "tone": "danger" if kind == "offline" else "warning",
                "kind": kind,
            }
        )
    return projected


def install_structured_health_contract(application: Any) -> HealthReader | None:
    fallback = getattr(application, "fallback", None)
    original = getattr(fallback, "_device_health", None)
    if not callable(original):
        return None
    if getattr(original, "__homebrain_structured_health_contract__", False):
        return original

    async def structured_device_health() -> dict[str, Any]:
        answer = await original()
        return apply_structured_health_contract(dict(answer))

    structured_device_health.__homebrain_structured_health_contract__ = True
    fallback._device_health = structured_device_health

    # The semantic router looks these names up in its module globals at runtime.
    # Replace the legacy prose-sniffing projector with the structured enum projector.
    import semantic_home_query_router as semantic_router

    semantic_router._health_attention_items = project_health_attention_items
    return structured_device_health


__all__ = [
    "apply_structured_health_contract",
    "install_structured_health_contract",
    "project_health_attention_items",
]

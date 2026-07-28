from __future__ import annotations

import json
from typing import Any, Awaitable, Callable


TerminalRoute = Callable[[Any], Awaitable[dict[str, Any] | None]]


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


def _device_name(item: dict[str, Any]) -> str:
    return str(item.get("device") or item.get("title") or item.get("label") or "").strip()


def _device_id(item: dict[str, Any]) -> str | None:
    value = item.get("id") or item.get("deviceId") or item.get("device_id")
    text = str(value or "").strip()
    return text or None


def _identity(item: dict[str, Any]) -> str:
    device_id = _device_id(item)
    return f"id:{device_id}" if device_id else f"name:{_device_name(item).casefold()}"


def _health_items(answer: Any) -> list[dict[str, Any]]:
    if not isinstance(answer, dict):
        return []
    values = answer.get("health_items")
    if isinstance(values, list):
        return [dict(item) for item in values if isinstance(item, dict)]

    technical = _technical_object(answer.get("technical"))
    items: list[dict[str, Any]] = []
    for kind, key in (
        ("offline", "offline_devices"),
        ("stale", "stale_telemetry"),
        ("quiet", "quiet_timestamp_devices"),
    ):
        for raw in technical.get(key) or []:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            item["kind"] = kind
            items.append(item)
    return items


def _names(items: list[dict[str, Any]]) -> str:
    names = [_device_name(item) for item in items]
    names = [name for name in names if name]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _accurate_message(attention: dict[str, Any]) -> str:
    parts: list[str] = []
    contacts = attention.get("open_contacts") if isinstance(attention.get("open_contacts"), dict) else {}
    open_items = [item for item in contacts.get("open") or [] if isinstance(item, dict)]
    if open_items:
        parts.append(f"Open contacts: {_names(open_items)}.")

    offline = attention.get("offline") if isinstance(attention.get("offline"), dict) else {}
    offline_items = [item for item in offline.get("items") or [] if isinstance(item, dict)]
    if offline_items:
        parts.append(
            f"{len(offline_items)} device{' is' if len(offline_items) == 1 else 's are'} confirmed offline: "
            f"{_names(offline_items)}."
        )

    stale = attention.get("stale") if isinstance(attention.get("stale"), dict) else {}
    stale_items = [item for item in stale.get("items") or [] if isinstance(item, dict)]
    if stale_items:
        parts.append(f"Stale telemetry is confirmed for {_names(stale_items)}.")

    low = attention.get("low_batteries") if isinstance(attention.get("low_batteries"), dict) else {}
    low_items = [item for item in low.get("items") or [] if isinstance(item, dict)]
    if low_items:
        details = []
        for item in low_items:
            name = _device_name(item)
            value = item.get("value")
            details.append(f"{name} at {float(value):g}%" if isinstance(value, (int, float)) else name)
        parts.append("Low batteries: " + ", ".join(details) + ".")

    return " ".join(parts) if parts else "Nothing currently stands out as needing attention."


def _row_from_health(item: dict[str, Any]) -> dict[str, Any]:
    kind = str(item.get("kind") or "").strip().lower()
    return {
        "id": _device_id(item),
        "device": _device_name(item),
        "room": item.get("room"),
        "value": "Offline" if kind == "offline" else "Stale",
        "detail": item.get("subtitle") or item.get("detail") or item.get("reason"),
        "kind": kind,
    }


def reconcile_semantic_attention(answer: dict[str, Any]) -> dict[str, Any]:
    if str(answer.get("route") or "") != "ai-semantic-home-attention":
        return answer
    attention = answer.get("semantic_attention")
    if not isinstance(attention, dict):
        return answer

    technical = _technical_object(answer.get("technical"))
    health_answer = answer.get("_health_evidence")
    if not isinstance(health_answer, dict):
        health_answer = technical.get("health_evidence")
    structured = _health_items(health_answer)
    if not structured:
        result = dict(answer)
        result.pop("_health_evidence", None)
        result.pop("_health_evidence_error", None)
        return result

    authoritative: dict[str, dict[str, Any]] = {
        _identity(item): item
        for item in structured
        if _identity(item) not in {"name:"}
    }

    reconciled_offline: list[dict[str, Any]] = []
    reconciled_stale: list[dict[str, Any]] = []
    for item in authoritative.values():
        kind = str(item.get("kind") or "").strip().lower()
        if kind == "offline":
            reconciled_offline.append(_row_from_health(item))
        elif kind == "stale":
            reconciled_stale.append(_row_from_health(item))
        # Quiet is deliberately omitted: event age alone is not a fault.

    # Preserve unrelated structured rows only when they carry an explicit kind and
    # do not refer to a device already covered by authoritative health evidence.
    covered = set(authoritative)
    for category, target in (
        ("offline", reconciled_offline),
        ("stale", reconciled_stale),
    ):
        block = attention.get(category)
        rows = block.get("items") if isinstance(block, dict) else []
        for raw in rows or []:
            if not isinstance(raw, dict):
                continue
            identity = _identity(raw)
            if identity in covered:
                continue
            if str(raw.get("kind") or "").strip().lower() != category:
                continue
            if identity not in {_identity(existing) for existing in target}:
                target.append(dict(raw))

    reconciled_offline.sort(key=lambda item: _device_name(item).casefold())
    reconciled_stale.sort(key=lambda item: _device_name(item).casefold())

    updated = dict(attention)
    updated["offline"] = {"count": len(reconciled_offline), "items": reconciled_offline}
    updated["stale"] = {"count": len(reconciled_stale), "items": reconciled_stale}
    updated["quiet_health_rows_suppressed"] = sum(
        str(item.get("kind") or "").strip().lower() == "quiet"
        for item in structured
    )
    updated["issue_count"] = sum(
        int((updated.get(name) or {}).get("count") or 0)
        for name in ("low_batteries", "offline", "stale", "warnings", "updates")
        if isinstance(updated.get(name), dict)
    )

    result = dict(answer)
    result.pop("_health_evidence", None)
    result.pop("_health_evidence_error", None)
    result["semantic_attention"] = updated
    result["message"] = _accurate_message(updated)
    result["health_reconciled"] = True
    result["technical"] = json.dumps(
        {
            **technical,
            "attention": updated,
            "health_reconciliation": {
                "authoritative_kind_counts": {
                    "offline": len(reconciled_offline),
                    "stale": len(reconciled_stale),
                    "quiet": updated["quiet_health_rows_suppressed"],
                },
                "identity_strategy": "device id, falling back to normalized label",
            },
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    return result


def wrap_semantic_home_query_route(route: TerminalRoute) -> TerminalRoute:
    async def guarded(request: Any) -> dict[str, Any] | None:
        answer = await route(request)
        if answer is None:
            return None
        return reconcile_semantic_attention(dict(answer))

    return guarded


__all__ = [
    "reconcile_semantic_attention",
    "wrap_semantic_home_query_route",
]

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


def _health_classifications(answer: Any) -> dict[str, str]:
    if not isinstance(answer, dict):
        return {}

    classifications: dict[str, str] = {}
    display = answer.get("display")
    if not isinstance(display, dict):
        return classifications

    for item in display.get("items") or []:
        if not isinstance(item, dict):
            continue
        name = _device_name(item)
        if not name:
            continue
        text = " ".join(
            str(item.get(key) or "")
            for key in ("value", "subtitle", "tone")
        ).casefold()
        if any(term in text for term in ("offline", "unavailable", "unreachable", "not responding")):
            kind = "offline"
        elif "stale" in text and "quiet" not in text:
            kind = "stale"
        elif any(
            term in text
            for term in (
                "quiet timestamp",
                "quiet timestamps",
                "old lastactivity",
                "event age",
                "not proof",
                "no negative live health",
                "normally static",
                "unchanged state",
            )
        ):
            kind = "quiet"
        else:
            # Device-health display rows that are neither explicitly negative nor
            # stale are informational. They must not be promoted to offline.
            kind = "quiet"
        classifications[name.casefold()] = kind
    return classifications


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


def reconcile_semantic_attention(answer: dict[str, Any]) -> dict[str, Any]:
    if str(answer.get("route") or "") != "ai-semantic-home-attention":
        return answer
    attention = answer.get("semantic_attention")
    if not isinstance(attention, dict):
        return answer

    technical = _technical_object(answer.get("technical"))
    classifications = _health_classifications(technical.get("health_evidence"))
    if not classifications:
        return answer

    offline_rows = [item for item in (attention.get("offline") or {}).get("items", []) if isinstance(item, dict)]
    stale_rows = [item for item in (attention.get("stale") or {}).get("items", []) if isinstance(item, dict)]
    other_rows = [
        item
        for item in offline_rows + stale_rows
        if _device_name(item).casefold() not in classifications
    ]

    reconciled_offline: list[dict[str, Any]] = []
    reconciled_stale: list[dict[str, Any]] = []
    for item in offline_rows + stale_rows:
        name = _device_name(item)
        kind = classifications.get(name.casefold())
        if kind == "offline":
            row = dict(item)
            row["value"] = "Offline"
            if not any(_device_name(existing).casefold() == name.casefold() for existing in reconciled_offline):
                reconciled_offline.append(row)
        elif kind == "stale":
            row = dict(item)
            row["value"] = "Stale"
            if not any(_device_name(existing).casefold() == name.casefold() for existing in reconciled_stale):
                reconciled_stale.append(row)
        elif kind is None:
            text = " ".join(str(item.get(key) or "") for key in ("value", "detail")).casefold()
            target = reconciled_offline if "offline" in text else reconciled_stale
            if not any(_device_name(existing).casefold() == name.casefold() for existing in target):
                target.append(dict(item))

    # Preserve unrelated rows that were not part of device-health evidence.
    for item in other_rows:
        name = _device_name(item)
        text = " ".join(str(item.get(key) or "") for key in ("value", "detail")).casefold()
        target = reconciled_offline if "offline" in text else reconciled_stale
        if not any(_device_name(existing).casefold() == name.casefold() for existing in target):
            target.append(dict(item))

    updated = dict(attention)
    updated["offline"] = {"count": len(reconciled_offline), "items": reconciled_offline}
    updated["stale"] = {"count": len(reconciled_stale), "items": reconciled_stale}
    updated["quiet_health_rows_suppressed"] = sum(
        kind == "quiet" for kind in classifications.values()
    )
    updated["issue_count"] = sum(
        int((updated.get(name) or {}).get("count") or 0)
        for name in ("low_batteries", "offline", "stale", "warnings", "updates")
        if isinstance(updated.get(name), dict)
    )

    result = dict(answer)
    result["semantic_attention"] = updated
    result["message"] = _accurate_message(updated)
    result["health_reconciled"] = True
    result["technical"] = json.dumps(
        {
            **technical,
            "attention": updated,
            "health_reconciliation": {
                "classifications": classifications,
                "quiet_rows_suppressed": updated["quiet_health_rows_suppressed"],
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

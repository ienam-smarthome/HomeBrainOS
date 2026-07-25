from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from device_intelligence_index import _device_rows


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_HOME_SUMMARY_TERMS = (
    "what's happening",
    "what is happening",
    "home insight",
    "home status",
    "at home",
)


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _state_value(value: Any) -> Any:
    if isinstance(value, dict):
        for name in ("currentValue", "currentState", "value", "state", "text"):
            if value.get(name) not in (None, ""):
                return _state_value(value[name])
        return None
    return value


def _motion_value(device: dict[str, Any]) -> str | None:
    for container_name in ("currentStates", "current_states", "attributes", "states"):
        container = device.get(container_name)
        if isinstance(container, dict):
            for name, value in container.items():
                if _key(name) in {"motion", "motionsensor"}:
                    current = _state_value(value)
                    return str(current).strip().lower() if current not in (None, "") else None
        elif isinstance(container, list):
            for item in container:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("attribute") or item.get("key")
                if _key(name) in {"motion", "motionsensor"}:
                    current = _state_value(item)
                    return str(current).strip().lower() if current not in (None, "") else None
    return None


def _label(device: dict[str, Any]) -> str:
    return str(
        device.get("label")
        or device.get("displayName")
        or device.get("name")
        or "Motion sensor"
    ).strip()


def _active_motion_labels(devices: list[dict[str, Any]]) -> tuple[list[str], int]:
    active: list[str] = []
    states_read = 0
    for device in devices:
        if not isinstance(device, dict) or device.get("disabled") is True:
            continue
        value = _motion_value(device)
        if value is None:
            continue
        states_read += 1
        if value in {"active", "motion", "detected", "on", "true", "1"}:
            active.append(_label(device))
    return sorted(set(active), key=str.casefold), states_read


def _motion_sentence(active: list[str], states_read: int) -> str:
    if not active:
        return f"Live motion check: no motion sensors are active ({states_read} states read)."
    if len(active) == 1:
        names = active[0]
    elif len(active) == 2:
        names = f"{active[0]} and {active[1]}"
    else:
        names = ", ".join(active[:-1]) + f", and {active[-1]}"
    return (
        f"Live motion check: {len(active)} motion sensors are active: "
        f"{names} ({states_read} states read)."
    )


def _replace_motion_claims(message: str, authoritative: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", str(message or "").strip())
    kept = [sentence for sentence in sentences if "motion" not in sentence.lower()]
    base = " ".join(sentence.strip() for sentence in kept if sentence.strip()).strip()
    return f"{base} {authoritative}".strip()


async def _read_live_motion(application: Any) -> tuple[list[str], int, dict[str, Any]]:
    diagnostic: dict[str, Any] = {"tool": "hub_list_devices", "success": False}
    try:
        result = await application.mcp.call_tool("hub_list_devices", {})
        diagnostic["success"] = not bool(getattr(result, "is_error", False))
        if diagnostic["success"]:
            rows = _device_rows(getattr(result, "data", None))
            active, states_read = _active_motion_labels(rows)
            diagnostic.update(
                {
                    "device_count": len(rows),
                    "motion_states_read": states_read,
                    "active_motion_count": len(active),
                    "active_motion_labels": active,
                }
            )
            return active, states_read, diagnostic
    except Exception as exc:
        diagnostic["error"] = str(exc) or type(exc).__name__
    return [], 0, diagnostic


def install_home_summary_consistency_guard(application: Any) -> AskHandler:
    """Correct legacy AI home-summary motion claims from live Hubitat states.

    Semantic home summary and attention routes already use typed authoritative
    evidence and must not be rewritten by this compatibility guard.
    """

    original_ask: AskHandler = application.ask

    async def guarded_ask(request: Any) -> dict[str, Any]:
        answer = dict(await original_ask(request))
        if str(answer.get("route") or "") in {
            "ai-semantic-home-evidence",
            "ai-semantic-home-attention",
        }:
            return answer

        query = str(getattr(request, "query", "") or "").lower()
        if not any(term in query for term in _HOME_SUMMARY_TERMS):
            return answer

        active, states_read, diagnostic = await _read_live_motion(application)
        if not diagnostic.get("success") or states_read == 0:
            answer["home_summary_motion_guard_read"] = diagnostic
            return answer

        original_message = str(answer.get("message") or "")
        corrected = _replace_motion_claims(
            original_message,
            _motion_sentence(active, states_read),
        )
        answer["message"] = corrected
        display = answer.get("display")
        if isinstance(display, dict):
            display = dict(display)
            if display.get("summary") == original_message:
                display["summary"] = corrected
            answer["display"] = display
        answer["home_summary_motion_corrected"] = corrected != original_message
        answer["home_summary_motion"] = {
            "active": active,
            "active_count": len(active),
            "states_read": states_read,
        }
        answer["home_summary_motion_guard_read"] = diagnostic
        tools = list(answer.get("tools_used") or [])
        tools.append({"name": "hub_list_devices", "success": True, "purpose": "home-summary-motion-verification"})
        answer["tools_used"] = tools
        return answer

    application.ask = guarded_ask
    return original_ask


__all__ = [
    "_active_motion_labels",
    "_replace_motion_claims",
    "install_home_summary_consistency_guard",
]

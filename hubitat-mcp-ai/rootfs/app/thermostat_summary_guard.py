from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from device_intelligence_index import _device_rows
from presenter import display_payload, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_HOME_SUMMARY_TERMS = (
    "what's happening",
    "what is happening",
    "home insight",
    "home status",
    "at home",
)
_SET_TO_PATTERN = re.compile(
    r"\b(?:the\s+)?thermostat\s+is\s+set\s+to\s+(-?\d+(?:\.\d+)?)\s*°?c\b",
    re.IGNORECASE,
)
_DIRECT_THERMOSTAT_QUERY = re.compile(
    r"\bthermostat\b.*\b(?:temperature|temp|setpoint|set point|setting|target)\b|"
    r"\b(?:temperature|temp|setpoint|set point|setting|target)\b.*\bthermostat\b",
    re.IGNORECASE,
)


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _number(value: Any) -> float | None:
    if isinstance(value, dict):
        for name in ("currentValue", "value", "state", "text", "currentState"):
            if value.get(name) not in (None, ""):
                return _number(value[name])
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or "").replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _attributes(device: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for container_name in ("currentStates", "attributes", "state", "states"):
        container = device.get(container_name)
        if isinstance(container, dict):
            for name, value in container.items():
                values[_key(name)] = value
        elif isinstance(container, list):
            for item in container:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("attribute") or item.get("key")
                if name:
                    values[_key(name)] = item
    for name in (
        "temperature",
        "heatingSetpoint",
        "thermostatSetpoint",
        "coolingSetpoint",
        "thermostatMode",
        "thermostatOperatingState",
    ):
        if device.get(name) not in (None, ""):
            values.setdefault(_key(name), device[name])
    return values


def _device_id(device: dict[str, Any]) -> str:
    for name in ("id", "deviceId", "device_id"):
        value = device.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def _device_label(device: dict[str, Any]) -> str:
    return str(
        device.get("label")
        or device.get("displayName")
        or device.get("name")
        or ""
    ).strip()


def _thermostat_inventory_candidates(
    devices: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[tuple[tuple[int, str], dict[str, Any]]] = []
    thermostat_attributes = {
        "heatingsetpoint",
        "thermostatsetpoint",
        "coolingsetpoint",
        "thermostatmode",
        "thermostatoperatingstate",
    }
    for device in devices:
        if not isinstance(device, dict) or device.get("disabled") is True:
            continue
        label = _device_label(device)
        descriptive = " ".join(
            str(device.get(name) or "")
            for name in ("label", "displayName", "name", "type", "deviceType", "category")
        ).lower()
        attribute_names = set(_attributes(device))
        if (
            "thermostat" not in descriptive
            and "trv" not in descriptive
            and not thermostat_attributes.intersection(attribute_names)
        ):
            continue
        lowered = label.lower()
        if lowered == "thermostat":
            rank = 0
        elif lowered.startswith("thermostat"):
            rank = 1
        elif "thermostat" in lowered:
            rank = 2
        elif "trv" in lowered:
            rank = 3
        else:
            rank = 4
        candidates.append(((rank, lowered), device))
    candidates.sort(key=lambda item: item[0])
    return [device for _, device in candidates]


def _thermostat_reading(devices: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for device in devices:
        if not isinstance(device, dict) or device.get("disabled") is True:
            continue
        attrs = _attributes(device)
        heating = _number(attrs.get("heatingsetpoint"))
        generic = _number(attrs.get("thermostatsetpoint"))
        temperature = _number(attrs.get("temperature"))
        if heating is None and generic is None:
            continue
        label = str(device.get("label") or device.get("displayName") or device.get("name") or "Thermostat").strip()
        candidates.append(
            {
                "id": device.get("id") or device.get("deviceId"),
                "label": label,
                "temperature": temperature,
                "heating_setpoint": heating if heating is not None else generic,
                "cooling_setpoint": _number(attrs.get("coolingsetpoint")),
                "mode": attrs.get("thermostatmode"),
                "operating_state": attrs.get("thermostatoperatingstate"),
            }
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (0 if item["label"].lower() == "thermostat" else 1, 0 if "thermostat" in item["label"].lower() else 1, item["label"].lower()))
    return candidates[0]


def _format_celsius(value: float) -> str:
    return f"{value:g}°C"


async def _live_thermostat_reading(application: Any) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    diagnostic: dict[str, Any] = {
        "live_read": False,
        "tools_used": [],
    }
    try:
        result = await application.mcp.call_tool("hub_list_devices", {})
        diagnostic["live_read"] = True
        diagnostic["result_is_error"] = bool(getattr(result, "is_error", False))
        diagnostic["tools_used"].append(
            {
                "name": "hub_list_devices",
                "success": not bool(getattr(result, "is_error", False)),
            }
        )
        if not getattr(result, "is_error", False):
            rows = _device_rows(getattr(result, "data", None))
            candidates = _thermostat_inventory_candidates(rows)
            diagnostic["device_count"] = len(rows)
            diagnostic["candidate_count"] = len(candidates)
            diagnostic["candidates"] = [
                {"id": _device_id(item), "label": _device_label(item)}
                for item in candidates[:6]
            ]

            # Prefer the explicitly named main Thermostat. If it is not present,
            # probe a small bounded set of thermostat/TRV candidates.
            probe = (
                candidates[:1]
                if candidates and _device_label(candidates[0]).lower() == "thermostat"
                else candidates[:4]
            )
            for candidate in probe:
                device_id = _device_id(candidate)
                if not device_id:
                    continue
                detail = await application.mcp.call_tool(
                    "hub_get_device",
                    {"deviceId": device_id},
                )
                detail_success = not bool(getattr(detail, "is_error", False))
                diagnostic["tools_used"].append(
                    {"name": "hub_get_device", "success": detail_success}
                )
                if not detail_success:
                    continue
                detail_rows = _device_rows(getattr(detail, "data", None))
                reading = _thermostat_reading(detail_rows)
                if reading is not None:
                    diagnostic["source"] = "hub_get_device"
                    diagnostic["selected_device_id"] = device_id
                    diagnostic["selected_device_label"] = reading.get("label")
                    return reading, diagnostic

            # Compatibility path for older servers whose inventory response is
            # already detailed enough to contain live setpoint attributes.
            reading = _thermostat_reading(candidates)
            if reading is not None:
                diagnostic["source"] = "hub_list_devices"
                return reading, diagnostic
    except Exception as exc:
        diagnostic["live_error"] = str(exc) or type(exc).__name__

    index = getattr(application, "device_index", None)
    read = getattr(index, "enriched_devices", None)
    if callable(read):
        try:
            rows = list(await read())
            diagnostic["inventory_count"] = len(rows)
            reading = _thermostat_reading(rows)
            if reading is not None:
                diagnostic["source"] = "device_index_fallback"
                return reading, diagnostic
        except Exception as exc:
            diagnostic["inventory_error"] = str(exc) or type(exc).__name__
    return None, diagnostic


def correct_thermostat_summary(message: str, devices: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    match = _SET_TO_PATTERN.search(str(message or ""))
    if not match:
        return message, None
    reading = None
    if devices and devices[0].get("heating_setpoint") is not None:
        reading = devices[0]
    if reading is None:
        reading = _thermostat_reading(devices)
    if reading is None or reading.get("heating_setpoint") is None:
        return message, None

    claimed = float(match.group(1))
    temperature = reading.get("temperature")
    setpoint = float(reading["heating_setpoint"])
    if temperature is None or abs(claimed - float(temperature)) > 0.05 or abs(claimed - setpoint) <= 0.05:
        return message, None

    replacement = (
        f"the thermostat room temperature is {_format_celsius(float(temperature))}, "
        f"and its heating setpoint is {_format_celsius(setpoint)}"
    )
    corrected = _SET_TO_PATTERN.sub(replacement, message, count=1)
    return corrected, {
        "device": reading["label"],
        "measured_temperature": temperature,
        "heating_setpoint": setpoint,
        "claimed_setpoint": claimed,
        "reason": "measured-temperature-was-described-as-setpoint",
    }


def _direct_answer(reading: dict[str, Any], diagnostic: dict[str, Any]) -> dict[str, Any]:
    temperature = reading.get("temperature")
    heating = reading.get("heating_setpoint")
    cooling = reading.get("cooling_setpoint")
    parts: list[str] = []
    if temperature is not None:
        parts.append(f"The thermostat room temperature is {_format_celsius(float(temperature))}")
    if heating is not None:
        parts.append(f"its heating setpoint is {_format_celsius(float(heating))}")
    if cooling is not None:
        parts.append(f"its cooling setpoint is {_format_celsius(float(cooling))}")
    message = ", and ".join(parts[:2]) + "."
    if len(parts) > 2:
        message = ", ".join(parts[:-1]) + f", and {parts[-1]}."
    metrics = []
    if temperature is not None:
        metrics.append({"label": "Room temperature", "value": _format_celsius(float(temperature)), "icon": "🌡️"})
    if heating is not None:
        metrics.append({"label": "Heating setpoint", "value": _format_celsius(float(heating)), "icon": "🔥"})
    if cooling is not None:
        metrics.append({"label": "Cooling setpoint", "value": _format_celsius(float(cooling)), "icon": "❄️"})
    display = display_payload(
        "thermostat-live-state",
        reading.get("label") or "Thermostat",
        subtitle="Authoritative live thermostat attributes",
        metrics=metrics,
        note="Room temperature and thermostat setpoints are reported as separate attributes.",
    )
    display["summary"] = message
    return {
        "success": True,
        "route": "mcp-thermostat-live-state",
        "intent": "thermostat-live-state",
        "message": message,
        "display": display,
        "thermostat": reading,
        "technical": safe_debug({"thermostat": reading, "read": diagnostic}),
        "answered_by": "Deterministic live Hubitat thermostat reader",
        "tools_used": list(diagnostic.get("tools_used") or []),
    }


def install_thermostat_summary_guard(application: Any) -> AskHandler:
    """Use live thermostat state for direct reads and correct AI summary semantics."""

    original_ask: AskHandler = application.ask

    async def guarded_ask(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "")
        if _DIRECT_THERMOSTAT_QUERY.search(query):
            reading, diagnostic = await _live_thermostat_reading(application)
            if reading is not None:
                return _direct_answer(reading, diagnostic)

        answer = dict(await original_ask(request))
        lowered = query.lower()
        message = str(answer.get("message") or "")
        if not any(term in lowered for term in _HOME_SUMMARY_TERMS) or not _SET_TO_PATTERN.search(message):
            return answer

        reading, diagnostic = await _live_thermostat_reading(application)
        if reading is None:
            answer["thermostat_summary_guard_read"] = diagnostic
            return answer
        corrected, evidence = correct_thermostat_summary(message, [reading])
        if evidence is None:
            return answer
        answer["message"] = corrected
        display = answer.get("display")
        if isinstance(display, dict):
            display = dict(display)
            if display.get("summary") == message:
                display["summary"] = corrected
            answer["display"] = display
        answer["thermostat_semantics_corrected"] = True
        answer["thermostat_semantics"] = evidence
        answer["thermostat_summary_guard_read"] = diagnostic
        return answer

    application.ask = guarded_ask
    return original_ask


__all__ = [
    "correct_thermostat_summary",
    "install_thermostat_summary_guard",
]

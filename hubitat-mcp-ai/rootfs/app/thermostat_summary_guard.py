from __future__ import annotations

import re
from typing import Any, Awaitable, Callable


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


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _number(value: Any) -> float | None:
    if isinstance(value, dict):
        for name in ("currentValue", "value", "state", "text"):
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
                "label": label,
                "temperature": temperature,
                "heating_setpoint": heating if heating is not None else generic,
                "cooling_setpoint": _number(attrs.get("coolingsetpoint")),
                "mode": attrs.get("thermostatmode"),
            }
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (0 if "thermostat" in item["label"].lower() else 1, item["label"].lower()))
    return candidates[0]


def _format_celsius(value: float) -> str:
    return f"{value:g}°C"


def correct_thermostat_summary(message: str, devices: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    match = _SET_TO_PATTERN.search(str(message or ""))
    if not match:
        return message, None
    reading = _thermostat_reading(devices)
    if reading is None or reading.get("heating_setpoint") is None:
        return message, None

    claimed = float(match.group(1))
    temperature = reading.get("temperature")
    setpoint = float(reading["heating_setpoint"])

    # Only rewrite the known failure mode: the claimed setpoint equals the measured
    # temperature while the authoritative heating setpoint is different.
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


def install_thermostat_summary_guard(application: Any) -> AskHandler:
    """Correct AI home summaries that confuse room temperature with setpoint."""

    original_ask: AskHandler = application.ask

    async def guarded_ask(request: Any) -> dict[str, Any]:
        answer = dict(await original_ask(request))
        query = str(getattr(request, "query", "") or "").lower()
        message = str(answer.get("message") or "")
        if not any(term in query for term in _HOME_SUMMARY_TERMS) or not _SET_TO_PATTERN.search(message):
            return answer

        index = getattr(application, "device_index", None)
        read = getattr(index, "enriched_devices", None)
        if not callable(read):
            return answer
        try:
            devices = list(await read())
        except Exception as exc:
            answer["thermostat_summary_guard_error"] = str(exc) or type(exc).__name__
            return answer

        corrected, evidence = correct_thermostat_summary(message, devices)
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
        return answer

    application.ask = guarded_ask
    return original_ask


__all__ = [
    "correct_thermostat_summary",
    "install_thermostat_summary_guard",
]

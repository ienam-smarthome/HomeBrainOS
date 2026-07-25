from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from control_agent_gate import is_contextual_device_control, is_exact_fast_control
from control_agent_intent import is_control_candidate
from contextual_control import is_other_device_control
from device_health_fast_route import is_attention_query, is_device_health_query
from entity_request_policy import parse_entity_request
from entity_resolution import ResolutionRequest, ResolutionStatus, resolve_devices
from fallback_router import _device_id, _label
from mutation_result_policy import enforce_device_mutation_result
from routing_policy import classify_query


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_PROTOCOL_FOLLOWUPS = {
    "yes",
    "no",
    "cancel",
    "confirm",
    "proceed",
    "do it",
    "create it",
    "create paused rule",
    "repair it",
    "retry",
}
_CONTEXT_WORDS = {
    "again",
    "also",
    "another",
    "it",
    "its",
    "same",
    "that",
    "them",
    "then",
    "these",
    "this",
    "those",
}
_CONTEXT_PREFIXES = (
    "and ",
    "how about ",
    "what about ",
    "what is its ",
    "what's its ",
)


def _normalise(value: str) -> str:
    return " ".join(str(value or "").strip().lower().strip(" .!?").split())


def _normalise_history(items: Any) -> list[dict[str, str]]:
    """Convert Pydantic history models and mappings to the agent's stable format."""

    normalised: list[dict[str, str]] = []
    for item in list(items or []):
        if isinstance(item, dict):
            role = item.get("role")
            content = item.get("content")
        elif hasattr(item, "model_dump"):
            value = item.model_dump()
            role = value.get("role")
            content = value.get("content")
        else:
            role = getattr(item, "role", None)
            content = getattr(item, "content", None)
        if role in {"user", "assistant"} and content:
            normalised.append({"role": str(role), "content": str(content)})
    return normalised


def _uses_conversation_context(query: str) -> bool:
    """Return true only when the current request explicitly depends on prior turns."""

    q = _normalise(query)
    if not q:
        return False
    if q in _PROTOCOL_FOLLOWUPS or q.startswith(_CONTEXT_PREFIXES):
        return True
    words = set(re.findall(r"[a-z0-9]+", q))
    return bool(words & _CONTEXT_WORDS)


def _executed_tool_names(answer: Any) -> set[str]:
    """Return only tools that actually executed, never tools merely offered to the model.

    ``selected_tools`` is the planner catalogue subset. It can contain
    ``homebrain_search_devices`` even when the model actually called only
    ``hub_list_devices``. Mixing the two caused targeted lookup correction to be skipped.
    """

    if not isinstance(answer, dict):
        return set()
    names: set[str] = set()
    for item in answer.get("tools_used") or []:
        if isinstance(item, dict) and item.get("name"):
            names.add(str(item["name"]))
        elif isinstance(item, str):
            names.add(item)
    return names


def _has_successful_tool_call(answer: Any) -> bool:
    if not isinstance(answer, dict):
        return False
    return any(
        isinstance(item, dict) and item.get("success") is True
        for item in answer.get("tools_used") or []
    )


def _looks_like_false_evidence_failure(message: Any) -> bool:
    text = _normalise(str(message or ""))
    return any(
        marker in text
        for marker in (
            "trouble retrieving",
            "timing out",
            "system is timing out",
            "too many items",
            "could not retrieve the full device list",
            "couldn't retrieve the full device list",
            "don't have a list of your devices",
            "do not have a list of your devices",
            "don't have your device list",
            "do not have your device list",
        )
    )


async def _apply_automation_recommendation_policy(
    application: Any,
    query: str,
    answer: dict[str, Any],
) -> dict[str, Any]:
    """Replace a false MCP timeout claim with the grounded recommendation service."""

    service = getattr(application, "automation_recommendation", None)
    matches = getattr(service, "matches", None)
    if not callable(matches) or not matches(query):
        return answer
    if not _has_successful_tool_call(answer):
        return answer
    if not _looks_like_false_evidence_failure(answer.get("message")):
        return answer

    try:
        corrected = await service.answer(query)
    except Exception as exc:
        result = dict(answer)
        result["recommendation_policy_error"] = str(exc) or type(exc).__name__
        return result

    result = dict(corrected)
    result["synthesis_policy_corrected"] = True
    result["original_message"] = str(answer.get("message") or "")
    result["original_executed_tools"] = sorted(_executed_tool_names(answer))
    return result


_DEVICE_ATTRIBUTE_REQUESTS = (
    (re.compile(r"\b(?:lux|illuminance)\b", re.IGNORECASE), "illuminance", "lux"),
    (re.compile(r"\b(?:temperature|temp)\b", re.IGNORECASE), "temperature", "°C"),
    (re.compile(r"\b(?:humidity|relative humidity)\b", re.IGNORECASE), "humidity", "%"),
    (re.compile(r"\b(?:power|watts?|wattage)\b", re.IGNORECASE), "power", "W"),
    (re.compile(r"\b(?:energy|kilowatt[- ]?hours?|kwh)\b", re.IGNORECASE), "energy", "kWh"),
    (re.compile(r"\b(?:battery|battery level)\b", re.IGNORECASE), "battery", "%"),
)

_NON_DEVICE_ATTRIBUTE_QUERY = re.compile(
    r"\b(?:all|average|compare|highest|lowest|most|least|total|whole[- ]?house|"
    r"home|today|yesterday|this (?:week|month|year)|last (?:hour|day|week|month))\b",
    re.IGNORECASE,
)


def _requested_device_attribute(query: str) -> tuple[str, str] | None:
    q = _normalise(query)
    if _NON_DEVICE_ATTRIBUTE_QUERY.search(q):
        return None
    if not any(
        term in q
        for term in (
            "reading",
            "value",
            "current",
            "what is",
            "what's",
            "what temperature",
            "what humidity",
            "how bright",
            "how much power",
            "how much energy",
        )
    ):
        return None
    for pattern, attribute, unit in _DEVICE_ATTRIBUTE_REQUESTS:
        if pattern.search(q):
            return attribute, unit
    return None


def _attribute_target_phrase(query: str) -> str:
    q = str(query or "").strip().strip(" .!?")
    parsed_request = parse_entity_request(query)

    # A natural room metric question such as
    # "What is the humidity in the bathroom?" identifies a room rather than a
    # named device. Return that complete room name so the exact-room metric
    # route can select and probe only devices assigned to that room.
    if parsed_request.room:
        parsed_target = _normalise(parsed_request.target_phrase)
        requested_attribute = _requested_device_attribute(query)
        attribute_terms = {
            "temperature",
            "temp",
            "humidity",
            "relative humidity",
            "battery",
            "battery level",
            "power",
            "energy",
            "lux",
            "illuminance",
        }
        if requested_attribute and parsed_target in attribute_terms:
            return parsed_request.room

    match = re.search(r"\b(?:from|of)\s+(.+)$", q, re.IGNORECASE)
    if match:
        return re.sub(
            r"^(?:the|a|an)\s+",
            "",
            match.group(1),
            flags=re.IGNORECASE,
        ).strip()
    patterns = (
        r"^what\s+(?:temperature|humidity|battery(?: level)?|power|energy|lux|illuminance)\s+is\s+(.+)$",
        r"^how\s+much\s+(?:power|energy)\s+(?:is|does)\s+(.+?)(?:\s+(?:using|use|reporting|report))?$",
        r"^how\s+bright\s+is\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, q, re.IGNORECASE)
        if match:
            return re.sub(r"^(?:the|a|an)\s+", "", match.group(1), flags=re.IGNORECASE).strip()

    target = parse_entity_request(query).target_phrase
    target = re.sub(
        r"\b(?:current|reading|value|temperature|temp|humidity|relative humidity|"
        r"battery(?: level)?|power|watts?|wattage|energy|kilowatt[- ]?hours?|kwh|"
        r"lux|illuminance)\b",
        " ",
        target,
        flags=re.IGNORECASE,
    )
    target = re.sub(r"\s+", " ", target).strip(" -")
    return target


def _tool_data(result: Any) -> Any:
    return getattr(result, "data", result)


_ATTRIBUTE_ALIASES = {
    "illuminance": {"illuminance", "illuminancelevel", "lux"},
    "temperature": {"temperature", "temp"},
    "humidity": {"humidity", "relativehumidity"},
    "power": {"power", "powermeter", "watts", "wattage"},
    "energy": {"energy", "energymeter"},
    "battery": {"battery", "batterylevel"},
}
_ATTRIBUTE_VALUE_KEYS = ("currentValue", "currentState", "value", "displayValue", "current_value")
_INVENTORY_STATE_PRIORITY = (
    "switch",
    "contact",
    "water",
    "smoke",
    "carbonMonoxide",
    "motion",
    "acceleration",
    "presence",
    "lock",
    "valve",
    "thermostatOperatingState",
    "thermostatMode",
    "temperature",
    "humidity",
    "illuminance",
    "power",
    "energy",
    "level",
    "battery",
    "healthStatus",
    "deviceHealth",
    "health",
)
_INVENTORY_STATE_ALIASES = {
    "switch": {"switch"},
    "contact": {"contact", "contactsensor"},
    "water": {"water", "watersensor"},
    "smoke": {"smoke", "smokedetector"},
    "carbonMonoxide": {"carbonmonoxide", "co", "codetector"},
    "motion": {"motion", "motionsensor"},
    "acceleration": {"acceleration", "accelerationsensor"},
    "presence": {"presence", "presencesensor"},
    "lock": {"lock"},
    "valve": {"valve"},
    "thermostatOperatingState": {"thermostatoperatingstate", "operatingstate"},
    "thermostatMode": {"thermostatmode"},
    "temperature": {"temperature", "temp"},
    "humidity": {"humidity", "relativehumidity"},
    "illuminance": {"illuminance", "illuminancelevel", "lux"},
    "power": {"power", "powermeter", "watts", "wattage"},
    "energy": {"energy", "energymeter"},
    "level": {"level", "switchlevel"},
    "battery": {"battery", "batterylevel"},
    "healthStatus": {"healthstatus"},
    "deviceHealth": {"devicehealth"},
    "health": {"health"},
}


def _attribute_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _present_attribute_value(value: Any) -> Any:
    if isinstance(value, dict):
        for key in _ATTRIBUTE_VALUE_KEYS:
            candidate = value.get(key)
            if candidate not in (None, ""):
                return candidate
    return value if value not in (None, "") else None


def _extract_attribute_value(value: Any, attribute: str) -> Any:
    aliases = _ATTRIBUTE_ALIASES.get(attribute, {attribute})
    aliases = {_attribute_key(item) for item in aliases | {attribute}}
    if isinstance(value, dict):
        record_name = value.get("name") or value.get("attribute") or value.get("key")
        if _attribute_key(record_name) in aliases:
            record_value = _present_attribute_value(value)
            if record_value not in (None, "") and record_value is not value:
                return record_value

        for key, candidate in value.items():
            if _attribute_key(key) in aliases:
                direct_value = _present_attribute_value(candidate)
                if direct_value not in (None, ""):
                    return direct_value

        states = (
            value.get("currentStates")
            or value.get("current_states")
            or value.get("attributes")
            or value.get("states")
        )
        if states is not None:
            found = _extract_attribute_value(states, attribute)
            if found not in (None, ""):
                return found

        for child in value.values():
            found = _extract_attribute_value(child, attribute)
            if found not in (None, ""):
                return found
    elif isinstance(value, (list, tuple)):
        for child in value:
            found = _extract_attribute_value(child, attribute)
            if found not in (None, ""):
                return found
    return None


def _inventory_state_value(device: dict[str, Any], attribute: str) -> Any:
    """Read a compact inventory state without mistaking metadata for live state."""

    aliases = _INVENTORY_STATE_ALIASES.get(attribute, {attribute})
    aliases = {_attribute_key(item) for item in aliases}
    states = (
        device.get("currentStates")
        or device.get("current_states")
        or device.get("attributes")
        or device.get("states")
    )
    if isinstance(states, dict):
        for key, candidate in states.items():
            if _attribute_key(key) in aliases:
                return _present_attribute_value(candidate)
    elif isinstance(states, (list, tuple)):
        for record in states:
            if not isinstance(record, dict):
                continue
            name = record.get("name") or record.get("attribute") or record.get("key")
            if _attribute_key(name) in aliases:
                return _present_attribute_value(record)
    return None


def _title_state(value: Any) -> str:
    return str(value).strip().replace("_", " ").replace("-", " ").title()


def _inventory_primary_state(device: dict[str, Any], disabled: bool) -> dict[str, Any]:
    """Project the most useful live state already present in hub_list_devices."""

    if disabled:
        return {
            "attribute": None,
            "value": "Disabled",
            "icon": "⏸️",
            "tone": "muted",
            "available": False,
        }

    for attribute in _INVENTORY_STATE_PRIORITY:
        raw_value = _inventory_state_value(device, attribute)
        if raw_value in (None, ""):
            continue
        normalised = _normalise(str(raw_value))
        if attribute == "switch":
            value = "On" if normalised == "on" else "Off" if normalised == "off" else _title_state(raw_value)
            return {
                "attribute": attribute,
                "value": value,
                "icon": "💡",
                "tone": "success" if normalised == "on" else "neutral",
                "available": True,
            }
        if attribute == "contact":
            value = "Open" if normalised == "open" else "Closed" if normalised == "closed" else _title_state(raw_value)
            return {
                "attribute": attribute,
                "value": value,
                "icon": "🚪",
                "tone": "warning" if normalised == "open" else "success",
                "available": True,
            }
        if attribute in {"water", "smoke", "carbonMonoxide"}:
            clear_values = {"clear", "dry", "tested"}
            alert_values = {"detected", "wet"}
            value = _title_state(raw_value)
            return {
                "attribute": attribute,
                "value": value,
                "icon": "💧" if attribute == "water" else "🚨",
                "tone": (
                    "danger"
                    if normalised in alert_values
                    else "success"
                    if normalised in clear_values
                    else "neutral"
                ),
                "available": True,
            }
        if attribute == "motion":
            value = "Active" if normalised == "active" else "Inactive" if normalised == "inactive" else _title_state(raw_value)
            return {
                "attribute": attribute,
                "value": value,
                "icon": "🏃",
                "tone": "warning" if normalised == "active" else "neutral",
                "available": True,
            }
        if attribute == "acceleration":
            value = "Active" if normalised == "active" else "Inactive" if normalised == "inactive" else _title_state(raw_value)
            return {
                "attribute": attribute,
                "value": value,
                "icon": "📳",
                "tone": "warning" if normalised == "active" else "neutral",
                "available": True,
            }
        if attribute == "presence":
            value = "Present" if normalised in {"present", "on", "true"} else "Not present" if normalised in {"not present", "notpresent", "off", "false"} else _title_state(raw_value)
            return {
                "attribute": attribute,
                "value": value,
                "icon": "👤",
                "tone": "success" if value == "Present" else "neutral",
                "available": True,
            }
        if attribute == "lock":
            value = "Locked" if normalised == "locked" else "Unlocked" if normalised == "unlocked" else _title_state(raw_value)
            return {
                "attribute": attribute,
                "value": value,
                "icon": "🔒" if normalised == "locked" else "🔓",
                "tone": "success" if normalised == "locked" else "warning",
                "available": True,
            }
        if attribute == "valve":
            value = "Open" if normalised == "open" else "Closed" if normalised == "closed" else _title_state(raw_value)
            return {
                "attribute": attribute,
                "value": value,
                "icon": "🚰",
                "tone": "warning" if normalised == "open" else "success",
                "available": True,
            }
        if attribute in {"thermostatOperatingState", "thermostatMode"}:
            return {
                "attribute": attribute,
                "value": _title_state(raw_value),
                "icon": "🌡️",
                "tone": "success" if normalised not in {"off", "idle"} else "neutral",
                "available": True,
            }
        if attribute == "temperature":
            value = _format_attribute_value(raw_value, "°C")
            icon = "🌡️"
        elif attribute == "humidity":
            value = _format_attribute_value(raw_value, "%")
            icon = "💧"
        elif attribute == "power":
            value = _format_attribute_value(raw_value, "W")
            icon = "⚡"
        elif attribute == "energy":
            value = _format_attribute_value(raw_value, "kWh")
            icon = "🔌"
        elif attribute == "illuminance":
            value = _format_attribute_value(raw_value, "lux")
            icon = "☀️"
        elif attribute == "level":
            value = _format_attribute_value(raw_value, "%")
            icon = "🔆"
        elif attribute == "battery":
            value = _format_attribute_value(raw_value, "%")
            icon = "🔋"
        else:
            value = _title_state(raw_value)
            icon = "🩺"
        health_problem = attribute in {"healthStatus", "deviceHealth", "health"} and normalised not in {
            "ok",
            "online",
            "healthy",
        }
        return {
            "attribute": attribute,
            "value": value,
            "icon": icon,
            "tone": "danger" if health_problem else "neutral",
            "available": True,
        }

    return {
        "attribute": None,
        "value": "State unavailable",
        "icon": "📱",
        "tone": "muted",
        "available": False,
    }


def _format_attribute_value(value: Any, unit: str) -> str:
    text = str(value).strip()
    if not unit:
        return text
    if unit in {"%", "°C"}:
        return f"{text}{unit}"
    return f"{text} {unit}"


def _format_attribute_message(label: str, attribute: str, value: Any, unit: str) -> str:
    formatted = _format_attribute_value(value, unit)
    if attribute == "humidity":
        normalised_label = _normalise(label)
        if "humidity" not in normalised_label:
            room = re.sub(r"\b(?:meter|sensor)\b", " ", label, flags=re.IGNORECASE)
            room = re.sub(r"\s+", " ", room).strip(" -")
            if room:
                return f"{room} humidity is {formatted}."
    return f"{label} is {formatted}."


async def _load_authoritative_inventory(application: Any) -> tuple[Any, list[dict[str, Any]]]:
    result = await application.mcp.call_tool("hub_list_devices", {})
    return result, list(_iter_device_records(_tool_data(result)))


async def _read_authoritative_device(application: Any, device_id: str) -> Any:
    # ``hub_read_devices`` is a category gateway in the upstream MCP server,
    # not a device-detail operation.  The state broker translates this hidden
    # operation to hub_read_devices(tool="hub_get_device", args={...}) when
    # gateways are enabled, while still supporting legacy flat-tool mode.
    return await application.mcp.call_tool("hub_get_device", {"deviceId": device_id})


async def _answer_terminal_entity_read(application: Any, query: str) -> dict[str, Any] | None:
    inventory_request = _is_all_device_inventory_query(query)
    explicit_lookup = _is_explicit_device_lookup(query)
    attribute_request = _requested_device_attribute(query)
    if not inventory_request and not explicit_lookup and attribute_request is None:
        return None

    inventory_result, devices = await _load_authoritative_inventory(application)
    tools_used = [{"name": "hub_list_devices", "success": not bool(getattr(inventory_result, "is_error", False))}]
    if inventory_request:
        ordered = sorted(devices, key=lambda item: _normalise(_label(item)))
        inventory = []
        rooms: set[str] = set()
        disabled_count = 0
        for device in ordered:
            room_value = device.get("room") or device.get("roomName") or device.get("room_name")
            if isinstance(room_value, dict):
                room_value = room_value.get("name") or room_value.get("label")
            room = str(room_value or "").strip()
            if room:
                rooms.add(room)
            disabled = bool(device.get("disabled"))
            disabled_count += int(disabled)
            primary_state = _inventory_primary_state(device, disabled)
            inventory.append(
                {
                    "id": str(_device_id(device) or ""),
                    "label": _label(device) or "Unnamed device",
                    "room": room or None,
                    "device_type": (
                        device.get("deviceType")
                        or device.get("category")
                        or device.get("name")
                    ),
                    "disabled": disabled,
                    "state": primary_state["value"],
                    "state_attribute": primary_state["attribute"],
                    "state_available": primary_state["available"],
                    "state_icon": primary_state["icon"],
                    "state_tone": primary_state["tone"],
                }
            )

        total = len(inventory)
        message = f"Found {total} selected Hubitat device{'' if total == 1 else 's'}."
        if rooms:
            message += f" They are assigned across {len(rooms)} room{'' if len(rooms) == 1 else 's'}."
        return {
            "success": not bool(getattr(inventory_result, "is_error", False)),
            "route": "mcp-fast",
            "intent": "device-inventory",
            "message": message,
            "device_count": total,
            "room_count": len(rooms),
            "disabled_count": disabled_count,
            "device_inventory": inventory,
            "display": {
                "kind": "device-inventory",
                "title": "All Hubitat devices",
                "subtitle": f"{total} selected devices",
                "metrics": [
                    {"label": "Devices", "value": str(total), "icon": "📱"},
                    {"label": "Rooms", "value": str(len(rooms)), "icon": "🏠"},
                    {"label": "Disabled", "value": str(disabled_count), "icon": "⏸️"},
                ],
                "items": [
                    {
                        "icon": item["state_icon"],
                        "title": item["label"],
                        "subtitle": " · ".join(
                            value
                            for value in (
                                str(item["room"] or ""),
                                str(item["device_type"] or ""),
                            )
                            if value
                        ),
                        "value": item["state"],
                        "tone": item["state_tone"],
                    }
                    for item in inventory
                ],
                "note": (
                    "Primary states exposed by the live Hubitat device inventory. "
                    "Open a device for complete state details."
                ),
            },
            "tools_used": tools_used,
            "entity_resolution_request": parse_entity_request(query).as_dict(),
            "answered_by": "deterministic device inventory",
        }

    entity_request = parse_entity_request(query)
    target_phrase = (
        entity_request.target_phrase
        if explicit_lookup
        else _attribute_target_phrase(query)
    )
    target_request = parse_entity_request(target_phrase)

    # Phrases such as "Bedroom 2 Meter" contain a room prefix but do not use
    # explicit grammar such as "meter in Bedroom 2". Infer that room from the
    # authoritative inventory before confidence scoring so shared room words
    # cannot make unrelated devices appear ambiguous.
    inferred_room = target_request.room
    if not inferred_room:
        normalised_phrase = _normalise(target_phrase)
        inventory_rooms = sorted(
            {
                _normalise(_device_room(item))
                for item in devices
                if _normalise(_device_room(item))
            },
            key=len,
            reverse=True,
        )
        inferred_room = next(
            (
                room_name
                for room_name in inventory_rooms
                if normalised_phrase == room_name
                or normalised_phrase.startswith(room_name + " ")
            ),
            None,
        )

    normalised_target = _normalise(target_phrase)
    compact_target = re.sub(r"[^a-z0-9]", "", normalised_target)
    exact_label_match = any(
        re.sub(r"[^a-z0-9]", "", _normalise(_label(item))) == compact_target
        for item in devices
    )
    exact_room_match = any(
        _normalise(_device_room(item)) == normalised_target
        for item in devices
    )
    room_metric_request = bool(
        attribute_request
        and exact_room_match
        and not exact_label_match
    )

    if room_metric_request:
        shared_resolution = None
        shared_resolution_data = {
            "status": "room_metric",
            "confidence": 1.0,
            "targets": [],
            "candidates": [],
            "reason": "The target phrase exactly matches a room rather than a device label.",
            "query": target_phrase,
            "metadata": {"room_metric_request": True},
        }
    else:
        shared_resolution = resolve_devices(
            devices,
            ResolutionRequest(
                target_phrase=target_phrase,
                room=inferred_room,
                device_type=target_request.device_type,
                ordinal=target_request.ordinal,
                allow_group=False,
            ),
        )
        shared_resolution_data = shared_resolution.as_dict()

    resolved_by_confidence = False

    if (
        shared_resolution is not None
        and shared_resolution.status is ResolutionStatus.AMBIGUOUS
    ):
        labels = [item.label for item in shared_resolution.candidates[:3]]
        choices = ", ".join(labels)
        return {
            "success": False,
            "route": "mcp-fast",
            "intent": "device-resolution-ambiguous",
            "message": (
                f'I found multiple devices matching "{target_phrase}": '
                f"{choices}. Please use the exact device name."
            ),
            "confirmation_required": True,
            "alternatives": labels,
            "tools_used": tools_used,
            "entity_resolution_request": entity_request.as_dict(),
            "entity_resolution": shared_resolution_data,
            "answered_by": "shared deterministic entity resolver",
        }

    if (
        shared_resolution is not None
        and shared_resolution.status is ResolutionStatus.RESOLVED
        and shared_resolution.targets
    ):
        resolved_id = shared_resolution.targets[0].device_id
        device = next(
            (
                item
                for item in devices
                if str(_device_id(item) or "") == resolved_id
            ),
            None,
        )
        candidates = [device] if device is not None else []
        resolved_by_confidence = device is not None
    elif room_metric_request:
        # Room-level reads use exact room membership rather than fuzzy label
        # ranking. Attribute-compatible devices are probed in deterministic
        # order, while named-device NOT_FOUND remains terminal.
        candidates = _room_metric_candidates(
            devices,
            normalised_target,
            attribute_request[0] if attribute_request else None,
        )
        device = candidates[0] if candidates else None
    else:
        candidates = []
        device = None

    if device is None:
        if room_metric_request and attribute_request:
            attribute, unit = attribute_request
            room_label = next(
                (
                    _device_room(item)
                    for item in devices
                    if _normalise(_device_room(item)) == normalised_target
                ),
                target_phrase,
            )
            return {
                "success": False,
                "route": "mcp-fast",
                "intent": "device-attribute-read",
                "message": (
                    f"No device in {room_label} exposed a current "
                    f"{attribute} value."
                ),
                "device_id": "",
                "device_label": room_label,
                "attribute": attribute,
                "value": None,
                "unit": unit,
                "devices_probed": 0,
                "tools_used": tools_used,
                "entity_resolution_request": entity_request.as_dict(),
                "entity_resolution": shared_resolution_data,
                "answered_by": "deterministic entity reader",
            }

        return {
            "success": False,
            "route": "mcp-fast",
            "intent": "device-lookup" if explicit_lookup else "device-attribute-read",
            "message": f'I could not find a device matching "{target_phrase}".',
            "tools_used": tools_used,
            "entity_resolution_request": entity_request.as_dict(),
            "entity_resolution": shared_resolution_data,
            "answered_by": "shared deterministic entity resolver",
        }

    if explicit_lookup:
        return {
            "success": True,
            "route": "mcp-fast",
            "intent": "device-lookup",
            "message": _format_lookup_device(device),
            "lookup_device": {
                "id": str(_device_id(device) or ""),
                "label": _label(device),
                "room": device.get("room") or device.get("roomName") or device.get("room_name"),
                "device_type": device.get("name") or device.get("category") or device.get("deviceType"),
                "disabled": bool(device.get("disabled")),
            },
            "tools_used": tools_used,
            "entity_resolution_request": parse_entity_request(query).as_dict(),
            "answered_by": "deterministic entity resolver",
        }

    attribute, unit = attribute_request
    selected_score = _lookup_record_score(device, target_phrase, attribute)
    exact_device_match = resolved_by_confidence or selected_score[0] > 0

    value = None
    devices_probed = 0
    probe_candidates = (
        [device]
        if exact_device_match
        else candidates[:_MAX_ROOM_METRIC_PROBES]
    )

    for candidate in probe_candidates:
        read_result = await _read_authoritative_device(
            application,
            str(_device_id(candidate) or ""),
        )
        read_success = not bool(getattr(read_result, "is_error", False))
        tools_used.append({"name": "hub_get_device", "success": read_success})
        devices_probed += 1

        candidate_value = _extract_attribute_value(
            _tool_data(read_result),
            attribute,
        )
        if candidate_value not in (None, ""):
            device = candidate
            value = candidate_value
            break
    label = _label(device) or "Device"
    response_device_id = str(_device_id(device) or "")
    response_device_label = label

    if value in (None, ""):
        if room_metric_request:
            room_label = _device_room(device) or target_phrase
            message = (
                f"No device in {room_label} exposed a current "
                f"{attribute} value."
            )
            response_device_id = ""
            response_device_label = room_label
        else:
            message = (
                f"{label} is available, but Hubitat did not expose "
                f"a current {attribute} value."
            )
        success = False
    else:
        message = _format_attribute_message(label, attribute, value, unit)
        success = True

    return {
        "success": success,
        "route": "mcp-fast",
        "intent": "device-attribute-read",
        "message": message,
        "device_id": response_device_id,
        "device_label": response_device_label,
        "attribute": attribute,
        "value": value,
        "unit": unit,
        "devices_probed": devices_probed,
        "tools_used": tools_used,
        "entity_resolution_request": parse_entity_request(query).as_dict(),
        "answered_by": "deterministic entity reader",
    }


_LOOKUP_PREFIX_RE = re.compile(
    r"^(?:find|locate|search for|look for|where is|where's)\b",
    re.IGNORECASE,
)

_ALL_DEVICE_INVENTORY_RE = re.compile(
    r"^(?:please\s+)?(?:find|list|show|display|get|search(?:\s+for)?)\s+"
    r"(?:(?:all|my|the)\s+)*devices[?.!]*$",
    re.IGNORECASE,
)


def _is_all_device_inventory_query(query: str) -> bool:
    return bool(_ALL_DEVICE_INVENTORY_RE.fullmatch(str(query or "").strip()))


def _is_explicit_device_lookup(query: str) -> bool:
    """Return true for identity/location lookups, not state or value questions."""

    entity_request = parse_entity_request(query)
    return bool(_LOOKUP_PREFIX_RE.match(_normalise(query))) and entity_request.targeted


def _iter_device_records(value: Any):
    """Yield device-shaped dictionaries from nested targeted-search evidence."""

    if isinstance(value, dict):
        if _device_id(value) not in (None, "") and _label(value):
            yield value
        for child in value.values():
            yield from _iter_device_records(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _iter_device_records(child)


def _device_attribute_support(device: dict[str, Any], attribute: str | None) -> int:
    if not attribute:
        return 0
    aliases = _ATTRIBUTE_ALIASES.get(attribute, {attribute}) | {attribute}
    haystack = " ".join(
        str(device.get(key) or "")
        for key in (
            "label",
            "displayName",
            "name",
            "deviceLabel",
            "category",
            "deviceType",
            "capabilities",
            "currentStates",
            "attributes",
        )
    )
    compact_haystack = _attribute_key(haystack)
    return int(any(_attribute_key(alias) in compact_haystack for alias in aliases))


def _device_room(device: dict[str, Any]) -> str:
    room = device.get("room") or device.get("roomName") or device.get("room_name")
    if isinstance(room, dict):
        room = room.get("name") or room.get("label") or room.get("roomName")
    return str(room or "").strip()


def _device_attribute_compatibility(device: dict[str, Any], attribute: str | None) -> int:
    if attribute not in {"temperature", "humidity", "illuminance"}:
        return 1
    text = f" {_normalise(_label(device))} "
    actuator_terms = (" light ", " lamp ", " bulb ", " switch ", " socket ", " plug ", " outlet ")
    return int(not any(term in text for term in actuator_terms))


def _lookup_record_score(
    device: dict[str, Any],
    target_phrase: str,
    attribute: str | None = None,
) -> tuple[int, int, int, int, int]:
    label = _normalise(_label(device))
    room = _normalise(_device_room(device))
    target = _normalise(target_phrase)
    compact_label = re.sub(r"[^a-z0-9]", "", label)
    compact_target = re.sub(r"[^a-z0-9]", "", target)
    exact = int(bool(compact_target) and compact_label == compact_target)
    target_tokens = set(target.split())
    label_overlap = len(target_tokens & set(label.split()))
    room_overlap = len(target_tokens & set(room.split()))
    target_overlap = max(label_overlap, room_overlap)
    return (
        exact,
        target_overlap,
        _device_attribute_compatibility(device, attribute),
        _device_attribute_support(device, attribute),
        label_overlap,
    )


_MAX_ROOM_METRIC_PROBES = 6


def _room_metric_candidates(
    payload: Any,
    room: str,
    attribute: str | None = None,
) -> list[dict[str, Any]]:
    """Return capability-aware candidates confined to one exact room.

    Prefer devices whose inventory already exposes the requested state, then
    devices advertising matching capability or attribute metadata. When the
    inventory is sparse and exposes no support metadata, retain compatible
    room devices as a bounded fallback.
    """
    room_n = _normalise(room)
    if not room_n:
        return []

    records = [
        item
        for item in _iter_device_records(payload)
        if _normalise(_device_room(item)) == room_n
    ]

    def inventory_support(item: dict[str, Any]) -> int:
        if not attribute:
            return 0
        return int(_inventory_state_value(item, attribute) not in (None, ""))

    supported = [
        item
        for item in records
        if inventory_support(item) or _device_attribute_support(item, attribute)
    ]

    # Detailed capability metadata may be absent from compact inventories.
    # Only use the broader compatible set when no explicit support exists.
    candidates = supported or [
        item
        for item in records
        if _device_attribute_compatibility(item, attribute)
    ]

    def sort_key(item: dict[str, Any]) -> tuple[int, int, int, str, str]:
        return (
            -inventory_support(item),
            -_device_attribute_support(item, attribute),
            -_device_attribute_compatibility(item, attribute),
            _normalise(_label(item)),
            str(_device_id(item) or ""),
        )

    return sorted(candidates, key=sort_key)


def _rank_lookup_devices(
    payload: Any,
    target_phrase: str,
    attribute: str | None = None,
) -> list[dict[str, Any]]:
    records = list(_iter_device_records(payload))
    if not records or not _normalise(target_phrase):
        return []
    def sort_key(item: dict[str, Any]) -> tuple[int, int, int, int, int, str, str]:
        exact, overlap, compatible, support, label_overlap = _lookup_record_score(
            item,
            target_phrase,
            attribute,
        )
        return (
            -exact,
            -overlap,
            -compatible,
            -support,
            -label_overlap,
            _normalise(_label(item)),
            str(_device_id(item) or ""),
        )

    ranked = sorted(records, key=sort_key)
    return [
        item
        for item in ranked
        if (
            _lookup_record_score(item, target_phrase, attribute)[0] > 0
            or _lookup_record_score(item, target_phrase, attribute)[1] > 0
        )
    ]


def _best_lookup_device(
    payload: Any,
    target_phrase: str,
    attribute: str | None = None,
) -> dict[str, Any] | None:
    ranked = _rank_lookup_devices(payload, target_phrase, attribute)
    return ranked[0] if ranked else None


def _format_lookup_device(device: dict[str, Any]) -> str:
    label = str(device.get("label") or device.get("name") or "Device")
    room = device.get("room") or device.get("roomName") or device.get("room_name")
    device_type = device.get("name") or device.get("category") or device.get("deviceType")
    disabled = bool(device.get("disabled"))
    parts = [f"Found {label}"]
    if room:
        parts[0] += f" in {room}"
    if device_type and _normalise(str(device_type)) != _normalise(label):
        parts.append(f"Device type: {device_type}")
    parts.append("Status: disabled" if disabled else "Status: available")
    return ". ".join(parts) + "."


async def _apply_device_lookup_response_policy(
    application: Any,
    query: str,
    history: list[dict[str, str]],
    answer: dict[str, Any],
) -> dict[str, Any]:
    """Make explicit find/locate requests terminal and evidence-shaped.

    A lookup asks where/what a device is. It must not be reinterpreted as a request
    for the device's current sensor value merely because the label contains words
    such as lux, temperature or power.
    """

    if not _is_explicit_device_lookup(query):
        return answer
    entity_request = parse_entity_request(query)
    if entity_request.broad_inventory or not entity_request.targeted:
        return answer
    executed = _executed_tool_names(answer)
    if not ({"homebrain_search_devices", "hub_list_devices"} & executed):
        return answer

    agent = getattr(application, "ollama", None)
    targeted = getattr(agent, "_answer_from_targeted_device_search", None)
    if not callable(targeted):
        return answer

    corrected = await targeted(
        query,
        history,
        RuntimeError("Explicit lookup requires deterministic targeted-device evidence"),
    )
    result = dict(corrected)
    device = _best_lookup_device({"targeted": corrected, "planner": answer}, entity_request.target_phrase)
    if device is not None:
        result["message"] = _format_lookup_device(device)
        result["lookup_device"] = {
            "id": str(device.get("id") or ""),
            "label": str(device.get("label") or device.get("name") or ""),
            "room": device.get("room") or device.get("roomName") or device.get("room_name"),
            "device_type": device.get("name") or device.get("category") or device.get("deviceType"),
            "disabled": bool(device.get("disabled")),
        }
    result["lookup_response_policy_corrected"] = True
    result["entity_resolution_request"] = entity_request.as_dict()
    result["original_message"] = str(answer.get("message") or "")
    result["original_executed_tools"] = sorted(executed)
    return result


async def _apply_device_tool_policy(
    application: Any,
    query: str,
    history: list[dict[str, str]],
    answer: dict[str, Any],
) -> dict[str, Any]:
    """Correct a broad inventory call when the task needs targeted device resolution.

    The model remains responsible for understanding the request. The execution layer is
    responsible for tool semantics: ``hub_list_devices`` is authoritative inventory data,
    but it is not a completed entity lookup. If the planner executed only that broad tool
    for a non-broad request, run the MCP-backed targeted search over the complete structured
    inventory before allowing the answer to stand.
    """

    executed = _executed_tool_names(answer)
    if "hub_list_devices" not in executed or "homebrain_search_devices" in executed:
        return answer

    agent = getattr(application, "ollama", None)
    entity_request = parse_entity_request(query)
    if entity_request.broad_inventory or not entity_request.targeted:
        return answer

    targeted = getattr(agent, "_answer_from_targeted_device_search", None)
    if not callable(targeted):
        return answer

    corrected = await targeted(
        query,
        history,
        RuntimeError("Planner executed broad inventory for a targeted device task"),
    )
    result = dict(corrected)
    result["tool_policy_corrected"] = True
    result["entity_resolution_request"] = entity_request.as_dict()
    result["original_executed_tools"] = sorted(executed)
    result["original_selected_tools"] = [
        str(item) for item in answer.get("selected_tools") or [] if item
    ]
    return result


def should_use_unified_agent(query: str) -> bool:
    """Use AI for every substantive non-fast request."""

    q = _normalise(query)
    if not q or q in _PROTOCOL_FOLLOWUPS:
        return False
    # Device controls are terminally owned by the deterministic Control Agent.
    # The agent may use AI to produce a typed intent, but only Python may resolve
    # device IDs, execute mutations and verify the resulting Hubitat state.
    if is_control_candidate(query):
        return False
    if is_exact_fast_control(query):
        return False
    if is_contextual_device_control(query) or is_other_device_control(query):
        return False
    # Device-health classification is authoritative and intentionally conservative:
    # live healthStatus may confirm a fault, while lastActivity age alone is not one.
    # This guard must live in the outer unified-agent wrapper as well as the inner
    # deterministic route; routing_policy.classify_query is imported independently
    # and does not see the late request-tracing classifier patch.
    if is_device_health_query(query) or is_attention_query(query):
        return False
    return classify_query(q).route != "mcp-fast"


def install_unified_mcp_agent_orchestrator(application: Any) -> None:
    """Install one AI-first decision point above the legacy route stack."""

    original_ask: AskHandler = application.ask

    async def ask_with_unified_agent(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "")
        if not should_use_unified_agent(query):
            return await original_ask(request)

        history = _normalise_history(getattr(request, "history", None))
        history_used = _uses_conversation_context(query)
        if not history_used:
            history = []
        try:
            terminal_entity = await _answer_terminal_entity_read(application, query)
            if terminal_entity is not None:
                terminal_entity.setdefault("success", True)
                terminal_entity["agent_orchestrator"] = "deterministic-entity-read"
                terminal_entity["legacy_fallback_used"] = False
                terminal_entity["conversation_history_used"] = False
                terminal_entity.setdefault("version", application.VERSION)
                return terminal_entity
            planner = getattr(application.ollama, "answer_with_planner", None)
            if callable(planner):
                answer = await planner(query, history)
            else:
                answer = await application.ollama.answer(query, history)
            result = await _apply_device_tool_policy(
                application,
                query,
                history,
                dict(answer),
            )
            result = await _apply_device_lookup_response_policy(
                application,
                query,
                history,
                result,
            )
            result = await _apply_automation_recommendation_policy(
                application,
                query,
                result,
            )
            result = enforce_device_mutation_result(query, result)
            result.setdefault("success", True)
            result["agent_orchestrator"] = "unified-mcp-ai-first"
            result["legacy_fallback_used"] = False
            result["conversation_history_used"] = history_used
            result.setdefault("version", application.VERSION)
            return result
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
            return {
                "success": False,
                "route": "unified-agent-error",
                "intent": "unified-agent-failed",
                "message": f"The unified Hubitat MCP agent could not complete this request: {error}",
                "agent_orchestrator": "unified-mcp-ai-first",
                "legacy_fallback_used": False,
                "conversation_history_used": history_used,
                "unified_agent_error": error,
                "version": application.VERSION,
                "technical": {
                    "unified_agent": {
                        "attempted": True,
                        "fallback": False,
                        "error": error,
                    }
                },
            }

    application.ask = ask_with_unified_agent


__all__ = [
    "_answer_terminal_entity_read",
    "_apply_device_tool_policy",
    "_apply_device_lookup_response_policy",
    "_is_explicit_device_lookup",
    "_is_all_device_inventory_query",
    "_apply_automation_recommendation_policy",
    "_executed_tool_names",
    "_has_successful_tool_call",
    "_looks_like_false_evidence_failure",
    "_normalise_history",
    "_uses_conversation_context",
    "install_unified_mcp_agent_orchestrator",
    "should_use_unified_agent",
]

from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from control_agent_gate import is_contextual_device_control, is_exact_fast_control
from control_agent_intent import is_control_candidate
from contextual_control import is_other_device_control
from device_health_fast_route import is_attention_query, is_device_health_query
from entity_request_policy import parse_entity_request
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
    match = re.search(r"\b(?:from|of)\s+(.+)$", q, re.IGNORECASE)
    if match:
        return match.group(1).strip()
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
_ATTRIBUTE_VALUE_KEYS = ("currentValue", "value", "displayValue", "current_value")


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


async def _load_authoritative_inventory(application: Any) -> tuple[Any, list[dict[str, Any]]]:
    result = await application.mcp.call_tool("hub_list_devices", {})
    return result, list(_iter_device_records(_tool_data(result)))


async def _read_authoritative_device(application: Any, device_id: str) -> Any:
    desired = {
        "ids": [device_id],
        "deviceIds": [device_id],
        "device_ids": [device_id],
        "id": device_id,
        "deviceId": device_id,
    }
    supported = getattr(application.mcp, "supported_arguments", None)
    arguments = await supported("hub_read_devices", desired) if callable(supported) else {"ids": [device_id]}
    if not arguments:
        arguments = {"ids": [device_id]}
    return await application.mcp.call_tool("hub_read_devices", arguments)


async def _answer_terminal_entity_read(application: Any, query: str) -> dict[str, Any] | None:
    explicit_lookup = _is_explicit_device_lookup(query)
    attribute_request = _requested_device_attribute(query)
    if not explicit_lookup and attribute_request is None:
        return None

    inventory_result, devices = await _load_authoritative_inventory(application)
    target_phrase = parse_entity_request(query).target_phrase if explicit_lookup else _attribute_target_phrase(query)
    device = _best_lookup_device(devices, target_phrase, attribute_request[0] if attribute_request else None)
    tools_used = [{"name": "hub_list_devices", "success": not bool(getattr(inventory_result, "is_error", False))}]
    if device is None:
        return {
            "success": False,
            "route": "mcp-fast",
            "intent": "device-lookup" if explicit_lookup else "device-attribute-read",
            "message": f'I could not find a device matching "{target_phrase}".',
            "tools_used": tools_used,
            "entity_resolution_request": parse_entity_request(query).as_dict(),
            "answered_by": "deterministic entity resolver",
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
    read_result = await _read_authoritative_device(application, str(_device_id(device) or ""))
    tools_used.append({"name": "hub_read_devices", "success": not bool(getattr(read_result, "is_error", False))})
    value = _extract_attribute_value(_tool_data(read_result), attribute)
    label = _label(device) or "Device"
    if value in (None, ""):
        message = f"{label} is available, but Hubitat did not expose a current {attribute} value."
        success = False
    else:
        message = f"{label} is {value} {unit}."
        success = True
    return {
        "success": success,
        "route": "mcp-fast",
        "intent": "device-attribute-read",
        "message": message,
        "device_id": str(_device_id(device) or ""),
        "device_label": label,
        "attribute": attribute,
        "value": value,
        "unit": unit,
        "tools_used": tools_used,
        "entity_resolution_request": parse_entity_request(query).as_dict(),
        "answered_by": "deterministic entity reader",
    }


_LOOKUP_PREFIX_RE = re.compile(
    r"^(?:find|locate|search for|look for|where is|where's)\b",
    re.IGNORECASE,
)


def _is_explicit_device_lookup(query: str) -> bool:
    """Return true for identity/location lookups, not state or value questions."""

    return bool(_LOOKUP_PREFIX_RE.match(_normalise(query)))


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


def _lookup_record_score(
    device: dict[str, Any],
    target_phrase: str,
    attribute: str | None = None,
) -> tuple[int, int, int]:
    label = _normalise(_label(device))
    target = _normalise(target_phrase)
    compact_label = re.sub(r"[^a-z0-9]", "", label)
    compact_target = re.sub(r"[^a-z0-9]", "", target)
    exact = int(bool(compact_target) and compact_label == compact_target)
    overlap = len(set(target.split()) & set(label.split()))
    return _device_attribute_support(device, attribute), exact, overlap


def _best_lookup_device(
    payload: Any,
    target_phrase: str,
    attribute: str | None = None,
) -> dict[str, Any] | None:
    records = list(_iter_device_records(payload))
    if not records or not _normalise(target_phrase):
        return None
    ranked = sorted(
        records,
        key=lambda item: _lookup_record_score(item, target_phrase, attribute),
        reverse=True,
    )
    best = ranked[0]
    if _lookup_record_score(best, target_phrase, attribute)[2] == 0:
        return None
    return best


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
    "_apply_automation_recommendation_policy",
    "_executed_tool_names",
    "_has_successful_tool_call",
    "_looks_like_false_evidence_failure",
    "_normalise_history",
    "_uses_conversation_context",
    "install_unified_mcp_agent_orchestrator",
    "should_use_unified_agent",
]

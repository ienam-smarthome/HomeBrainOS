from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from automation_rule_workflow import _normalise, _session_id
from automation_rule_workflow_repair_id_safe import (
    RepairIdSafeWashingRuleMachineWorkflow,
    install_repair_id_safe_rule_machine_workflow,
)
from device_intelligence_index import _attributes, _label, _room_name


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_DIRECT_CONTACT_RULE = re.compile(
    r"^(?:please\s+)?(?:write|create|make|build|draft|prepare)\s+"
    r"(?:me\s+)?(?:a\s+)?(?:rule|automation)\s+to\s+"
    r"(?:(?:send|give)(?:\s+me)?\s+(?:an?\s+)?(?:alert|notification)|"
    r"(?:alert|notify)(?:\s+me)?)\s+when\s+(?:the\s+)?(.+?)\s+"
    r"(?:has\s+been\s+|is\s+)?(?:left\s+)?open"
    r"(?:\s+for\s+(\d{1,3})\s*(seconds?|secs?|minutes?|mins?))?[.!?]*$",
    re.IGNORECASE,
)
_FIND_DEVICE = re.compile(
    r"^(?:please\s+)?(?:find|search(?:\s+for)?|locate|show\s+matches\s+for)\s+"
    r"(?:the\s+)?(?:device\s+)?(.+?)[.!?]*$",
    re.IGNORECASE,
)


def _spoken_name(value: str) -> str:
    value = re.sub(r"[._/\\-]+", " ", str(value or ""))
    return re.sub(r"\s+", " ", value).strip(" .!?")


def parse_direct_contact_rule(query: str) -> dict[str, Any] | None:
    """Parse one narrow, explicit contact-left-open rule family."""

    match = _DIRECT_CONTACT_RULE.fullmatch(str(query or "").strip())
    if not match:
        return None
    requested = _spoken_name(match.group(1))
    if not requested:
        return None

    amount = int(match.group(2) or 2)
    unit = str(match.group(3) or "minutes").lower()
    seconds = amount if unit.startswith(("sec", "s")) else amount * 60
    seconds = max(10, min(24 * 60 * 60, seconds))
    return {"requested_device": requested, "duration_seconds": seconds}


def parse_device_search(query: str) -> str | None:
    match = _FIND_DEVICE.fullmatch(str(query or "").strip())
    if not match:
        return None
    requested = _spoken_name(match.group(1))
    return requested or None


def _has_contact_capability(device: dict[str, Any]) -> bool:
    attributes = _attributes(device)
    if "contact" in {str(key).lower() for key in attributes}:
        return True
    capabilities = device.get("capabilities") or device.get("capability") or []
    if isinstance(capabilities, dict):
        capabilities = list(capabilities)
    if isinstance(capabilities, str):
        capabilities = [capabilities]
    return any("contact" in str(item).lower() for item in capabilities)


def _duration_text(seconds: int) -> str:
    if seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} minute" + ("s" if minutes != 1 else "")
    return f"{seconds} seconds"


def _candidate_message(requested: str, candidates: list[str]) -> str:
    if not candidates:
        return f'I could not find a selected device matching "{requested}".'
    lines = [f'Devices matching "{requested}":']
    lines.extend(f"{index}. {candidate}" for index, candidate in enumerate(candidates, start=1))
    return "\n".join(lines)


async def _find_devices(
    service: RepairIdSafeWashingRuleMachineWorkflow,
    requested: str,
) -> dict[str, Any]:
    exact = None
    candidates: list[str] = []
    try:
        exact, candidates = await service.device_index.exact_device(requested)
    except Exception as exc:
        return {
            "success": False,
            "route": "mcp-device-search",
            "intent": "device-search-error",
            "message": f'Device search failed for "{requested}": {exc}',
            "requested_name": requested,
        }

    if isinstance(exact, dict):
        label = _label(exact) or requested
        device_id = exact.get("id") or exact.get("deviceId")
        room = _room_name(exact)
        descriptor = label
        details = [item for item in (f"ID {device_id}" if device_id else "", room) if item]
        if details:
            descriptor += f" ({', '.join(details)})"
        candidates = [descriptor]

    return {
        "success": bool(candidates),
        "route": "mcp-device-search",
        "intent": "device-search-results" if candidates else "device-search-empty",
        "message": _candidate_message(requested, candidates),
        "requested_name": requested,
        "matched_devices": candidates,
        "match_count": len(candidates),
        "answered_by": "HomeBrain selected-device index",
    }


async def _build_direct_contact_rule(
    service: RepairIdSafeWashingRuleMachineWorkflow,
    request: Any,
    parsed: dict[str, Any],
) -> dict[str, Any]:
    requested = str(parsed["requested_device"])
    exact = None
    candidates: list[str] = []
    error: str | None = None
    for candidate in (requested, _normalise(requested)):
        try:
            exact, candidates = await service.device_index.exact_device(candidate)
        except Exception as exc:
            error = str(exc)
            exact = None
            candidates = []
        if isinstance(exact, dict):
            break

    if not isinstance(exact, dict):
        message = _candidate_message(requested, candidates)
        if candidates:
            message += "\nUse the exact Hubitat label from this list to build the rule."
        else:
            message += " Check that the contact sensor is selected in the MCP device allowlist."
        return {
            "success": False,
            "route": "mcp-rule-intake",
            "intent": "automation-rule-device-not-found",
            "message": message,
            "requested_name": requested,
            "alternatives": candidates,
            "matched_devices": candidates,
            "match_count": len(candidates),
            "technical": {"device_resolution_error": error},
        }

    label = _label(exact) or requested
    if not _has_contact_capability(exact):
        return {
            "success": False,
            "route": "mcp-rule-intake",
            "intent": "automation-rule-capability-blocked",
            "message": f"{label} was found, but it is not verified as a contact sensor, so no rule draft was produced.",
            "requested_name": requested,
            "matched_device": label,
        }

    seconds = int(parsed["duration_seconds"])
    duration = _duration_text(seconds)
    recommendation = {
        "type": "cold-storage-door",
        "title": f"{label} left-open alert",
        "reason": f"Alert when {label} remains open longer than {duration}.",
        "room": _room_name(exact),
        "devices": [label],
        "trigger": f"When {label} contact remains open for {duration}",
        "action": f"Send a high-priority notification that {label} has been left open",
        "safeguard": f"Cancel the pending alert when {label} closes",
        "direct_contact_rule": True,
        "duration_seconds": seconds,
    }
    pending = await service.store.remember(_session_id(request), recommendation)
    answer = await service._build(pending)

    draft = pending.draft or {}
    trigger = draft.get("trigger")
    if isinstance(trigger, dict):
        trigger["duration_seconds"] = seconds
    actions = draft.get("actions")
    if isinstance(actions, list) and actions and isinstance(actions[0], dict):
        actions[0]["message"] = f"{label} has been open for {duration}."
    draft["type"] = "contact-left-open"
    draft["description"] = recommendation["reason"]
    pending.create_args = None
    pending.create_tool = None
    pending.compile_error = None
    tools = pending.discovered_tools or await service._discover_rule_tools(refresh=True)
    create_tool, create_args, compile_error = service._choose_create_tool(tools, draft)
    pending.create_tool = create_tool
    pending.create_args = create_args
    pending.compile_error = compile_error

    answer["rule_draft"] = draft
    answer["write_ready"] = bool(service.write_enabled and create_tool and create_args)
    answer["route"] = "mcp-rule-draft"
    answer["intent"] = "automation-rule-draft"
    answer["message"] = (
        f"Draft ready for **{recommendation['title']}**. It will alert after {duration}. "
        "No rule has been written to Hubitat. Review it, then press Create paused rule."
    )
    answer["direct_rule_intake"] = True
    answer["matched_device"] = {"id": exact.get("id") or exact.get("deviceId"), "label": label}
    return answer


def install_direct_contact_rule_workflow(
    application: Any,
    device_index: Any,
    *,
    ttl_seconds: float = 600.0,
    max_sessions: int = 128,
    write_enabled: bool = True,
    require_paused_create: bool = True,
) -> RepairIdSafeWashingRuleMachineWorkflow:
    service = install_repair_id_safe_rule_machine_workflow(
        application,
        device_index,
        ttl_seconds=ttl_seconds,
        max_sessions=max_sessions,
        write_enabled=write_enabled,
        require_paused_create=require_paused_create,
    )
    original_ask: AskHandler = application.ask

    async def ask_with_direct_contact_rule(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "")
        parsed = parse_direct_contact_rule(query)
        if parsed:
            answer = await _build_direct_contact_rule(service, request, parsed)
            answer.setdefault("version", application.VERSION)
            return answer
        search = parse_device_search(query)
        if search:
            answer = await _find_devices(service, search)
            answer.setdefault("version", application.VERSION)
            return answer
        answer = await original_ask(request)
        pending = await service.store.get(_session_id(request))
        if pending and pending.recommendation.get("direct_contact_rule"):
            message = str(answer.get("message") or "")
            if "fridge" in message.lower():
                label = str((pending.recommendation.get("devices") or ["contact sensor"])[0])
                answer["message"] = re.sub(r"the fridge", label, message, flags=re.IGNORECASE)
        return answer

    application.ask = ask_with_direct_contact_rule
    application.automation_rule_workflow = service
    return service


__all__ = [
    "install_direct_contact_rule_workflow",
    "parse_device_search",
    "parse_direct_contact_rule",
]

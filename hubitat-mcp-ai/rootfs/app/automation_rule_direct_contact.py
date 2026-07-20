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
    r"(?:alert|notify)(?:\s+me)?\s+when\s+(?:the\s+)?(.+?)\s+"
    r"(?:has\s+been\s+|is\s+)?(?:left\s+)?open"
    r"(?:\s+for\s+(\d{1,3})\s*(seconds?|secs?|minutes?|mins?))?[.!?]*$",
    re.IGNORECASE,
)


def parse_direct_contact_rule(query: str) -> dict[str, Any] | None:
    """Parse a complete, explicit contact-left-open rule request.

    This intentionally recognises one narrow, safe rule family. Other automation
    requests continue through the existing recommendation and review workflow.
    Punctuation inside spoken device names is treated as a separator, so
    ``front.door`` and ``front door`` resolve identically.
    """

    match = _DIRECT_CONTACT_RULE.fullmatch(str(query or "").strip())
    if not match:
        return None
    requested = re.sub(r"[._/\\-]+", " ", match.group(1))
    requested = re.sub(r"\s+", " ", requested).strip(" .!?")
    if not requested:
        return None

    amount = int(match.group(2) or 2)
    unit = str(match.group(3) or "minutes").lower()
    seconds = amount if unit.startswith(("sec", "s")) else amount * 60
    seconds = max(10, min(24 * 60 * 60, seconds))
    return {"requested_device": requested, "duration_seconds": seconds}


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


async def _build_direct_contact_rule(
    service: RepairIdSafeWashingRuleMachineWorkflow,
    request: Any,
    parsed: dict[str, Any],
) -> dict[str, Any]:
    requested = str(parsed["requested_device"])
    exact = None
    details: dict[str, Any] = {}
    for candidate in (requested, _normalise(requested)):
        try:
            exact, details = await service.device_index.exact_device(candidate)
        except Exception as exc:
            details = {"error": str(exc)}
            exact = None
        if isinstance(exact, dict):
            break

    if not isinstance(exact, dict):
        return {
            "success": False,
            "route": "mcp-rule-intake",
            "intent": "automation-rule-device-not-found",
            "message": f'I could not find one exact selected device matching "{requested}". Use its exact Hubitat label.',
            "requested_name": requested,
            "technical": {"device_resolution": details},
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
        parsed = parse_direct_contact_rule(str(getattr(request, "query", "") or ""))
        if parsed:
            answer = await _build_direct_contact_rule(service, request, parsed)
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


__all__ = ["install_direct_contact_rule_workflow", "parse_direct_contact_rule"]

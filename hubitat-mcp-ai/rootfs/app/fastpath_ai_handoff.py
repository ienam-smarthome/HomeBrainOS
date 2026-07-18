from __future__ import annotations

import asyncio
import re
from typing import Any, Awaitable, Callable

from control_language import canonicalise_basic_control
from fast_fallback_speech import normalise_spoken_device_name


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_HANDOFF_INTENTS = {
    "fallback-ambiguous-device",
    "fallback-device-not-found",
}


def _control_executed(answer: dict[str, Any]) -> bool:
    for item in answer.get("tools_used") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").lower()
        if "command" in name and item.get("success") is not False:
            return True
    return str(answer.get("intent") or "") in {
        "fallback-device-control-confirmed",
        "fallback-device-group-control-confirmed",
    }


def _number_suffix(value: str) -> str | None:
    match = re.search(r"(?:^|\s)(\d+)$", normalise_spoken_device_name(value))
    return match.group(1) if match else None


def _opposite_humidity_name(requested: str, candidate: str) -> bool:
    requested_norm = normalise_spoken_device_name(requested)
    candidate_norm = normalise_spoken_device_name(candidate)
    requested_de = "dehumidifier" in requested_norm
    candidate_de = "dehumidifier" in candidate_norm
    requested_hum = "humidifier" in requested_norm
    candidate_hum = "humidifier" in candidate_norm
    return requested_hum and candidate_hum and requested_de != candidate_de


def _confirmation_candidates(requested: str, alternatives: list[str]) -> list[str]:
    candidates = list(dict.fromkeys(item for item in alternatives if item))[:5]
    requested_number = _number_suffix(requested)
    if requested_number:
        numbered = [item for item in candidates if _number_suffix(item) == requested_number]
        if len(numbered) == 1:
            return numbered
    return candidates


def _clarification_message(
    requested: str,
    alternatives: list[str],
    *,
    action: str | None = None,
) -> str:
    candidates = _confirmation_candidates(requested, alternatives)
    if not candidates:
        return f'I could not find a device matching "{requested}". What is its exact Hubitat label?'
    if len(candidates) == 1:
        if action in {"on", "off"}:
            return f"Did you mean {candidates[0]}? Reply Yes to turn it {action}, or No to cancel."
        return f"Did you mean {candidates[0]}? Reply Yes to confirm, or No to cancel."
    lines = ["Which device did you mean?"]
    lines.extend(f"{index}. {label}" for index, label in enumerate(candidates, start=1))
    lines.append("Reply with the number or exact device name. Reply No to cancel.")
    return "\n".join(lines)


def _confirmation_payload(
    requested: str,
    alternatives: list[str],
    action: str | None,
) -> dict[str, Any] | None:
    candidates = _confirmation_candidates(requested, alternatives)
    if action not in {"on", "off"} or not candidates:
        return None
    return {
        "action": action,
        "requested_name": requested,
        "candidates": candidates,
    }


def install_fastpath_ai_handoff(application: Any) -> AskHandler:
    """Send unresolved exact on/off matches to the natural Ollama MCP planner."""
    original_ask = application.ask

    async def ask_with_handoff(request: Any) -> dict[str, Any]:
        answer = await original_ask(request)
        intent = str(answer.get("intent") or "")
        if intent not in _HANDOFF_INTENTS:
            return answer

        control = canonicalise_basic_control(str(request.query or ""))
        requested_name = str(
            answer.get("requested_name")
            or (control.target if control else request.query)
        ).strip()
        action = control.action if control else None
        alternatives = [
            str(item).strip()
            for item in (answer.get("alternatives") or [])
            if str(item).strip()
        ]
        confirmation = _confirmation_payload(requested_name, alternatives, action)

        # One uniquely numbered/labelled suggestion should be confirmed locally,
        # not sent through a long Ollama planning round. No command is executed here.
        if confirmation and len(confirmation["candidates"]) == 1:
            clarified = dict(answer)
            clarified.update(
                {
                    "success": False,
                    "route": "mcp-fast",
                    "intent": "fallback-device-confirmation-required",
                    "message": _clarification_message(
                        requested_name,
                        alternatives,
                        action=action,
                    ),
                    "confirmation_required": True,
                    "confirmation": confirmation,
                    "alternatives": confirmation["candidates"],
                }
            )
            return clarified

        # Humidifier and dehumidifier are opposite appliance meanings. A speech
        # transcript that loses the "de" prefix must never silently operate the
        # opposite device, even when the number strongly suggests one candidate.
        if alternatives and any(
            _opposite_humidity_name(requested_name, item) for item in alternatives
        ):
            clarified = dict(answer)
            clarified.update(
                {
                    "success": False,
                    "route": "mcp-fast",
                    "intent": "fallback-device-confirmation-required",
                    "message": _clarification_message(
                        requested_name,
                        alternatives,
                        action=action,
                    ),
                    "confirmation_required": True,
                }
            )
            if confirmation:
                clarified["confirmation"] = confirmation
                clarified["alternatives"] = confirmation["candidates"]
            return clarified

        history = [
            {"role": item.role, "content": item.content}
            for item in request.history[-6:]
        ]
        closest = answer.get("message") or "The deterministic matcher found no exact match."
        planner_query = (
            f"{request.query.strip()}\n\n"
            "Resolve this as a smart-home device-control request using live Hubitat MCP tools. "
            "Treat spoken number words and digits as equivalent. Do not explain what the listed "
            "devices do and do not mention unrelated candidates. If one device is clearly meant, "
            "execute the requested command and verify its state. If ambiguity remains, control "
            "nothing and ask exactly one short clarification question. Humidifier and "
            "dehumidifier are not interchangeable. "
            f"Matcher context: {closest}"
        )

        timeout = max(
            30.0,
            min(
                75.0,
                float(application.OPTIONS.get("ollama_agent_timeout_seconds") or 75),
            ),
        )
        try:
            natural = await asyncio.wait_for(
                application.ollama.answer_with_planner(planner_query, history),
                timeout=timeout,
            )
            natural["route"] = "ollama+mcp"
            natural["handoff_from"] = "mcp-fast"
            natural["fast_match_intent"] = intent
            natural["fast_match_message"] = answer.get("message")
            natural.setdefault("version", application.VERSION)
            if alternatives and not _control_executed(natural):
                candidates = _confirmation_candidates(requested_name, alternatives)
                natural.update(
                    {
                        "success": False,
                        "intent": "ollama-device-clarification",
                        "message": _clarification_message(
                            requested_name,
                            candidates,
                            action=action,
                        ),
                        "confirmation_required": True,
                        "alternatives": candidates,
                    }
                )
                confirmation = _confirmation_payload(requested_name, candidates, action)
                if confirmation:
                    natural["confirmation"] = confirmation
            return natural
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            fallback = dict(answer)
            candidates = _confirmation_candidates(requested_name, alternatives)
            fallback["ai_handoff_attempted"] = True
            fallback["ai_handoff_error"] = str(exc)
            fallback["message"] = _clarification_message(
                requested_name,
                candidates,
                action=action,
            )
            fallback["confirmation_required"] = True
            fallback["alternatives"] = candidates
            confirmation = _confirmation_payload(requested_name, candidates, action)
            if confirmation:
                fallback["confirmation"] = confirmation
            return fallback

    application.ask = ask_with_handoff
    return ask_with_handoff


__all__ = ["install_fastpath_ai_handoff"]

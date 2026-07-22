from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from control_agent_gate import is_contextual_device_control, is_exact_fast_control
from control_agent_intent import is_control_candidate
from contextual_control import is_other_device_control
from device_health_fast_route import is_attention_query, is_device_health_query
from entity_request_policy import parse_entity_request
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
    "_apply_device_tool_policy",
    "_apply_automation_recommendation_policy",
    "_executed_tool_names",
    "_has_successful_tool_call",
    "_looks_like_false_evidence_failure",
    "_normalise_history",
    "_uses_conversation_context",
    "install_unified_mcp_agent_orchestrator",
    "should_use_unified_agent",
]

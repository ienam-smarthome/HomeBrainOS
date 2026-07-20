from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

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
    broad_check = getattr(agent, "_is_broad_device_inventory_request", None)
    if callable(broad_check) and bool(broad_check(query)):
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
                "message": (
                    "The unified Hubitat MCP agent could not complete this request. "
                    "It was not redirected to the read-only evidence planner. "
                    f"Technical error: {error}"
                ),
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
    "_executed_tool_names",
    "_normalise_history",
    "_uses_conversation_context",
    "install_unified_mcp_agent_orchestrator",
    "should_use_unified_agent",
]

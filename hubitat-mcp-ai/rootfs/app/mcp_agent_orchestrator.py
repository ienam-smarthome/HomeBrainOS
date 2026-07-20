from __future__ import annotations

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


def should_use_unified_agent(query: str) -> bool:
    """Use AI for every substantive non-fast request.

    Exact deterministic routes remain available for latency and offline operation.
    Short protocol replies remain with the confirmation/workflow handlers because
    they refer to pending server-side state rather than a new natural-language task.
    """

    q = _normalise(query)
    if not q or q in _PROTOCOL_FOLLOWUPS:
        return False
    return classify_query(q).route != "mcp-fast"


def install_unified_mcp_agent_orchestrator(application: Any) -> None:
    """Install one AI-first decision point above the legacy route stack.

    Substantive requests remain in the unified agent. A planner failure is returned
    transparently instead of being silently rerouted to the restricted read-only
    evidence planner. Exact fast paths and pending confirmation replies still use the
    existing deterministic handlers.
    """

    original_ask: AskHandler = application.ask

    async def ask_with_unified_agent(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "")
        if not should_use_unified_agent(query):
            return await original_ask(request)

        history = _normalise_history(getattr(request, "history", None))
        try:
            planner = getattr(application.ollama, "answer_with_planner", None)
            if callable(planner):
                answer = await planner(query, history)
            else:
                answer = await application.ollama.answer(query, history)
            result = dict(answer)
            result.setdefault("success", True)
            result["agent_orchestrator"] = "unified-mcp-ai-first"
            result["legacy_fallback_used"] = False
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
    "_normalise_history",
    "install_unified_mcp_agent_orchestrator",
    "should_use_unified_agent",
]

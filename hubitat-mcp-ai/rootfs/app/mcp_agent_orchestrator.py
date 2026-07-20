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

    The wrapped legacy stack is now an offline/timeout fallback. It is no longer the
    primary natural-language interpreter. Safety remains in MCP tool execution and
    the existing confirmation and verification layers.
    """

    original_ask: AskHandler = application.ask

    async def ask_with_unified_agent(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "")
        if not should_use_unified_agent(query):
            return await original_ask(request)

        history = list(getattr(request, "history", None) or [])
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
            fallback = dict(await original_ask(request))
            fallback["agent_orchestrator"] = "unified-mcp-ai-first"
            fallback["legacy_fallback_used"] = True
            fallback["unified_agent_error"] = str(exc) or exc.__class__.__name__
            fallback.setdefault("version", application.VERSION)
            technical = fallback.get("technical")
            if not isinstance(technical, dict):
                technical = {}
            technical["unified_agent"] = {
                "attempted": True,
                "fallback": True,
                "error": fallback["unified_agent_error"],
            }
            fallback["technical"] = technical
            return fallback

    application.ask = ask_with_unified_agent


__all__ = ["install_unified_mcp_agent_orchestrator", "should_use_unified_agent"]

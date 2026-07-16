from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_HANDOFF_INTENTS = {
    "fallback-ambiguous-device",
    "fallback-device-not-found",
}


def install_fastpath_ai_handoff(application: Any) -> AskHandler:
    """Send unresolved exact on/off matches to the natural Ollama MCP planner."""
    original_ask = application.ask

    async def ask_with_handoff(request: Any) -> dict[str, Any]:
        answer = await original_ask(request)
        intent = str(answer.get("intent") or "")
        if intent not in _HANDOFF_INTENTS:
            return answer

        history = [
            {"role": item.role, "content": item.content}
            for item in request.history[-6:]
        ]
        closest = answer.get("message") or "The deterministic matcher found no exact match."
        planner_query = (
            f"{request.query.strip()}\n\n"
            "The deterministic exact device matcher could not safely resolve this command. "
            "Use the live Hubitat MCP tools to identify the intended device from labels, room, "
            "device type and aliases. If one match is clearly intended, execute the requested "
            "command and verify the resulting state. If more than one interpretation remains "
            "plausible, do not control anything; ask one concise clarification question. "
            f"Matcher context: {closest}"
        )

        timeout = max(
            30.0,
            min(
                90.0,
                float(application.OPTIONS.get("ollama_agent_timeout_seconds") or 90),
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
            return natural
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            fallback = dict(answer)
            fallback["ai_handoff_attempted"] = True
            fallback["ai_handoff_error"] = str(exc)
            fallback["message"] = (
                str(answer.get("message") or "I could not resolve that device.")
                + "\n\nThe natural AI device-resolution attempt also failed: "
                + str(exc)
            )
            return fallback

    application.ask = ask_with_handoff
    return ask_with_handoff


__all__ = ["install_fastpath_ai_handoff"]

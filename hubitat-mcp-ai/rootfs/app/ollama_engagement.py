from __future__ import annotations

import asyncio
import re
from typing import Any, Awaitable, Callable

from presenter import display_payload, safe_debug


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_HELP_QUERY = re.compile(
    r"^(?:what\s+can|how\s+does)\s+(?:ollama|the\s+ai|ai)\s+"
    r"(?:answer|help(?:\s+with)?|do)[?.!]*$"
    r"|^(?:show|give\s+me)\s+(?:the\s+)?(?:ollama|ai)\s+"
    r"(?:question\s+guide|examples|capabilities)[?.!]*$",
    re.IGNORECASE,
)
_AI_INSIGHT_QUERY = re.compile(
    r"^(?:what\s+looks\s+unusual|what\s+should\s+i\s+know|"
    r"give\s+me\s+(?:an\s+)?(?:ai\s+)?(?:home\s+)?insight|"
    r"analyse\s+(?:my\s+)?home|analyze\s+(?:my\s+)?home|"
    r"summarise\s+(?:my\s+)?home|summarize\s+(?:my\s+)?home)"
    r"(?:\s+(?:at\s+home|about\s+(?:my\s+)?home|right\s+now|now))?[?.!]*$",
    re.IGNORECASE,
)
_FORCE_OLLAMA = re.compile(
    r"^(?:ask|use)\s+(?:ollama|the\s+ai|ai)\s*(?:to|:|-)?\s*(.+)$",
    re.IGNORECASE,
)


def _history(request: Any) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for item in list(getattr(request, "history", []) or [])[-8:]:
        if isinstance(item, dict):
            role = item.get("role")
            content = item.get("content")
        else:
            role = getattr(item, "role", None)
            content = getattr(item, "content", None)
        if role in {"user", "assistant"} and content:
            values.append({"role": str(role), "content": str(content)})
    return values


def ollama_help(application: Any) -> dict[str, Any]:
    model = str(application.OPTIONS.get("ollama_model") or "Configured local model")
    examples = [
        ("Explain", "Why are three lights on, and is anything unusual?"),
        ("Compare", "Compare the bedroom temperatures and explain the difference."),
        ("Diagnose", "Why might this device command be failing?"),
        ("Recommend", "Suggest one useful automation for the devices I have."),
        ("Multi-step", "Find active motion and tell me which nearby lights are off."),
        ("Forced AI", "Start any request with ‘Ask Ollama:’ to require an AI-written answer."),
    ]
    return {
        "success": True,
        "route": "system",
        "intent": "ollama-question-guide",
        "message": (
            "Ollama handles explanations, comparisons, diagnosis, recommendations, "
            "multi-step questions and natural summaries. Exact lists and simple on/off "
            "commands normally stay on the faster deterministic Hubitat route."
        ),
        "model": model,
        "display": display_payload(
            "ollama-question-guide",
            "What Ollama answers",
            subtitle=f"Local model: {model}",
            metrics=[
                {"label": "Exact live reads", "value": "Hubitat fast", "icon": "⚡"},
                {"label": "Natural summaries", "value": "Ollama + MCP", "icon": "🤖"},
                {"label": "Reasoning", "value": "Ollama planner", "icon": "🧠"},
            ],
            items=[
                {
                    "icon": "✨",
                    "title": title,
                    "value": "Try it",
                    "subtitle": example,
                }
                for title, example in examples
            ],
            note=(
                "Ollama is never treated as the source of device state. It interprets and "
                "phrases live evidence returned by Hubitat MCP."
            ),
        ),
    }


def install_ollama_engagement(
    application: Any,
    home_snapshot: Any,
) -> AskHandler:
    """Add visible AI help, AI home insights and an explicit Ollama override."""
    original_ask: AskHandler = application.ask

    async def ask_with_ollama_engagement(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()

        if _HELP_QUERY.match(query):
            answer = ollama_help(application)
            answer.setdefault("version", application.VERSION)
            return answer

        if _AI_INSIGHT_QUERY.match(query):
            answer = await home_snapshot.answer(query)
            answer["engagement_mode"] = "ai-home-insight"
            answer.setdefault("version", application.VERSION)
            return answer

        forced = _FORCE_OLLAMA.match(query)
        if not forced:
            return await original_ask(request)

        clean_query = forced.group(1).strip()
        if not clean_query:
            return ollama_help(application)

        timeout = max(
            30.0,
            min(
                180.0,
                float(application.OPTIONS.get("ollama_agent_timeout_seconds") or 120),
            ),
        )
        try:
            answer = await asyncio.wait_for(
                application.ollama.answer(clean_query, _history(request)),
                timeout=timeout,
            )
            answer = dict(answer)
            answer["forced_ollama"] = True
            answer["original_query"] = query
            answer["resolved_query"] = clean_query
            answer.setdefault("version", application.VERSION)
            return answer
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            original_query = query
            request.query = clean_query
            try:
                answer = await original_ask(request)
            finally:
                request.query = original_query
            answer = dict(answer)
            answer["forced_ollama"] = True
            answer["ollama_force_error"] = str(exc)
            answer["fallback_reason"] = (
                "The explicitly requested Ollama answer failed, so HomeBrain used the "
                "authoritative Hubitat route instead."
            )
            answer["technical"] = safe_debug(
                {
                    "ollama_force_error": str(exc),
                    "resolved_query": clean_query,
                    "fallback": answer.get("technical"),
                }
            )
            return answer

    application.ask = ask_with_ollama_engagement
    application.ollama_help = lambda: ollama_help(application)
    return ask_with_ollama_engagement


__all__ = ["install_ollama_engagement", "ollama_help"]

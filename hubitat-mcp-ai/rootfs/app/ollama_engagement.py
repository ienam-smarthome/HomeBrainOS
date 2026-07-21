from __future__ import annotations

import asyncio
import re
from typing import Any, Awaitable, Callable

from presenter import display_payload, safe_debug
from temperature_insight import TemperatureInsightService


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_HELP_QUERY = re.compile(
    r"^(?:what\s+can|how\s+does)\s+(?:ollama|the\s+ai|ai)\s+"
    r"(?:answer|help(?:\s+with)?|do)[?.!]*$"
    r"|^(?:show|give\s+me)\s+(?:the\s+)?(?:ollama|ai)\s+"
    r"(?:question\s+guide|examples|capabilities)[?.!]*$",
    re.IGNORECASE,
)
_AI_INSIGHT_QUERY = re.compile(
    r"^(?:"
    r"what\s+looks\s+unusual(?:\s+at\s+home)?|"
    r"what\s+should\s+i\s+know(?:\s+about\s+(?:my\s+)?home)?|"
    r"give\s+me\s+(?:an\s+)?(?:ai\s+)?(?:home\s+)?insight|"
    r"analyse\s+(?:my\s+)?home|analyze\s+(?:my\s+)?home|"
    r"summarise\s+(?:my\s+)?home|summarize\s+(?:my\s+)?home"
    r")(?:\s+(?:right\s+now|now))?[?.!]*$",
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
            "multi-step questions and natural summaries. Common analytical reads, such "
            "as bedroom temperature comparison, now use bounded live evidence instead "
            "of waiting for the general MCP planner. Exact lists and simple on/off "
            "commands stay on the faster deterministic Hubitat route."
        ),
        "model": model,
        "display": display_payload(
            "ollama-question-guide",
            "What Ollama answers",
            subtitle=f"Local model: {model}",
            metrics=[
                {"label": "Exact live reads", "value": "Hubitat fast", "icon": "⚡"},
                {"label": "Bounded analysis", "value": "Ollama + MCP", "icon": "🤖"},
                {"label": "Open reasoning", "value": "Ollama planner", "icon": "🧠"},
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


def _decorate_snapshot_ai(
    application: Any,
    home_snapshot: Any,
    answer: dict[str, Any],
) -> dict[str, Any]:
    """Make it explicit whether the snapshot wording came from Ollama."""
    result = dict(answer)
    ai_used = result.get("route") == "ollama+snapshot"
    ai_attempted = bool(
        getattr(home_snapshot, "ai_enabled", False)
        and result.get("success")
    )
    result["ai_attempted"] = ai_attempted
    result["ai_used"] = ai_used
    result["ai_status"] = (
        "used" if ai_used else "fallback" if ai_attempted else "disabled"
    )
    result["answered_by"] = "Ollama" if ai_used else "Home Snapshot"
    result["evidence_source"] = "Hubitat MCP"

    if ai_attempted and not ai_used:
        result["route"] = "mcp-snapshot-ai-fallback"
        result["model"] = str(
            application.OPTIONS.get("ollama_model") or result.get("model") or ""
        ) or None
        display = result.get("display")
        if isinstance(display, dict):
            display = dict(display)
            note = str(display.get("note") or "").strip()
            fallback_note = (
                "Ollama wording was attempted but did not finish, so this answer was "
                "written by the deterministic Home Snapshot from live Hubitat data."
            )
            display["note"] = f"{note} {fallback_note}".strip()
            result["display"] = display
    return result


def install_ollama_engagement(
    application: Any,
    home_snapshot: Any,
) -> AskHandler:
    """Add visible AI help, bounded insights and an explicit Ollama override."""
    original_ask: AskHandler = application.ask

    quick_timeout = max(
        15.0,
        min(
            60.0,
            float(
                application.OPTIONS.get("ollama_quick_insight_timeout_seconds")
                or 25
            ),
        ),
    )
    # Existing installations may retain the old 12-second snapshot value. A local
    # 9B model often needs longer after keep-alive expiry, so bounded insight routes
    # receive the new quick-analysis allowance without extending the general planner.
    home_snapshot.ai_timeout_seconds = max(
        float(getattr(home_snapshot, "ai_timeout_seconds", 0) or 0),
        quick_timeout,
    )
    device_index = getattr(application, "device_index", None) or getattr(
        home_snapshot,
        "device_index",
        None,
    )
    temperature_insight = (
        TemperatureInsightService(
            application,
            device_index,
            timeout_seconds=quick_timeout,
        )
        if device_index is not None
        else None
    )

    async def ask_with_ollama_engagement(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()

        if _HELP_QUERY.match(query):
            answer = ollama_help(application)
            answer.setdefault("version", application.VERSION)
            return answer

        if temperature_insight is not None and temperature_insight.matches(query):
            answer = await temperature_insight.answer(query)
            answer["engagement_mode"] = "bounded-temperature-insight"
            answer.setdefault("version", application.VERSION)
            return answer

        if _AI_INSIGHT_QUERY.match(query):
            answer = await home_snapshot.answer(query)
            answer = _decorate_snapshot_ai(application, home_snapshot, answer)
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
            answer["ai_attempted"] = True
            answer["ai_used"] = True
            answer["ai_status"] = "used"
            answer["answered_by"] = "Ollama"
            answer["evidence_source"] = "Hubitat MCP"
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
            answer["ai_attempted"] = True
            answer["ai_used"] = False
            answer["ai_status"] = "fallback"
            answer["answered_by"] = "HomeBrain fallback"
            answer["evidence_source"] = "Hubitat MCP"
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
    application.temperature_insight = temperature_insight
    return ask_with_ollama_engagement


def install_ollama_help_terminal_route(application: Any) -> AskHandler:
    """Keep the static AI question guide outside every model-driven wrapper."""

    original_ask: AskHandler = application.ask

    async def ask_with_terminal_ollama_help(request: Any) -> dict[str, Any]:
        query = str(getattr(request, "query", "") or "").strip()
        if not _HELP_QUERY.match(query):
            return await original_ask(request)

        answer = dict(ollama_help(application))
        answer.setdefault("version", application.VERSION)
        answer["route"] = "system"
        answer["model"] = None
        answer["answered_by"] = "HomeBrain AI question guide"
        return answer

    application.ask = ask_with_terminal_ollama_help
    return original_ask


__all__ = [
    "_AI_INSIGHT_QUERY",
    "_FORCE_OLLAMA",
    "_HELP_QUERY",
    "_decorate_snapshot_ai",
    "install_ollama_engagement",
    "install_ollama_help_terminal_route",
    "ollama_help",
]

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from presenter import display_payload, safe_debug
from routing_policy import classify_query
from semantic_read_intent import SemanticReadIntentClassifier


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


def _history_field(item: Any, name: str) -> str:
    if isinstance(item, dict):
        return str(item.get(name) or "")
    return str(getattr(item, name, "") or "")


def install_semantic_read_pipeline(
    application: Any,
    executor: Any,
    *,
    timeout_seconds: float = 5.0,
    cache_ttl_seconds: float = 300.0,
) -> SemanticReadIntentClassifier:
    """Install semantic interpretation only for the semantic-read route.

    Exact fast reads and every control route bypass the classifier entirely. Once a
    question has been validated as a supported metric comparison, it remains on the
    deterministic MCP executor. An evidence error is reported directly and is never
    handed to Cloud to estimate or invent a numeric answer.
    """

    original_ask: AskHandler = application.ask
    classifier = SemanticReadIntentClassifier(
        application,
        timeout_seconds=timeout_seconds,
        cache_ttl_seconds=cache_ttl_seconds,
    )

    async def semantic_ask(request: Any) -> dict[str, Any]:
        query = str(request.query or "").strip()
        if not application.option_bool("semantic_intent_enabled", True):
            return await original_ask(request)
        if classify_query(query).route != "semantic-read":
            return await original_ask(request)

        history = [
            {
                "role": _history_field(item, "role"),
                "content": _history_field(item, "content"),
            }
            for item in list(getattr(request, "history", None) or [])[-4:]
        ]
        intent, diagnostics = await classifier.classify(query, history)
        if intent is None:
            # The semantic gate is intentionally broad. Unsupported analytical reads
            # may still use the normal planner, but validated comparisons may not.
            return await original_ask(request)

        try:
            answer = dict(await executor.execute(intent, query=query))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error = str(exc).strip() or type(exc).__name__
            model = diagnostics.get("ai_model")
            metric = intent.metric.replace("_", " ")
            answer = {
                "success": False,
                "message": (
                    f"I understood this as a {metric} comparison, but the live Hubitat "
                    "evidence request failed. No Cloud estimate was used."
                ),
                "intent": f"semantic-{intent.metric}-evidence-error",
                "route": "semantic+mcp",
                "semantic_intent_attempted": True,
                "semantic_intent_error": error,
                "semantic_intent": intent.response_dict(),
                "semantic_classifier": diagnostics,
                "intent_model": model,
                "answered_by": "Local AI intent + deterministic Hubitat MCP",
                "display": display_payload(
                    "semantic-read-error",
                    "Live comparison unavailable",
                    subtitle="Hubitat evidence request failed",
                    metrics=[
                        {"label": "Metric", "value": metric.title(), "icon": "📊"},
                        {"label": "Cloud estimate", "value": "Not used", "icon": "🛡️"},
                    ],
                    note=(
                        "The read-only intent was understood, but deterministic MCP evidence "
                        "could not be completed. Technical details contain the exact failure."
                    ),
                ),
                "technical": safe_debug(
                    {
                        "query": query,
                        "semantic_intent": intent.response_dict(),
                        "semantic_classifier": diagnostics,
                        "evidence_error": error,
                        "cloud_fallback_blocked": True,
                    }
                ),
            }
            if model:
                answer["model"] = model
                answer["ai_provider"] = "Local Ollama intent classifier"
            return answer

        model = diagnostics.get("ai_model")
        answer.update(
            {
                "route": "semantic+mcp",
                "semantic_intent": intent.response_dict(),
                "semantic_classifier": diagnostics,
                "intent_model": model,
                "answered_by": "Local AI intent + deterministic Hubitat MCP",
            }
        )
        if model:
            # Reuse the existing model/provider badges and request-trace field while
            # making clear that this model classified the intent, not the live values.
            answer["model"] = model
            answer["ai_provider"] = "Local Ollama intent classifier"
        return answer

    application.ask = semantic_ask
    return classifier


__all__ = ["install_semantic_read_pipeline"]

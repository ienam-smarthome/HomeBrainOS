from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from routing_policy import classify_query
from semantic_read_intent import SemanticReadIntentClassifier


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


def install_semantic_read_pipeline(
    application: Any,
    executor: Any,
    *,
    timeout_seconds: float = 5.0,
    cache_ttl_seconds: float = 300.0,
) -> SemanticReadIntentClassifier:
    """Install semantic interpretation only for the semantic-read route.

    Exact fast reads and every control route bypass the classifier entirely. This
    keeps established shortcuts fast and prevents an analytical model from entering
    the command path.
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
                "role": str(item.role or ""),
                "content": str(item.content or ""),
            }
            for item in request.history[-4:]
        ]
        intent, diagnostics = await classifier.classify(query, history)
        if intent is None:
            return await original_ask(request)

        try:
            answer = dict(await executor.execute(intent, query=query))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            fallback = dict(await original_ask(request))
            fallback["semantic_intent_attempted"] = True
            fallback["semantic_intent_error"] = str(exc).strip() or type(exc).__name__
            fallback["semantic_classifier"] = diagnostics
            return fallback

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

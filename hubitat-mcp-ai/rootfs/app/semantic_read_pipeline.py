from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Awaitable, Callable

import semantic_read_intent as semantic_intent_module
from presenter import display_payload, safe_debug
from routing_policy import classify_query
from semantic_read_intent import SemanticReadIntentClassifier


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]


def _history_field(item: Any, name: str) -> str:
    if isinstance(item, dict):
        return str(item.get(name) or "")
    return str(getattr(item, name, "") or "")


def _semantic_model_candidates(
    classifier: SemanticReadIntentClassifier,
) -> list[tuple[str, str, float]]:
    """Return bounded local then Cloud candidates for semantic interpretation.

    Semantic-read classification previously hard-coded the local planner model. That
    made the whole route fail before MCP evidence collection whenever the Ollama PC
    was offline, even though the direct Ollama Cloud transport was configured. Keep
    local classification first to conserve Cloud usage, but bound its connection wait
    and immediately retry the configured Cloud model through the hybrid HTTP client.
    """

    application = classifier.application
    agent = application.ollama
    values: list[tuple[str, str, float]] = []
    seen: set[str] = set()

    local = str(
        getattr(agent, "planner_model", "")
        or getattr(agent, "local_fallback_model", "")
        or getattr(agent, "model", "")
    ).strip()
    if local:
        seen.add(local.lower())
        values.append(
            (
                local,
                "Local Ollama semantic classifier",
                min(classifier.timeout_seconds, 2.5),
            )
        )

    cloud = str(getattr(agent, "cloud_model", "") or "").strip()
    cloud_enabled = bool(getattr(agent, "cloud_enabled", False))
    if (
        cloud_enabled
        and cloud
        and cloud.lower() not in seen
        and application.option_bool("semantic_intent_cloud_fallback_enabled", True)
    ):
        options = getattr(application, "OPTIONS", {})
        options = options if isinstance(options, dict) else {}
        timeout = float(
            options.get("semantic_intent_cloud_timeout_seconds")
            or options.get("ollama_cloud_timeout_seconds")
            or 12
        )
        values.append(
            (
                cloud,
                "Ollama Cloud semantic classifier",
                max(5.0, min(40.0, timeout)),
            )
        )

    return values


async def _classify_semantic_with_model(
    classifier: SemanticReadIntentClassifier,
    *,
    model: str,
    provider: str,
    timeout: float,
    query: str,
    history: list[dict[str, str]],
) -> tuple[Any, dict[str, Any]]:
    agent = classifier.application.ollama
    client = getattr(agent, "_http", None)
    post = getattr(client, "post", None)
    if not callable(post):
        raise RuntimeError("Ollama HTTP client is unavailable")

    context_lines: list[str] = []
    for item in history[-4:]:
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            context_lines.append(f"{role}: {content[:300]}")
    context = "\n".join(context_lines) or "None"

    system = (
        "/no_think\n"
        "You are a semantic intent classifier for a smart-home assistant. "
        "Classify only read-only metric comparisons or rankings. Never execute a command, "
        "never choose a device to control, and return unsupported for any write/control request. "
        "Map watts, electricity draw, load and current consumption to power; warmth/hot/cold "
        "to temperature; damp/dry/moist to humidity; charge to battery; lux/brightness to "
        "illuminance; and kWh/energy totals to energy. Use max for most/highest/hottest, min for "
        "least/lowest/coldest, and rank when the user asks for a list or top N. Use group_by room "
        "when comparing rooms, otherwise device. Return JSON matching the supplied schema only."
    )
    user = f"Recent conversation:\n{context}\n\nCurrent question:\n{query.strip()}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "think": False,
        "format": semantic_intent_module._INTENT_SCHEMA,
        "keep_alive": str(getattr(agent, "keep_alive", "30m") or "30m"),
        "options": {
            "num_ctx": 1024,
            "num_predict": 160,
            "temperature": 0,
        },
    }
    response = await post(
        f"{str(agent.base_url).rstrip('/')}/api/chat",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError(f"{provider} returned a non-object semantic response")
    if str(body.get("done_reason") or "").lower() == "length":
        raise RuntimeError(f"{provider} semantic response was truncated")

    message = body.get("message") or {}
    content = str(message.get("content") or "").strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I | re.S).strip()
    decoded = json.loads(content)
    intent = classifier.validate_payload(decoded)
    actual_provider = provider
    provider_reader = getattr(client, "last_provider", None)
    if callable(provider_reader):
        actual_provider = str(provider_reader(provider) or provider)
    return intent, {
        "ai_success": intent is not None,
        "ai_model": model,
        "ai_provider": actual_provider,
    }


def _install_semantic_cloud_failover() -> None:
    if getattr(SemanticReadIntentClassifier, "_direct_cloud_failover_installed", False):
        return

    async def classify_with_failover(
        self: SemanticReadIntentClassifier,
        query: str,
        history: list[dict[str, str]],
    ) -> tuple[Any, dict[str, Any]]:
        attempts: list[dict[str, Any]] = []
        last_error: Exception | None = None
        unsupported_details: dict[str, Any] | None = None

        for model, provider, timeout in _semantic_model_candidates(self):
            try:
                intent, details = await _classify_semantic_with_model(
                    self,
                    model=model,
                    provider=provider,
                    timeout=timeout,
                    query=query,
                    history=history,
                )
                attempt = {
                    "model": model,
                    "provider": details.get("ai_provider") or provider,
                    "success": intent is not None,
                }
                attempts.append(attempt)
                details["ai_attempts"] = list(attempts)
                if intent is not None:
                    return intent, details
                unsupported_details = details
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                attempts.append(
                    {
                        "model": model,
                        "provider": provider,
                        "success": False,
                        "error": str(exc).strip() or type(exc).__name__,
                    }
                )

        if unsupported_details is not None:
            unsupported_details["ai_attempts"] = list(attempts)
            return None, unsupported_details
        if last_error is not None:
            summary = "; ".join(
                f"{item['model']}: {item.get('error') or 'unsupported'}"
                for item in attempts
            )
            raise RuntimeError(summary or str(last_error)) from last_error
        raise RuntimeError("No semantic-intent model is configured")

    SemanticReadIntentClassifier._classify_with_ai = classify_with_failover
    SemanticReadIntentClassifier._direct_cloud_failover_installed = True


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

    _install_semantic_cloud_failover()
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

        provider = str(diagnostics.get("ai_provider") or "AI semantic classifier")
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
                "answered_by": "AI intent + deterministic Hubitat MCP",
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
                answer["ai_provider"] = provider
            return answer

        model = diagnostics.get("ai_model")
        answer.update(
            {
                "route": "semantic+mcp",
                "semantic_intent": intent.response_dict(),
                "semantic_classifier": diagnostics,
                "intent_model": model,
                "answered_by": "AI intent + deterministic Hubitat MCP",
            }
        )
        if model:
            # Reuse the existing model/provider badges and request-trace field while
            # making clear that this model classified the intent, not the live values.
            answer["model"] = model
            answer["ai_provider"] = provider
        return answer

    application.ask = semantic_ask
    return classifier


__all__ = ["install_semantic_read_pipeline"]

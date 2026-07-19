from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable

from routing_policy import is_semantic_read_candidate, normalise


AskHandler = Callable[[Any], Awaitable[dict[str, Any]]]

_SUPPORTED_METRICS = {
    "power",
    "temperature",
    "humidity",
    "battery",
    "illuminance",
    "energy",
}
_SUPPORTED_OPERATIONS = {"max", "min", "rank"}
_SUPPORTED_GROUPS = {"device", "room"}
_SUPPORTED_SCOPES = {"all", "room", "entities"}

_INTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["metric_comparison", "unsupported"]},
        "metric": {
            "type": "string",
            "enum": sorted(_SUPPORTED_METRICS | {"unknown"}),
        },
        "operation": {
            "type": "string",
            "enum": sorted(_SUPPORTED_OPERATIONS),
        },
        "group_by": {
            "type": "string",
            "enum": sorted(_SUPPORTED_GROUPS),
        },
        "scope_kind": {
            "type": "string",
            "enum": sorted(_SUPPORTED_SCOPES),
        },
        "scope_name": {"type": "string", "maxLength": 100},
        "entity_names": {
            "type": "array",
            "items": {"type": "string", "maxLength": 100},
            "maxItems": 8,
        },
        "top_n": {"type": "integer", "minimum": 1, "maximum": 10},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "intent",
        "metric",
        "operation",
        "group_by",
        "scope_kind",
        "scope_name",
        "entity_names",
        "top_n",
        "confidence",
    ],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class SemanticReadIntent:
    intent: str
    metric: str
    operation: str
    group_by: str
    scope_kind: str
    scope_name: str
    entity_names: tuple[str, ...]
    top_n: int
    confidence: float

    def response_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["entity_names"] = list(self.entity_names)
        return value


class SemanticReadIntentClassifier:
    """Use the local planner model only to understand a read-only question.

    The model cannot call MCP tools or execute commands here. Its JSON output is
    validated into a small allowlisted schema before deterministic code can use it.
    """

    def __init__(
        self,
        application: Any,
        *,
        timeout_seconds: float = 5.0,
        cache_ttl_seconds: float = 300.0,
    ) -> None:
        self.application = application
        self.timeout_seconds = max(1.0, min(15.0, float(timeout_seconds)))
        self.cache_ttl_seconds = max(10.0, min(3600.0, float(cache_ttl_seconds)))
        self._cache: dict[str, tuple[float, SemanticReadIntent, dict[str, Any]]] = {}

    async def classify(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[SemanticReadIntent | None, dict[str, Any]]:
        key = normalise(query)
        cached = self._cache.get(key)
        now = time.monotonic()
        if cached and now - cached[0] <= self.cache_ttl_seconds:
            diagnostics = dict(cached[2])
            diagnostics["cache"] = "hit"
            return cached[1], diagnostics

        diagnostics: dict[str, Any] = {
            "cache": "miss",
            "classifier": "local-ollama-structured-intent",
        }
        intent: SemanticReadIntent | None = None

        if self.application.option_bool("ollama_enabled", True):
            try:
                intent, ai_details = await self._classify_with_ai(query, history or [])
                diagnostics.update(ai_details)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                diagnostics.update(
                    {
                        "ai_success": False,
                        "ai_error": str(exc).strip() or type(exc).__name__,
                    }
                )

        if intent is None:
            intent = self._deterministic_fallback(query)
            diagnostics["fallback_parser_used"] = intent is not None

        if intent is not None:
            self._cache[key] = (now, intent, dict(diagnostics))
        return intent, diagnostics

    async def _classify_with_ai(
        self,
        query: str,
        history: list[dict[str, str]],
    ) -> tuple[SemanticReadIntent | None, dict[str, Any]]:
        agent = self.application.ollama
        client = getattr(agent, "_http", None)
        post = getattr(client, "post", None)
        if not callable(post):
            raise RuntimeError("Ollama HTTP client is unavailable")

        model = str(
            getattr(agent, "planner_model", "")
            or getattr(agent, "local_fallback_model", "")
            or getattr(agent, "model", "")
        ).strip()
        if not model:
            raise RuntimeError("No local semantic-intent model is configured")

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
            "format": _INTENT_SCHEMA,
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
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("Ollama returned a non-object semantic response")
        if str(body.get("done_reason") or "").lower() == "length":
            raise RuntimeError("Semantic intent response was truncated")

        message = body.get("message") or {}
        content = str(message.get("content") or "").strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I | re.S).strip()
        decoded = json.loads(content)
        intent = self.validate_payload(decoded)
        details = {
            "ai_success": intent is not None,
            "ai_model": model,
            "ai_provider": "Local Ollama semantic classifier",
        }
        return intent, details

    @staticmethod
    def validate_payload(value: Any) -> SemanticReadIntent | None:
        if not isinstance(value, dict) or value.get("intent") != "metric_comparison":
            return None

        metric = str(value.get("metric") or "").strip().lower()
        operation = str(value.get("operation") or "").strip().lower()
        group_by = str(value.get("group_by") or "").strip().lower()
        scope_kind = str(value.get("scope_kind") or "").strip().lower()
        if metric not in _SUPPORTED_METRICS:
            return None
        if operation not in _SUPPORTED_OPERATIONS:
            return None
        if group_by not in _SUPPORTED_GROUPS:
            return None
        if scope_kind not in _SUPPORTED_SCOPES:
            return None

        names = value.get("entity_names") or []
        if not isinstance(names, list):
            return None
        entity_names = tuple(
            dict.fromkeys(
                str(item).strip()[:100]
                for item in names[:8]
                if str(item).strip()
            )
        )
        try:
            top_n = max(1, min(10, int(value.get("top_n") or 3)))
        except Exception:
            top_n = 3
        try:
            confidence = max(0.0, min(1.0, float(value.get("confidence") or 0.0)))
        except Exception:
            confidence = 0.0

        return SemanticReadIntent(
            intent="metric_comparison",
            metric=metric,
            operation=operation,
            group_by=group_by,
            scope_kind=scope_kind,
            scope_name=str(value.get("scope_name") or "").strip()[:100],
            entity_names=entity_names,
            top_n=top_n,
            confidence=confidence,
        )

    @staticmethod
    def _deterministic_fallback(query: str) -> SemanticReadIntent | None:
        """Small resilient fallback; AI remains the primary interpreter."""

        q = normalise(query)
        if not is_semantic_read_candidate(q):
            return None

        metric = ""
        if any(term in q for term in ("kwh", "energy total", "energy used", "energy usage")):
            metric = "energy"
        elif any(
            term in q
            for term in (
                "power",
                "watt",
                "electricity",
                "power draw",
                "drawing",
                "load",
                "greediest",
            )
        ):
            metric = "power"
        elif any(term in q for term in ("temperature", "temp", "warm", "hot", "cold", "cool")):
            metric = "temperature"
        elif any(term in q for term in ("humidity", "humid", "damp", "dry", "moist")):
            metric = "humidity"
        elif any(term in q for term in ("battery", "charge")):
            metric = "battery"
        elif any(term in q for term in ("illuminance", "lux", "bright", "dark")):
            metric = "illuminance"
        if not metric:
            return None

        operation = "max"
        if any(
            term in q
            for term in (
                "least",
                "lowest",
                "smallest",
                "bottom",
                "coldest",
                "coolest",
                "driest",
                "darkest",
            )
        ):
            operation = "min"
        if any(term in q for term in ("rank", "ranking", "top ", "bottom ", "list")):
            operation = "rank"

        top_n = 3
        top_match = re.search(r"\b(?:top|bottom)\s+(\d{1,2})\b", q)
        if top_match:
            top_n = max(1, min(10, int(top_match.group(1))))

        return SemanticReadIntent(
            intent="metric_comparison",
            metric=metric,
            operation=operation,
            group_by="room" if "room" in q else "device",
            scope_kind="all",
            scope_name="",
            entity_names=(),
            top_n=top_n,
            confidence=0.55,
        )


def install_semantic_read_intent(
    application: Any,
    executor: Any,
    *,
    timeout_seconds: float = 5.0,
    cache_ttl_seconds: float = 300.0,
) -> SemanticReadIntentClassifier:
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
        if not is_semantic_read_candidate(query):
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

        answer.update(
            {
                "route": "semantic+mcp",
                "semantic_intent": intent.response_dict(),
                "semantic_classifier": diagnostics,
                "answered_by": "Local AI intent + deterministic Hubitat MCP",
            }
        )
        return answer

    application.ask = semantic_ask
    return classifier


__all__ = [
    "SemanticReadIntent",
    "SemanticReadIntentClassifier",
    "install_semantic_read_intent",
]

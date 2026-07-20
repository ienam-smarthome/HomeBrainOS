from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable

import control_agent_gate
import control_agent_intent
import control_agent_rescue
import request_tracing
import routing_policy
from control_agent_intent import (
    ControlActionIntent,
    ControlIntent,
    ControlIntentInterpreter,
    ControlTargetIntent,
)


_CONTROL_NOUNS = re.compile(
    r"\b(?:light|lights|lamp|lamps|bulb|bulbs|fan|fans|switch|switches|"
    r"socket|sockets|plug|plugs|outlet|outlets|tv|television|dehumidifier|"
    r"purifier|robot|roborock)\b",
    re.IGNORECASE,
)
_CONTROL_ACTIONS = re.compile(
    r"\b(?:turn|switch|set|put|make|bring|dim|brighten|lower|raise|increase|"
    r"decrease|reduce|kill|shut|power|activate|deactivate|start|stop)\b",
    re.IGNORECASE,
)
_READ_PREFIX = re.compile(
    r"^(?:what|which|who|where|when|why|how|is|are|was|were|show|list|tell|"
    r"compare|explain|check)\b",
    re.IGNORECASE,
)
_LEVEL_CUE = re.compile(
    r"(?:\d{1,3}\s*%|\bpercent\b|\bper\s+cent\b|\bbrightness\b|"
    r"\bhalf\b|\bquarter\b|\bfull\s+brightness\b)",
    re.IGNORECASE,
)

_NATURAL_LEVEL = re.compile(
    r"^(?:please\s+)?(?:put|set|make|bring|dim)\s+(?:the\s+)?(?P<target>.+?)\s+"
    r"(?:(?:down|up)\s+)?(?:to|at)\s+(?:(?:about|around|roughly|approximately)\s+)?"
    r"(?P<value>[a-z0-9\-\s]+?)\s*(?:%|percent|per\s+cent|brightness)?[.!?]*$",
    re.IGNORECASE,
)
_NATURAL_LEVEL_BARE = re.compile(
    r"^(?:please\s+)?(?:put|set|make|dim)\s+(?:the\s+)?(?P<target>.+?)\s+"
    r"(?:(?:about|around|roughly|approximately)\s+)?(?P<value>\d{1,3})\s*%[.!?]*$",
    re.IGNORECASE,
)

_ONES = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_SPECIAL_LEVELS = {
    "quarter": 25,
    "a quarter": 25,
    "one quarter": 25,
    "half": 50,
    "a half": 50,
    "three quarters": 75,
    "three quarter": 75,
    "full": 100,
    "full brightness": 100,
    "maximum": 100,
    "max": 100,
    "off": 0,
}
_TRAILING_RELATIVE = re.compile(r"\b(?:dimmer|brighter|lower|higher|more|less)\b", re.I)


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def percentage_value(value: str) -> int | None:
    text = _normalise(value).strip(" .!?%")
    text = re.sub(r"\b(?:percent|per\s+cent|brightness)\b", "", text).strip()
    if text in _SPECIAL_LEVELS:
        return _SPECIAL_LEVELS[text]
    if re.fullmatch(r"\d{1,3}", text):
        number = int(text)
        return number if 0 <= number <= 100 else None

    tokens = [item for item in re.split(r"[\s-]+", text) if item and item != "and"]
    if not tokens:
        return None
    total = 0
    current = 0
    for token in tokens:
        if token in _ONES:
            current += _ONES[token]
        elif token in _TENS:
            current += _TENS[token]
        elif token == "hundred":
            current = max(1, current) * 100
        else:
            return None
    total += current
    return total if 0 <= total <= 100 else None


def is_probable_control_request(query: str) -> bool:
    """Broad, conservative control triage used before the read-only router.

    This deliberately recognises natural imperatives without deciding a device ID or
    executing anything. Questions with an interrogative/read prefix remain on read
    routes. Actual intent still has to pass the strict ControlIntent schema and the
    deterministic selected-device resolver.
    """

    text = _normalise(query).strip(" .!?")
    if not text or _READ_PREFIX.match(text):
        return False
    if not _CONTROL_NOUNS.search(text):
        return False
    if _CONTROL_ACTIONS.search(text):
        return True
    return bool(_LEVEL_CUE.search(text) and re.search(r"\b(?:at|to|on|off)\b", text))


def parse_natural_level(query: str) -> ControlIntent | None:
    text = str(query or "").strip()
    match = _NATURAL_LEVEL.match(text) or _NATURAL_LEVEL_BARE.match(text)
    if not match:
        return None
    target = re.sub(r"\s+", " ", match.group("target").strip(" .!?"))
    raw_value = match.group("value")
    if not target or _TRAILING_RELATIVE.search(raw_value):
        return None
    value = percentage_value(raw_value)
    if value is None:
        return None
    return ControlIntent(
        intent="device_control",
        actions=(
            ControlActionIntent(
                command="set_level",
                value=float(value),
                target=ControlTargetIntent(name_hint=target),
            ),
        ),
        confidence=0.99,
        interpreter="deterministic-natural-control-parser",
    )


def _model_candidates(interpreter: ControlIntentInterpreter) -> list[tuple[str, str, float]]:
    application = interpreter.application
    agent = application.ollama
    local = str(
        getattr(agent, "planner_model", "")
        or getattr(agent, "local_fallback_model", "")
        or getattr(agent, "model", "")
    ).strip()
    cloud = str(getattr(agent, "cloud_model", "") or "").strip()
    values: list[tuple[str, str, float]] = []
    if local:
        values.append((local, "Local Ollama control interpreter", interpreter.timeout_seconds))
    if (
        application.option_bool("control_agent_cloud_fallback_enabled", True)
        and bool(getattr(agent, "cloud_enabled", False))
        and cloud
        and cloud != local
    ):
        timeout = float(
            application.OPTIONS.get("control_agent_cloud_timeout_seconds")
            or application.OPTIONS.get("ollama_cloud_timeout_seconds")
            or 12
        )
        values.append((cloud, "Ollama Cloud structured control interpreter", max(5.0, timeout)))
    return values


async def _interpret_with_model(
    interpreter: ControlIntentInterpreter,
    model: str,
    provider: str,
    timeout: float,
    query: str,
    *,
    history: list[dict[str, str]],
    context: dict[str, Any],
    inventory: str,
) -> tuple[ControlIntent | None, dict[str, Any]]:
    agent = interpreter.application.ollama
    client = getattr(agent, "_http", None)
    post = getattr(client, "post", None)
    if not callable(post):
        raise RuntimeError("Ollama HTTP client is unavailable")

    recent = "\n".join(
        f"{str(item.get('role') or '')}: {str(item.get('content') or '')[:240]}"
        for item in history[-4:]
        if item.get("role") in {"user", "assistant"} and item.get("content")
    ) or "None"
    context_text = json.dumps(context, ensure_ascii=False, separators=(",", ":"))[:1600]
    inventory_text = inventory[:7000] or "No selected-device inventory supplied."
    system = (
        "/no_think\n"
        "Act like a careful MCP smart-home control planner. First understand the user's "
        "natural instruction, then match it against the supplied selected-device inventory. "
        "You have no tools and cannot execute anything. Return only the strict JSON schema. "
        "Supported commands are on, off and set_level from 0 to 100. Convert spoken numbers "
        "and approximate wording such as about thirty percent into a numeric level. Put semantic "
        "room, type, ordinal, quantifier and reference information in dedicated fields. Never "
        "invent a device ID or claim success. Return unsupported for schedules, conditions, locks, "
        "alarms, doors, heating changes, rule changes or anything outside supported commands."
    )
    user = (
        f"Selected devices (label | room | types):\n{inventory_text}\n\n"
        f"Structured context:\n{context_text}\n\nRecent conversation:\n{recent}\n\n"
        f"Current request:\n{query.strip()}"
    )
    response = await post(
        f"{str(agent.base_url).rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "think": False,
            "format": control_agent_intent._CONTROL_INTENT_SCHEMA,
            "keep_alive": str(getattr(agent, "keep_alive", "30m") or "30m"),
            "options": {
                "num_ctx": 3072,
                "num_predict": 280,
                "temperature": 0,
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError(f"{provider} returned a non-object control intent")
    content = str((body.get("message") or {}).get("content") or "").strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I | re.S).strip()
    payload = json.loads(content)
    intent = interpreter.validate_payload(payload, model=model)
    return intent, {
        "ai_used": True,
        "ai_model": model,
        "ai_provider": provider,
        "ai_success": intent is not None,
        "raw_intent": str(payload.get("intent") or "") if isinstance(payload, dict) else "",
    }


def install_claude_first_control_interpreter() -> None:
    """Install agent-first triage and strong structured-model fallback.

    Clear deterministic controls still avoid AI. Other probable controls reach the
    inventory-aware Control Agent before any read-only or general answer route. The
    model never receives MCP command tools; deterministic Python remains responsible
    for device IDs, policy, execution and verification.
    """

    if getattr(ControlIntentInterpreter, "_claude_first_installed", False):
        return

    original_candidate = control_agent_intent.is_control_candidate
    original_deterministic: Callable[[str], ControlIntent | None] = (
        ControlIntentInterpreter._deterministic_intent
    )

    def combined_candidate(query: str) -> bool:
        return bool(original_candidate(query) or is_probable_control_request(query))

    def deterministic_first(query: str) -> ControlIntent | None:
        natural = parse_natural_level(query)
        return natural if natural is not None else original_deterministic(query)

    async def model_chain(
        self: ControlIntentInterpreter,
        query: str,
        *,
        history: list[dict[str, str]],
        context: dict[str, Any],
        inventory: str,
    ) -> tuple[ControlIntent | None, dict[str, Any]]:
        attempts: list[dict[str, Any]] = []
        for model, provider, timeout in _model_candidates(self):
            try:
                intent, details = await _interpret_with_model(
                    self,
                    model,
                    provider,
                    timeout,
                    query,
                    history=history,
                    context=context,
                    inventory=inventory,
                )
                attempts.append({**details, "error": None})
                if intent is not None:
                    return intent, {**details, "model_attempts": attempts}
                if details.get("raw_intent") == "unsupported":
                    return None, {**details, "model_attempts": attempts, "unsupported": True}
            except Exception as exc:
                attempts.append(
                    {
                        "ai_used": True,
                        "ai_model": model,
                        "ai_provider": provider,
                        "ai_success": False,
                        "error": str(exc).strip() or type(exc).__name__,
                    }
                )
        last_error = next(
            (str(item.get("error")) for item in reversed(attempts) if item.get("error")),
            "No configured control model produced a valid structured intent.",
        )
        raise RuntimeError(last_error)

    control_agent_intent.is_control_candidate = combined_candidate
    control_agent_gate.is_control_candidate = combined_candidate
    control_agent_rescue.is_control_candidate = combined_candidate
    ControlIntentInterpreter._deterministic_intent = staticmethod(deterministic_first)
    ControlIntentInterpreter._interpret_with_ai = model_chain

    original_trace_classify = request_tracing.classify_query

    def trace_classify(query: str) -> routing_policy.RouteDecision:
        if is_probable_control_request(query):
            return routing_policy.RouteDecision(
                "control-agent",
                "probable natural device control; inventory-aware structured interpretation runs before read-only routing",
            )
        return original_trace_classify(query)

    request_tracing.classify_query = trace_classify
    ControlIntentInterpreter._claude_first_installed = True


__all__ = [
    "install_claude_first_control_interpreter",
    "is_probable_control_request",
    "parse_natural_level",
    "percentage_value",
]
